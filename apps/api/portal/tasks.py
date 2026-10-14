import hashlib
import logging
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.db.models import Q, Sum, F
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Tenant, Attachment, Draft, Outbox, Notification, ProjectMembership, Ticket, TicketEvent
from .security import tenant_context, tickets_for, STAFF_ROLES
from .files import antivirus, sanitize_image, file_path, erase_attachment, hydrate_blob, persist_blob, remove_blob, cleanup_quarantine

logger = logging.getLogger(__name__)

# Celery autodiscovery imports portal.tasks; register automation tasks as well.
from .automation_tasks import customer_reply, recover_customer_replies

def enqueue_scan(tenant_id, attachment_id):
    try:
        scan_attachment.delay(str(tenant_id), str(attachment_id))
    except Exception:
        # Persisted scanning rows are recovered by maintenance after broker restart.
        logger.warning('Scan queue unavailable; maintenance will retry')

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def scan_attachment(self, tenant_id, attachment_id):
    with tenant_context(tenant_id):
        item = Attachment.objects.select_for_update().filter(pk=attachment_id, tenant_id=tenant_id, state='scanning').first()
        if not item:
            return
        try:
            path = hydrate_blob(item.storage_key)
            antivirus(path)
            sanitize_image(path, item.mime_type)
            antivirus(path)
            size = path.stat().st_size
            limit = 10*1024*1024 if item.mime_type.startswith('image/') else 20*1024*1024
            tenant = Tenant.objects.select_for_update().get(pk=tenant_id)
            used = Attachment.objects.filter(tenant=tenant).exclude(state__in=['deleted','expired']).aggregate(total=Sum('size'))['total'] or 0
            if size > limit or used-item.size+size > tenant.quota_bytes:
                raise ValidationError('Temiz dosya boyutu veya tenant kotası aşıldı.')
            if item.draft_id:
                message_size = Attachment.objects.filter(draft_id=item.draft_id).exclude(state='deleted').aggregate(total=Sum('size'))['total'] or 0
                if message_size-item.size+size > 50*1024*1024:
                    raise ValidationError('Temiz mesaj eklerinin boyutu aşıldı.')
            item.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            item.size = size
            persist_blob(item.storage_key, clean=True)
            item.state = 'clean'
            item.reason = ''
        except ValidationError:
            item.state = 'rejected'
            item.reason = 'Dosya güvenlik kontrolünden geçmedi.'
            remove_blob(item.storage_key)
        except (OSError, ValueError):
            item.reason = 'Tarama servisi bekleniyor. Dosya erişime kapalı.'
            item.save(update_fields=['reason'])
            return  # maintenance retries; no fail-open or committed clean verdict
        item.save(update_fields=['state', 'reason', 'sha256', 'size'])
        if item.state == 'clean':
            transaction.on_commit(lambda: cleanup_quarantine(item.storage_key))

@shared_task
def dispatch_outbox():
    for tenant in Tenant.objects.filter(active=True).iterator():
        with tenant_context(tenant.pk):
            for outbox in Outbox.objects.filter(tenant=tenant, delivered=False).select_related('ticket', 'project')[:100]:
                recipients = ProjectMembership.objects.filter(tenant=tenant, project=outbox.project, active=True,
                                                              user__tenantmembership__tenant=tenant, user__tenantmembership__active=True).select_related('user')
                for member in recipients:
                    if tickets_for(member.user, member.project, member.role).filter(pk=outbox.ticket_id).exists():
                        Notification.objects.get_or_create(tenant=tenant, project=outbox.project, user=member.user,
                                                           ticket=outbox.ticket, event=outbox)
                outbox.delivered = True
                outbox.save(update_fields=['delivered'])
            for notification in Notification.objects.filter(tenant=tenant, emailed=False).select_related('user', 'ticket', 'project', 'event')[:100]:
                membership = ProjectMembership.objects.filter(project=notification.project, user=notification.user, active=True,
                                                               user__tenantmembership__tenant=tenant, user__tenantmembership__active=True).first()
                if not membership or not tickets_for(notification.user, notification.project, membership.role).filter(pk=notification.ticket_id).exists():
                    notification.delete()
                    continue
                if notification.user.email:
                    try:
                        # No ticket body, title, attachment name, or internal notes in email.
                        send_mail('Destek portalında güncelleme', 'Yetkili olduğunuz bir destek talebi güncellendi. Ayrıntılar için destek portalına giriş yapın.',
                                  None, [notification.user.email], fail_silently=False)
                    except Exception:
                        logger.warning('Notification delivery failed; will retry')
                        continue
                notification.emailed = True
                notification.save(update_fields=['emailed'])

