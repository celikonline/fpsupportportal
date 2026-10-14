import io
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, IntegrityError, DatabaseError, transaction
from django.db.models import F
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import *
from .security import tenant_context
from .sla import snapshot, business_due, business_minutes_between
from .tasks import scan_attachment, dispatch_outbox

class PortalSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = get_user_model().objects.create_user('test-agent', password='test-password-123')
        cls.customer = get_user_model().objects.create_user('test-customer', password='test-password-123')
        cls.other = get_user_model().objects.create_user('test-other', password='test-password-123')
        cls.a = Tenant.objects.create(name='A')
        cls.b = Tenant.objects.create(name='B')
        for tenant in [cls.a, cls.b]:
            for user in [cls.agent, cls.customer, cls.other]:
                TenantMembership.objects.create(tenant=tenant, user=user)
        cls.p = Project.objects.create(tenant=cls.a, name='P', code='p')
        cls.hidden = Project.objects.create(tenant=cls.a, name='Hidden', code='hidden')
        cls.q = Project.objects.create(tenant=cls.b, name='Q', code='q')
        for project in [cls.p, cls.q]:
            for user, role in [(cls.agent, 'agent'), (cls.customer, 'requester'), (cls.other, 'requester')]:
                ProjectMembership.objects.create(tenant=project.tenant, project=project, user=user, role=role)
        def ticket(project, number, requester):
            now, policy = timezone.now(), snapshot(project)
            return Ticket.objects.create(tenant=project.tenant, project=project, number=number, title='Ticket', description='Body',
                                         requester=requester, policy_snapshot=policy, first_response_due=business_due(now,240,policy), resolution_due=business_due(now,1440,policy))
        cls.ticket = ticket(cls.p, 1, cls.customer)
        cls.other_ticket = ticket(cls.p, 2, cls.other)
        cls.foreign_ticket = ticket(cls.q, 1, cls.customer)
        cls.p.next_number = 3
        cls.p.save(update_fields=['next_number'])
        cls.note = Comment.objects.create(tenant=cls.a, project=cls.p, ticket=cls.ticket, author=cls.agent, visibility='internal', body='secret-internal')
        cls.file = Attachment.objects.create(tenant=cls.a, project=cls.p, owner=cls.agent, comment=cls.note, filename='secret.png',
                                             mime_type='image/png', size=10, sha256='x', state='clean', storage_key=str(uuid.uuid4()))

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.customer)
        self.base = f'/api/v1/tenants/{self.a.pk}/projects/{self.p.pk}'
        self.temp = TemporaryDirectory()
        self.override = override_settings(PRIVATE_STORAGE_ROOT=Path(self.temp.name))
        self.override.enable()
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SET ROLE support_app')

    def tearDown(self):
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
        self.override.disable()
        self.temp.cleanup()

    def test_requester_sees_only_own_ticket(self):
        response = self.client.get(self.base + '/tickets')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(self.client.get(self.base + '/tickets/' + str(self.other_ticket.pk)).status_code, 404)

    def test_cross_tenant_object_and_project_denied(self):
        self.assertEqual(self.client.get(self.base + '/tickets/' + str(self.foreign_ticket.pk)).status_code, 404)
        hidden = f'/api/v1/tenants/{self.a.pk}/projects/{self.hidden.pk}/tickets'
        self.assertEqual(self.client.get(hidden).status_code, 404)
        mismatch = f'/api/v1/tenants/{self.a.pk}/projects/{self.q.pk}/tickets'
        self.assertEqual(self.client.get(mismatch).status_code, 404)

    def test_internal_note_and_attachment_are_hidden(self):
        result = self.client.get(self.base + '/tickets/' + str(self.ticket.pk))
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('secret-internal', str(result.data))
        self.assertNotIn('secret.png', str(result.data))
        self.assertEqual(self.client.get(self.base + '/attachments/' + str(self.file.pk)).status_code, 404)
        result = self.client.post(self.base + '/tickets/' + str(self.ticket.pk) + '/comments',
                                  {'body': 'forbidden', 'visibility': 'internal'}, format='json', HTTP_IDEMPOTENCY_KEY='internal')
        self.assertEqual(result.status_code, 403)

    def test_idempotency_replay_and_conflicting_payload(self):
        payload = {'title': 'A new issue', 'description': 'Reproduction steps'}
        first = self.client.post(self.base + '/tickets', payload, format='json', HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(first.status_code, 201)
        replay = self.client.post(self.base + '/tickets', payload, format='json', HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.data['id'], replay.data['id'])
        payload['title'] = 'changed'
        self.assertEqual(self.client.post(self.base + '/tickets', payload, format='json', HTTP_IDEMPOTENCY_KEY='same').status_code, 409)

    def test_revoked_membership_stops_existing_session(self):
        TenantMembership.objects.filter(tenant=self.a, user=self.customer).update(active=False)
        self.assertEqual(self.client.get(self.base + '/tickets').status_code, 404)

    def test_stale_version_does_not_overwrite(self):
        self.client.force_authenticate(self.agent)
        response = self.client.patch(self.base + '/tickets/' + str(self.ticket.pk), {'priority': 'high'}, format='json', HTTP_IF_MATCH='"0"')
        self.assertEqual(response.status_code, 409)
        response = self.client.patch(self.base + '/tickets/' + str(self.ticket.pk), {'priority': 'high'}, format='json', HTTP_IF_MATCH='"1"')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['version'], 2)

    def test_observer_cannot_write(self):
        with tenant_context(self.a.pk):
            ProjectMembership.objects.filter(project=self.p, user=self.customer).update(role='observer')
        self.assertEqual(self.client.post(self.base + '/tickets', {'title': 'no', 'description': 'no'}, format='json', HTTP_IDEMPOTENCY_KEY='x').status_code, 403)

    def test_spoofed_file_rejected(self):
        draft = self.client.post(self.base + '/drafts', {}, format='json').data['id']
        upload = SimpleUploadedFile('fake.png', b'not a PNG', content_type='image/png')
        response = self.client.post(self.base + '/drafts/' + draft + '/uploads', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_foreign_draft_cannot_bind(self):
        with tenant_context(self.a.pk):
            draft = Draft.objects.create(tenant=self.a, project=self.p, owner=self.other, expires_at=timezone.now()+timedelta(hours=1))
        response = self.client.post(self.base + '/tickets', {'title':'x','description':'x','draftId':str(draft.pk)}, format='json', HTTP_IDEMPOTENCY_KEY='foreign-draft')
        self.assertEqual(response.status_code, 400)

    @override_settings(DEV_SCAN_BYPASS=True)
    def test_image_scan_and_single_binding(self):
        image = io.BytesIO()
        Image.new('RGB', (20,20), 'red').save(image,format='PNG')
        draft = self.client.post(self.base+'/drafts',{},format='json').data['id']
        with patch('portal.tasks.enqueue_scan'):
            response = self.client.post(self.base+'/drafts/'+draft+'/uploads', {'file':SimpleUploadedFile('paste.png',image.getvalue(),'image/png')},format='multipart')
        self.assertEqual(response.status_code,201)
        attachment_id = response.data['id']
        scan_attachment(str(self.a.pk), attachment_id)
        first = self.client.post(self.base+'/tickets',{'title':'paste','description':'image','draftId':draft},format='json',HTTP_IDEMPOTENCY_KEY='image')
        self.assertEqual(first.status_code,201)
        self.assertEqual(first.data['attachments'][0]['state'],'clean')
        download = self.client.get(self.base+'/attachments/'+attachment_id)
        self.assertEqual(download.status_code,200)
        self.assertTrue(b''.join(download.streaming_content).startswith(b'\x89PNG'))
        second = self.client.post(self.base+'/tickets',{'title':'reuse','description':'image','draftId':draft},format='json',HTTP_IDEMPOTENCY_KEY='reuse')
        self.assertEqual(second.status_code,400)

    def test_scanner_failure_does_not_release_attachment(self):
        key=str(uuid.uuid4());Path(self.temp.name,key).write_bytes(b'hello')
        with tenant_context(self.a.pk):
            item=Attachment.objects.create(tenant=self.a,project=self.p,owner=self.customer,ticket=self.ticket,filename='x.txt',mime_type='text/plain',size=5,sha256='x',storage_key=key)
        with patch('portal.tasks.antivirus',side_effect=OSError('offline')):
            scan_attachment(str(self.a.pk),str(item.pk))
        with tenant_context(self.a.pk):
            item.refresh_from_db();self.assertEqual(item.state,'scanning')
        self.assertEqual(self.client.get(self.base+'/attachments/'+str(item.pk)).status_code,403)

    def test_postgres_rls_missing_context_and_cross_scope(self):
        if connection.vendor!='postgresql':
            self.skipTest('Requires PostgreSQL runtime role')
        self.assertEqual(Ticket.objects.count(),0)
        with tenant_context(self.a.pk):
            self.assertEqual(Ticket.objects.filter(pk=self.foreign_ticket.pk).count(),0)
            with self.assertRaises(DatabaseError), transaction.atomic():
                Ticket.objects.create(tenant=self.b,project=self.q,number=42,title='leak',description='leak',requester=self.customer,
                                      first_response_due=timezone.now(),resolution_due=timezone.now())
        self.assertEqual(Ticket.objects.count(),0)

    def test_tenant_admin_does_not_have_implicit_project_access(self):
        TenantMembership.objects.filter(tenant=self.a,user=self.customer).update(role='admin')
        hidden=f'/api/v1/tenants/{self.a.pk}/projects/{self.hidden.pk}/tickets'
        self.assertEqual(self.client.get(hidden).status_code,404)

    def test_notification_redelivery_deduplicates(self):
        with tenant_context(self.a.pk):
            event=Outbox.objects.create(tenant=self.a,project=self.p,ticket=self.ticket,action='reply')
        dispatch_outbox();dispatch_outbox()
        with tenant_context(self.a.pk):
            self.assertEqual(Notification.objects.filter(event=event,user=self.customer).count(),1)
            self.assertEqual(Notification.objects.filter(event=event,user=self.other).count(),0)

    def test_replay_rechecks_current_role_and_hides_internal_notes(self):
        self.client.force_authenticate(self.agent)
        payload={'title':'owned by staff','description':'issue'}
        result=self.client.post(self.base+'/tickets',payload,format='json',HTTP_IDEMPOTENCY_KEY='downgrade')
        self.assertEqual(result.status_code,201)
        with tenant_context(self.a.pk):
            ticket=Ticket.objects.get(pk=result.data['id'])
            Comment.objects.create(tenant=self.a,project=self.p,ticket=ticket,author=self.agent,visibility='internal',body='hidden-after-downgrade')
            ProjectMembership.objects.filter(project=self.p,user=self.agent).update(role='requester')
        replay=self.client.post(self.base+'/tickets',payload,format='json',HTTP_IDEMPOTENCY_KEY='downgrade')
        self.assertEqual(replay.status_code,200)
        self.assertNotIn('hidden-after-downgrade',str(replay.data))

    def test_erasure_honors_legal_hold(self):
        from .tasks import erase_person
        with tenant_context(self.a.pk):
            Ticket.objects.filter(pk=self.ticket.pk).update(legal_hold=True)
            item=PrivacyRequest.objects.create(tenant=self.a,user=self.customer,kind='erasure',status='processing')
        erase_person(str(self.a.pk),str(item.pk))
        with tenant_context(self.a.pk):
            item.refresh_from_db();self.ticket.refresh_from_db()
            self.assertEqual(item.status,'in_review');self.assertEqual(self.ticket.title,'Ticket')

    def test_erasure_redacts_tenant_content_without_touching_other_tenant(self):
        from .tasks import erase_person
        with tenant_context(self.a.pk):
            item=PrivacyRequest.objects.create(tenant=self.a,user=self.customer,kind='erasure',status='processing')
        erase_person(str(self.a.pk),str(item.pk))
        with tenant_context(self.a.pk):
            self.ticket.refresh_from_db();item.refresh_from_db()
            self.assertEqual(self.ticket.description,'[İmha edildi]');self.assertEqual(item.status,'completed')
        with tenant_context(self.b.pk):
            self.foreign_ticket.refresh_from_db();self.assertEqual(self.foreign_ticket.description,'Body')
        TenantMembership.objects.filter(tenant=self.a,user=self.agent).update(role='admin')
        self.client.force_authenticate(self.agent)
        members=self.client.get(f'/api/v1/tenants/{self.a.pk}/admin').data['members']
        erased=next(m for m in members if m['id']==self.customer.pk)
        self.assertEqual(erased['name'],'Anonim kullanıcı');self.assertEqual(erased['username'],'anonim')

    def test_erasure_requires_two_different_admins(self):
        for user in [self.agent,self.other]:
            TenantMembership.objects.filter(tenant=self.a,user=user).update(role='admin')
        with tenant_context(self.a.pk):
            item=PrivacyRequest.objects.create(tenant=self.a,user=self.customer,kind='erasure')
        self.client.force_authenticate(self.agent)
        session=self.client.session;session['mfa_at']=timezone.now().timestamp();session.save()
        path=f'/api/v1/tenants/{self.a.pk}/privacy/{item.pk}'
        self.assertEqual(self.client.post(path,{'action':'approve_erasure','reason':'reviewed'},format='json').status_code,400)
        self.assertEqual(self.client.post(path,{'action':'review','reason':'identity checked','identityVerified':True},format='json').status_code,200)
        self.assertEqual(self.client.post(path,{'action':'approve_erasure','reason':'no retention obligation'},format='json').status_code,200)
        self.assertEqual(self.client.post(path,{'action':'execute_erasure'},format='json').status_code,400)
        self.client.force_authenticate(self.other)
        with patch('portal.tasks.erase_person.delay'):
            self.assertEqual(self.client.post(path,{'action':'execute_erasure'},format='json').status_code,200)

    def test_audit_table_is_append_only_for_runtime_role(self):
        if connection.vendor!='postgresql':self.skipTest('Requires PostgreSQL')
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('DELETE FROM portal_auditevent')

    def test_s3_adapter_uses_private_namespaces_and_encryption(self):
        from .files import persist_blob,hydrate_blob,open_blob,remove_blob
        from unittest.mock import MagicMock
        key=str(uuid.uuid4());Path(self.temp.name,key).write_bytes(b'clean')
        client=MagicMock();client.get_object.return_value={'Body':io.BytesIO(b'clean')}
        with override_settings(STORAGE_BACKEND='s3',S3_BUCKET='private-test'),patch('portal.files.s3_client',return_value=client):
            persist_blob(key)
            arguments=client.put_object.call_args.kwargs
            self.assertEqual(arguments['Key'],'quarantine/'+key);self.assertEqual(arguments['ServerSideEncryption'],'AES256')
            hydrate_blob(key);self.assertEqual(open_blob(key).read(),b'clean');remove_blob(key)
            self.assertEqual(client.delete_object.call_count,2)

    def test_sla_escalation_is_not_duplicated(self):
        from .tasks import maintenance
        with tenant_context(self.a.pk):
            Ticket.objects.filter(pk=self.ticket.pk).update(first_response_due=timezone.now()-timedelta(minutes=1))
        with patch('portal.tasks.enqueue_scan'):
            maintenance();maintenance()
        with tenant_context(self.a.pk):
            self.assertEqual(TicketEvent.objects.filter(ticket=self.ticket,action='sla_breach').count(),1)

    @override_settings(DEV_SCAN_BYPASS=True)
    def test_clean_image_cannot_expand_beyond_tenant_quota(self):
        key=str(uuid.uuid4());path=Path(self.temp.name,key);path.write_bytes(b'original')
        with tenant_context(self.a.pk):
            Tenant.objects.filter(pk=self.a.pk).update(quota_bytes=100)
            item=Attachment.objects.create(tenant=self.a,project=self.p,owner=self.customer,ticket=self.ticket,filename='x.png',mime_type='image/png',size=8,sha256='x',storage_key=key)
        with patch('portal.tasks.sanitize_image',side_effect=lambda p,m:p.write_bytes(b'x'*101)):
            scan_attachment(str(self.a.pk),str(item.pk))
        with tenant_context(self.a.pk):
            item.refresh_from_db();self.assertEqual(item.state,'rejected')
        self.assertFalse(path.exists())

    def test_api_key_is_one_time_project_scoped_and_revocable(self):
        session = self.client.session
        session['mfa_at'] = timezone.now().timestamp()
        session.save()
        url = self.base + '/api-keys'
        created = self.client.post(url, {'name': 'Entegrasyon', 'mode': 'read', 'expiresInDays': 30}, format='json')
        self.assertEqual(created.status_code, 201)
        token = created.data['key']
        self.assertTrue(token.startswith('fpsk_'))
        listed = self.client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(token, str(listed.data))
        with tenant_context(self.a.pk):
            self.assertNotEqual(APIKey.objects.get(pk=created.data['id']).secret_hash, token)

        key_client = APIClient(enforce_csrf_checks=True)
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + token}
        self.assertEqual(key_client.get(self.base + '/tickets', **auth).status_code, 200)
        self.assertEqual(key_client.post(self.base + '/tickets', {'title': 'denied'}, format='json', **auth).status_code, 403)
        self.assertEqual(key_client.get(f'/api/v1/tenants/{self.b.pk}/projects/{self.q.pk}/tickets', **auth).status_code, 401)
        self.assertEqual(key_client.get('/api/v1/me/tenants', **auth).status_code, 403)
        self.assertEqual(key_client.get(url, **auth).status_code, 403)
        self.assertEqual(self.client.delete(url + '/' + created.data['id']).status_code, 200)
        self.assertEqual(key_client.get(self.base + '/tickets', **auth).status_code, 401)

    def test_api_key_write_uses_current_rbac_and_csrf_free_header(self):
        session = self.client.session
        session['mfa_at'] = timezone.now().timestamp()
        session.save()
        created = self.client.post(self.base + '/api-keys', {'name': 'Ticket bot', 'mode': 'read_write', 'expiresInDays': 90}, format='json')
        self.assertEqual(created.status_code, 201)
        key_client = APIClient(enforce_csrf_checks=True)
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + created.data['key'], 'HTTP_IDEMPOTENCY_KEY': 'bot-1'}
        response = key_client.post(self.base + '/tickets', {'title': 'API talebi', 'description': 'bot'}, format='json', **auth)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['requester']['id'], self.customer.pk)
        self.assertEqual(key_client.get(self.base + '/tickets/' + str(self.other_ticket.pk), **auth).status_code, 404)
        with tenant_context(self.a.pk):
            ProjectMembership.objects.filter(project=self.p, user=self.customer).update(active=False)
        self.assertEqual(key_client.get(self.base + '/tickets', **auth).status_code, 401)

    def test_api_key_requires_mfa_and_expiry_is_enforced(self):
        url = self.base + '/api-keys'
        self.assertEqual(self.client.post(url, {'name': 'x', 'mode': 'read', 'expiresInDays': 30}, format='json').status_code, 403)
        session = self.client.session
        session['mfa_at'] = timezone.now().timestamp()
        session.save()
        self.assertEqual(self.client.post(url, {'name': 'x', 'mode': 'read', 'expiresInDays': 366}, format='json').status_code, 400)
        created = self.client.post(url, {'name': 'x', 'mode': 'read', 'expiresInDays': 1}, format='json')
        self.assertEqual(created.status_code, 201)
        with tenant_context(self.a.pk):
            APIKey.objects.filter(pk=created.data['id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(APIClient().get(self.base + '/tickets', HTTP_AUTHORIZATION='Bearer ' + created.data['key']).status_code, 401)

    def _prepare_agent_work(self):
        with tenant_context(self.a.pk):
            ProjectMembership.objects.filter(project=self.p, user=self.other).update(role='lead')
            AutomationConfig.objects.create(tenant=self.a, project=self.p, external_agents=[self.agent.pk])
            work = AgentWork.objects.create(tenant=self.a, project=self.p, ticket=self.ticket)
        self.client.force_authenticate(self.other)
        return work, self.base + '/work-items/tickets/' + str(self.ticket.pk)

    def _route_and_claim(self):
        work, path = self._prepare_agent_work()
        route = self.client.post(path, {'action': 'external', 'assigneeId': self.agent.pk, 'reason': 'Implement and test',
                                      'version': 1, 'ticketVersion': 1}, format='json')
        self.assertEqual(route.status_code, 200, route.data)
        self.client.force_authenticate(self.agent)
        claim_path = self.base + '/work-items/' + str(work.pk)
        claimed = self.client.post(claim_path + '/claim', {'version': route.data['version']}, format='json')
        self.assertEqual(claimed.status_code, 200, claimed.data)
        return work, path, claim_path, claimed.data

    def test_external_solution_requires_po_approval_and_deduplicates_submission(self):
        work, path, job_path, claimed = self._route_and_claim()
        payload = {'action': 'submit', 'claimToken': claimed['claimToken'], 'solution': 'Verified solution and test evidence'}
        result = self.client.post(job_path + '/update', payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['state'], 'solution_review')
        self.assertEqual(self.client.post(job_path + '/update', payload, format='json').status_code, 200)
        with tenant_context(self.a.pk):
            self.assertFalse(Comment.objects.filter(ticket=self.ticket, source='external_agent').exists())
        self.assertEqual(self.client.post(path, {'action': 'approve'}, format='json').status_code, 403)
        self.client.force_authenticate(self.other)
        approval = {'action': 'approve', 'reason': 'Evidence verified', 'version': result.data['version'], 'ticketVersion': result.data['ticket']['version']}
        approved = self.client.post(path, approval, format='json')
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data['state'], 'done')
        self.assertEqual(approved.data['ticket']['status'], 'resolved')
        self.assertEqual(self.client.post(path, approval, format='json').status_code, 400)
        with tenant_context(self.a.pk):
            self.assertEqual(Comment.objects.filter(ticket=self.ticket, source='external_agent').count(), 1)

    def test_expired_lease_can_be_reclaimed_and_old_token_is_rejected(self):
        work, _, path, claimed = self._route_and_claim()
        self.assertEqual(self.client.post(path + '/claim', {'version': claimed['version']}, format='json').status_code, 409)
        with tenant_context(self.a.pk):
            AgentWork.objects.filter(pk=work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        new = self.client.post(path + '/claim', {'version': claimed['version']}, format='json')
        self.assertEqual(new.status_code, 200, new.data)
        self.assertNotEqual(new.data['claimToken'], claimed['claimToken'])
        self.assertEqual(self.client.post(path + '/update', {'action': 'heartbeat', 'claimToken': claimed['claimToken']}, format='json').status_code, 409)
        self.assertEqual(self.client.post(path + '/update', {'action': 'heartbeat', 'claimToken': new.data['claimToken']}, format='json').status_code, 200)

    def test_ticket_change_invalidates_external_solution_and_po_approval(self):
        work, po_path, path, claimed = self._route_and_claim()
        with tenant_context(self.a.pk):
            Ticket.objects.filter(pk=self.ticket.pk).update(version=F('version')+1)
        result = self.client.post(path + '/update', {'action': 'submit', 'claimToken': claimed['claimToken'], 'solution': 'obsolete'}, format='json')
        self.assertEqual(result.status_code, 409)

    def test_external_attachment_read_requires_assigned_work_and_clean_scan(self):
        work, _, path, _ = self._route_and_claim()
        with tenant_context(self.a.pk):
            item = Attachment.objects.create(tenant=self.a, project=self.p, ticket=self.ticket, owner=self.customer,
                filename='test.txt', mime_type='text/plain', size=5, sha256='x', storage_key=str(uuid.uuid4()))
        url = path + '/attachments/' + str(item.pk)
        self.assertEqual(self.client.get(url).status_code, 403)
        Path(self.temp.name, item.storage_key).write_bytes(b'clean')
        with tenant_context(self.a.pk):
            Attachment.objects.filter(pk=item.pk).update(state='clean')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'clean')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_mcp_key_can_only_access_assigned_work_and_cannot_bypass_po(self):
        from .api_key_auth import digest
        work, _, path, claimed = self._route_and_claim()
        token = 'fpsk_123456abcdef_' + 'a'*43
        with tenant_context(self.a.pk):
            APIKey.objects.create(tenant=self.a, project=self.p, user=self.agent, name='MCP', mode='read_write', prefix='123456abcdef', secret_hash=digest(token), expires_at=timezone.now()+timedelta(days=1))
            AgentWork.objects.create(tenant=self.a, project=self.p, ticket=self.other_ticket)
        client = APIClient(enforce_csrf_checks=True)
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + token}
        listed = client.get(self.base + '/work-items?state=claimed', **auth)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data['total'], 1)
        self.assertEqual(client.get(self.base + '/work-items/tickets/' + str(self.other_ticket.pk), **auth).status_code, 404)
        self.assertEqual(client.post(self.base + '/tickets/' + str(self.ticket.pk) + '/comments', {'body': 'bypass'}, format='json', **auth).status_code, 403)
        self.assertEqual(client.get(self.base + '/automation', **auth).status_code, 403)
        self.assertEqual(client.get(f'/api/v1/tenants/{self.b.pk}/projects/{self.q.pk}/work-items', **auth).status_code, 401)
        self.assertEqual(client.post(path + '/update', {'action': 'heartbeat', 'claimToken': claimed['claimToken']}, format='json', **auth).status_code, 200)
        with tenant_context(self.a.pk):
            APIKey.objects.filter(prefix='123456abcdef').update(mode='read')
        self.assertEqual(client.post(path + '/update', {'action': 'heartbeat', 'claimToken': claimed['claimToken']}, format='json', **auth).status_code, 403)

    def test_customer_reply_is_public_once_and_excludes_internal_context(self):
        from .automation_tasks import customer_reply
        with tenant_context(self.a.pk):
            AutomationConfig.objects.create(tenant=self.a, project=self.p, enabled=True, bot=self.agent)
            AutomationReply.objects.create(tenant=self.a, project=self.p, ticket=self.ticket, requested_version=1)
        with patch('portal.automation_tasks.model_reply', return_value={'reply': 'Please provide the error code.', 'needsHuman': True}) as model:
            customer_reply(str(self.a.pk), str(self.ticket.pk))
            customer_reply(str(self.a.pk), str(self.ticket.pk))
            self.assertEqual(model.call_count, 1)
            self.assertNotIn('secret-internal', str(model.call_args))
        self.client.force_authenticate(self.customer)
        result = self.client.get(self.base + '/tickets/' + str(self.ticket.pk))
        bot_comments = [c for c in result.data['comments'] if c['source'] == 'customer_agent']
        self.assertEqual(len(bot_comments), 1)
        self.assertEqual(result.data['status'], 'new')

    def test_customer_reply_discards_stale_model_output(self):
        from .automation_tasks import customer_reply
        with tenant_context(self.a.pk):
            AutomationConfig.objects.create(tenant=self.a, project=self.p, enabled=True, bot=self.agent)
            AutomationReply.objects.create(tenant=self.a, project=self.p, ticket=self.ticket, requested_version=1)
        def model(messages):
            with tenant_context(self.a.pk):
                Ticket.objects.filter(pk=self.ticket.pk).update(version=2)
            return {'reply': 'obsolete', 'needsHuman': False}
        with patch('portal.automation_tasks.model_reply', side_effect=model):
            customer_reply(str(self.a.pk), str(self.ticket.pk))
        with tenant_context(self.a.pk):
            self.assertFalse(Comment.objects.filter(ticket=self.ticket, source='customer_agent').exists())
            self.assertIsNone(AutomationReply.objects.get(ticket=self.ticket).claim_token)

    def test_model_failure_is_retried_without_exposing_provider_secrets(self):
        from .automation_tasks import customer_reply
        with tenant_context(self.a.pk):
            AutomationConfig.objects.create(tenant=self.a, project=self.p, enabled=True, bot=self.agent)
            AutomationReply.objects.create(tenant=self.a, project=self.p, ticket=self.ticket, requested_version=1)
        with patch('portal.automation_tasks.model_reply', side_effect=ValueError('provider-secret')):
            customer_reply(str(self.a.pk), str(self.ticket.pk))
            customer_reply(str(self.a.pk), str(self.ticket.pk))
        with tenant_context(self.a.pk):
            job = AutomationReply.objects.get(ticket=self.ticket)
            self.assertEqual(job.attempts, 1)
            self.assertNotIn('provider-secret', job.error)
            self.assertIsNone(job.claim_token)
            self.assertGreater(job.retry_at, timezone.now())

    def test_new_ticket_creates_po_work_and_durable_customer_reply_job(self):
        with tenant_context(self.a.pk):
            AutomationConfig.objects.create(tenant=self.a, project=self.p, enabled=True, bot=self.agent)
        with patch('portal.automation.enqueue_reply') as enqueue, self.captureOnCommitCallbacks(execute=True):
            result = self.client.post(self.base + '/tickets', {'title': 'A question', 'description': 'Details'}, format='json', HTTP_IDEMPOTENCY_KEY='agent-new')
        self.assertEqual(result.status_code, 201, result.data)
        enqueue.assert_called_once()
        with tenant_context(self.a.pk):
            self.assertEqual(AgentWork.objects.get(ticket_id=result.data['id']).state, 'review')
            self.assertEqual(AutomationReply.objects.get(ticket_id=result.data['id']).requested_version, 1)

    @override_settings(AI_API_URL='https://model.example.test/v1/chat/completions', AI_MODEL='support-model', AI_API_KEY='synthetic-key')
    def test_automation_configuration_requires_po_mfa_and_separate_accounts(self):
        self.assertEqual(self.client.put(self.base + '/automation', {}, format='json').status_code, 403)
        with tenant_context(self.a.pk):
            ProjectMembership.objects.filter(project=self.p, user=self.other).update(role='lead')
        self.client.force_authenticate(self.other)
        payload = {'enabled': True, 'botId': self.agent.pk, 'externalAgentIds': []}
        self.assertEqual(self.client.put(self.base + '/automation', payload, format='json').status_code, 403)
        session = self.client.session; session['mfa_at'] = timezone.now().timestamp(); session.save()
        self.assertEqual(self.client.put(self.base + '/automation', payload, format='json').status_code, 200)
        payload['externalAgentIds'] = [self.agent.pk]
        self.assertEqual(self.client.put(self.base + '/automation', payload, format='json').status_code, 400)

    def test_new_automation_tables_are_tenant_isolated(self):
        if connection.vendor != 'postgresql': self.skipTest('Requires PostgreSQL RLS')
        with tenant_context(self.a.pk):
            AutomationConfig.objects.create(tenant=self.a, project=self.p)
            AgentWork.objects.create(tenant=self.a, project=self.p, ticket=self.ticket)
            AutomationReply.objects.create(tenant=self.a, project=self.p, ticket=self.ticket, requested_version=1)
        with tenant_context(self.b.pk):
            self.assertFalse(AutomationConfig.objects.filter(project=self.p).exists())
            self.assertFalse(AgentWork.objects.filter(ticket=self.ticket).exists())
            self.assertFalse(AutomationReply.objects.filter(ticket=self.ticket).exists())

    def _bridge_client(self, subject='agency:one'):
        from .api_key_auth import digest
        token = 'fpsk_aabbccddeeff_' + 'b'*43
        with tenant_context(self.a.pk):
            APIKey.objects.get_or_create(prefix='aabbccddeeff', defaults={'tenant': self.a, 'project': self.p, 'user': self.agent,
                'name': 'Product', 'mode': 'customer_bridge', 'secret_hash': digest(token), 'expires_at': timezone.now()+timedelta(days=1)})
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+token, HTTP_X_SUPPORT_SUBJECT=subject)
        return client, self.base + '/customer-tickets'

    def test_product_bridge_is_subject_scoped_and_replay_hides_internal_notes(self):
        client, path = self._bridge_client()
        payload = {'title': 'Oto question', 'description': 'Details', 'sourceProduct': 'ototeklif', 'externalReference': 'local-1'}
        first = client.post(path, payload, format='json', HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(first.status_code, 201, first.data)
        with tenant_context(self.a.pk):
            Comment.objects.create(tenant=self.a, project=self.p, ticket_id=first.data['id'], author=self.agent, visibility='internal', body='hidden-product-note')
        replay = client.post(path, payload, format='json', HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertNotIn('hidden-product-note', str(replay.data))
        other, _ = self._bridge_client('agency:two')
        self.assertEqual(other.get(path).data['total'], 0)
        self.assertEqual(other.get(path+'/'+first.data['id']).status_code, 404)
        self.assertEqual(other.post(path+'/'+first.data['id']+'/comments', {'body': 'cross-subject'}, format='json', HTTP_IDEMPOTENCY_KEY='reply').status_code, 404)
        second = other.post(path, payload, format='json', HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(second.data['id'], first.data['id'])
        self.assertEqual(client.get(self.base+'/tickets').status_code, 403)
        self.assertEqual(client.get(self.base+'/work-items').status_code, 403)

    def test_product_reply_and_cancel_require_ownership_and_idempotency(self):
        client, path = self._bridge_client()
        result = client.post(path, {'title': 'Question', 'description': 'Body', 'sourceProduct': 'fphr', 'externalReference': '1'}, format='json', HTTP_IDEMPOTENCY_KEY='create')
        self.assertEqual(result.status_code, 201)
        ticket_path = path+'/'+result.data['id']
        reply = client.post(ticket_path+'/comments', {'body': 'More details'}, format='json', HTTP_IDEMPOTENCY_KEY='reply')
        self.assertEqual(reply.status_code, 201, reply.data)
        self.assertEqual(client.post(ticket_path+'/comments', {'body': 'More details'}, format='json', HTTP_IDEMPOTENCY_KEY='reply').status_code, 200)
        with tenant_context(self.a.pk):
            self.assertEqual(Comment.objects.filter(ticket_id=result.data['id'], body='More details').count(), 1)
        cancel = client.post(ticket_path+'/cancel', {}, format='json', HTTP_IDEMPOTENCY_KEY='cancel')
        self.assertEqual(cancel.status_code, 201, cancel.data)
        self.assertEqual(cancel.data['status'], 'cancelled')

    def test_product_list_can_include_bounded_public_comments(self):
        client, path = self._bridge_client()
        result = client.post(path, {'title': 'Question', 'description': 'Body', 'sourceProduct': 'fphr', 'externalReference': 'list-1'}, format='json', HTTP_IDEMPOTENCY_KEY='list')
        with tenant_context(self.a.pk):
            for i in range(7):
                Comment.objects.create(tenant=self.a, project=self.p, ticket_id=result.data['id'], author=self.agent, body=f'public-{i}')
            Comment.objects.create(tenant=self.a, project=self.p, ticket_id=result.data['id'], author=self.agent, body='LIST-SECRET', visibility='internal')
        self.assertNotIn('comments', client.get(path).data['results'][0])
        public = client.get(path+'?includeComments=1').data['results'][0]
        self.assertNotIn('LIST-SECRET', str(public))
        self.assertEqual(len(public['comments']), 5)
        self.assertTrue(public['commentsTruncated'])
        self.assertEqual(public['comments'][-1]['body'], 'public-6')

    def test_product_screenshots_use_quarantine_and_scan_queue(self):
        import base64
        image = io.BytesIO(); Image.new('RGB', (2,2)).save(image, format='PNG')
        client, path = self._bridge_client()
        with patch('portal.tasks.enqueue_scan') as scan, self.captureOnCommitCallbacks(execute=True):
            result = client.post(path, {'title': 'Screenshot', 'description': 'Body', 'sourceProduct': 'ototeklif', 'externalReference': 'image-1',
                'images': [{'mimeType': 'image/png', 'base64': base64.b64encode(image.getvalue()).decode()}]}, format='json', HTTP_IDEMPOTENCY_KEY='image')
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data['attachments'][0]['state'], 'scanning')
        scan.assert_called_once()

class SLATests(TestCase):
    def test_weekend_business_deadline(self):
        policy={'timezone':'Europe/Istanbul','start':9,'end':18,'holidays':[]}
        start=datetime(2026,10,16,14,0,tzinfo=dt_timezone.utc) # Friday 17:00 local
        due=business_due(start,120,policy)
        self.assertEqual(due.isoformat(),'2026-10-19T10:00:00+03:00')
        self.assertEqual(business_minutes_between(start,due,policy),120)

    def test_holiday_skipped(self):
        policy={'timezone':'Europe/Istanbul','start':9,'end':18,'holidays':['2026-10-19']}
        start=datetime(2026,10,16,14,0,tzinfo=dt_timezone.utc)
        self.assertEqual(business_due(start,120,policy).date().isoformat(),'2026-10-20')

class CSRFAuthTests(TestCase):
    def test_login_requires_csrf(self):
        client=APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/v1/auth/login',{'username':'x','password':'x'},format='json').status_code,403)

    def test_anonymous_ticket_endpoint_denied(self):
        client=APIClient()
        self.assertEqual(client.get(f'/api/v1/tenants/{uuid.uuid4()}/projects/{uuid.uuid4()}/tickets').status_code,401)

    def test_mfa_enrollment_and_replay_protection(self):
        import pyotp
        user=get_user_model().objects.create_user('mfa-test',password='long-password-for-mfa')
        client=APIClient();client.force_authenticate(user)
        setup=client.post('/api/v1/auth/mfa/setup',{'password':'long-password-for-mfa'},format='json')
        self.assertEqual(setup.status_code,200)
        code=pyotp.TOTP(setup.data['secret']).now()
        self.assertEqual(client.post('/api/v1/auth/mfa/verify',{'code':code},format='json').status_code,200)
        self.assertEqual(client.post('/api/v1/auth/mfa/verify',{'code':code},format='json').status_code,400)

    def test_invitation_acceptance_is_single_use(self):
        import hashlib
        token='synthetic-invitation-token-256bits'
        tenant=Tenant.objects.create(name='Invite')
        user=get_user_model().objects.create_user('inviter',password='inviter-password-123')
        with tenant_context(tenant.pk):
            project=Project.objects.create(tenant=tenant,name='Invite project',code='invite')
            Invitation.objects.create(tenant=tenant,project=project,email='invite@example.test',token_digest=hashlib.sha256(token.encode()).hexdigest(),
                                      expires_at=timezone.now()+timedelta(days=1),created_by=user)
        client=APIClient()
        payload={'token':token,'username':'joined','name':'Synthetic user','password':'a-strong-synthetic-password-123'}
        self.assertEqual(client.post('/api/v1/invitations/accept',payload,format='json').status_code,200)
        self.assertEqual(client.post('/api/v1/invitations/accept',payload,format='json').status_code,400)

    @override_settings(DEBUG=False)
    def test_production_login_is_restricted_until_mfa_enrolled(self):
        import pyotp
        get_user_model().objects.create_user('enroll',password='enrollment-password-123')
        client=APIClient()
        login=client.post('/api/v1/auth/login',{'username':'enroll','password':'enrollment-password-123'},format='json')
        self.assertEqual(login.status_code,200)
        self.assertTrue(client.get('/api/v1/session').data['enrollmentRequired'])
        self.assertEqual(client.get('/api/v1/me/tenants').status_code,403)
        setup=client.post('/api/v1/auth/mfa/setup',{'password':'enrollment-password-123'},format='json')
        code=pyotp.TOTP(setup.data['secret']).now()
        self.assertEqual(client.post('/api/v1/auth/mfa/verify',{'code':code},format='json').status_code,200)
        self.assertEqual(client.get('/api/v1/me/tenants').status_code,200)