@shared_task
def maintenance():
    for tenant in Tenant.objects.filter(active=True).iterator():
        with tenant_context(tenant.pk):
            from .models import PrivacyRequest
            for request_id in PrivacyRequest.objects.filter(tenant=tenant, status='processing', kind='erasure').values_list('id', flat=True)[:20]:
                erase_person.delay(str(tenant.pk), str(request_id))
            for item in Attachment.objects.filter(tenant=tenant, state='scanning')[:100]:
                enqueue_scan(tenant.pk, item.pk)
            for draft in Draft.objects.filter(tenant=tenant, expires_at__lt=timezone.now(), consumed=False)[:100]:
                for item in draft.attachments.exclude(state='deleted'):
                    erase_attachment(item)
                draft.consumed = True
                draft.save(update_fields=['consumed'])
            for ticket in Ticket.objects.filter(tenant=tenant, status='resolved', resolved_at__lt=timezone.now() - timedelta(days=7)).select_for_update()[:100]:
                ticket.status = 'closed'
                ticket.version += 1
                ticket.save()
                TicketEvent.objects.create(tenant=tenant, project=ticket.project, ticket=ticket, action='auto_closed', detail='7 günlük onay süresi tamamlandı')
                Outbox.objects.create(tenant=tenant, project=ticket.project, ticket=ticket, action='closed')
            now = timezone.now()
            late = Ticket.objects.filter(tenant=tenant).exclude(status__in=['resolved','closed','cancelled']).filter(
                Q(first_response_at__isnull=True, first_response_due__lt=now) | Q(resolution_due__lt=now, waiting_since__isnull=True)).select_for_update()[:100]
            for ticket in late:
                if not TicketEvent.objects.filter(ticket=ticket, action='sla_breach').exists():
                    TicketEvent.objects.create(tenant=tenant,project=ticket.project,ticket=ticket,action='sla_breach',detail='SLA hedefi aşıldı')
                    Outbox.objects.create(tenant=tenant,project=ticket.project,ticket=ticket,action='sla_breach')

@shared_task
def erase_person(tenant_id, request_id):
    from .models import PrivacyRequest, Comment, TenantMembership, IdempotencyRecord, APIKey
    from .security import audit
    with tenant_context(tenant_id):
        item = PrivacyRequest.objects.select_for_update().filter(pk=request_id, tenant_id=tenant_id, status='processing', kind='erasure').first()
        if not item:
            return
        user = item.user
        if Ticket.objects.filter(tenant_id=tenant_id, legal_hold=True).filter(Q(requester=user)|Q(comments__author=user)|Q(attachments__owner=user)|Q(events__actor=user)).exists():
            item.status = 'in_review'
            item.review_reason = 'Hukuki muhafaza kapsamındaki kayıtlar bulundu. İmha durduruldu.'
            item.save(update_fields=['status', 'review_reason'])
            audit('system', item.tenant, None, 'privacy_hold', item.pk)
            return
        for attachment in Attachment.objects.filter(tenant_id=tenant_id).filter(Q(owner=user) | Q(ticket__requester=user) | Q(comment__ticket__requester=user)):
            erase_attachment(attachment)
        own = Ticket.objects.filter(tenant_id=tenant_id, requester=user)
        from .models import AgentWork, AutomationReply, AutomationConfig
        AgentWork.objects.filter(tenant_id=tenant_id).filter(Q(ticket__in=own) | Q(assignee=user)).update(solution='', reason='', claim_token=None, lease_until=None, state='review')
        AutomationReply.objects.filter(tenant_id=tenant_id, ticket__in=own).delete()
        AutomationConfig.objects.filter(tenant_id=tenant_id, bot=user).update(enabled=False, bot=None)
        Comment.objects.filter(tenant_id=tenant_id, ticket__in=own).update(body='[İmha edildi]')
        Comment.objects.filter(tenant_id=tenant_id, author=user).update(body='[İmha edildi]')
        TicketEvent.objects.filter(tenant_id=tenant_id).filter(Q(ticket__in=own)|Q(actor=user)).update(detail='',reason='')
        own.update(title='[İmha edilmiş talep]', description='[İmha edildi]', category='Genel', tags=[], external_subject='', external_reference='', version=F('version')+1)
        IdempotencyRecord.objects.filter(tenant_id=tenant_id, user=user).delete()
        APIKey.objects.filter(tenant_id=tenant_id, user=user).delete()
        Notification.objects.filter(tenant_id=tenant_id, user=user).delete()
        TenantMembership.objects.filter(tenant_id=tenant_id, user=user).update(anonymized=True, active=False)
        ProjectMembership.objects.filter(tenant_id=tenant_id, user=user).update(active=False)
        item.status = 'completed'
        item.note = ''
        item.save(update_fields=['status', 'note'])
        audit('system', item.tenant, None, 'privacy_erased', item.pk)
