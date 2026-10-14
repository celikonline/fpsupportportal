import hashlib
import uuid
from datetime import timedelta, date
from zoneinfo import ZoneInfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .api import *
from .files import ingest, file_path, erase_attachment, persist_blob, open_blob, remove_blob
from .sla import snapshot, business_due, business_minutes_between

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok', 'service': 'fp-support-api'})

@api_view(['GET'])
def tenants(request):
    return Response([{'id': str(m.tenant_id), 'name': m.tenant.name, 'role': m.role,
                      'retentionDays': m.tenant.retention_days, 'retentionApproved': m.tenant.retention_approved}
                     for m in TenantMembership.objects.select_related('tenant').filter(user=request.user, active=True, tenant__active=True)])

@api_view(['GET', 'POST'])
@scoped(False)
def projects(request, tenant, member):
    if request.method == 'GET':
        query = ProjectMembership.objects.filter(tenant=tenant, user=request.user, active=True).select_related('project')
        return Response([project_json(m.project, m.role) for m in query.order_by('project__name')])
    if member.role != 'admin':
        raise PermissionDenied('Tenant yöneticisi gerekiyor.')
    name, code = text(request.data, 'name', 120), text(request.data, 'code', 16)
    import re
    if not re.fullmatch('[a-z0-9-]+', code) or Project.objects.filter(tenant=tenant, code=code).exists():
        raise ValidationError('Proje kodu küçük harf, rakam ve tire içermeli; benzersiz olmalı.')
    project = Project.objects.create(tenant=tenant, name=name, code=code)
    audit(request.user, tenant, project, 'project_created', project.pk)
    # Management does not silently grant content access.
    return Response({'id': str(project.pk), 'name': name, 'code': code}, status=201)

@api_view(['GET', 'PATCH'])
@scoped()
def project_settings(request, tenant, member):
    project = member.project
    if request.method == 'PATCH':
        if member.role != 'manager':
            raise PermissionDenied('Proje yöneticisi gerekiyor.')
        if 'name' in request.data:
            project.name = text(request.data, 'name', 120)
        if 'archived' in request.data:
            if not isinstance(request.data['archived'], bool):
                raise ValidationError('Arşiv değeri geçersiz.')
            project.archived = request.data['archived']
        for field, key, maximum in [('first_response_minutes', 'firstResponseMinutes', 525600), ('resolution_minutes', 'resolutionMinutes', 525600),
                                    ('business_start', 'businessStart', 23), ('business_end', 'businessEnd', 24)]:
            if key in request.data:
                value = request.data[key]
                if not isinstance(value, int) or isinstance(value, bool) or value < (0 if key == 'businessStart' else 1) or value > maximum:
                    raise ValidationError(f'{key} geçersiz.')
                setattr(project, field, value)
        if project.business_start >= project.business_end:
            raise ValidationError('Çalışma saatleri geçersiz.')
        if 'timezone' in request.data:
            try:
                ZoneInfo(request.data['timezone'])
            except Exception:
                raise ValidationError('Saat dilimi geçersiz.')
            project.timezone = request.data['timezone']
        if 'holidays' in request.data:
            values = request.data['holidays']
            if not isinstance(values, list) or len(values) > 366:
                raise ValidationError('Tatil listesi geçersiz.')
            try:
                for value in values:
                    date.fromisoformat(value)
            except (ValueError, TypeError):
                raise ValidationError('Tatil tarihleri YYYY-MM-DD biçiminde olmalı.')
            project.holidays = values
        if 'categories' in request.data:
            values = request.data['categories']
            if not isinstance(values,list) or len(values)>30 or any(not isinstance(v,str) or not v.strip() or len(v)>64 for v in values):
                raise ValidationError('Kategori listesi geçersiz.')
            project.categories = list(dict.fromkeys(v.strip() for v in values))
        project.save()
        audit(request.user, tenant, project, 'project_settings', project.pk)
    return Response(project_json(project, member.role))

@api_view(['GET'])
@scoped()
def capabilities(request, tenant, member):
    return Response({'role': member.role, 'write': member.role != 'observer' and not member.project.archived,
                     'staff': member.role in STAFF_ROLES, 'manage': member.role == 'manager'})

@api_view(['GET', 'POST'])
@scoped()
def tickets(request, tenant, member):
    if request.method == 'GET':
        query = tickets_for(request.user, member.project, member.role)
        search = request.query_params.get('q', '')[:200]
        if search:
            query = query.filter(Q(title__icontains=search) | Q(description__icontains=search))
        for key in ['status', 'priority']:
            if value := request.query_params.get(key):
                query = query.filter(**{key: value})
        if request.query_params.get('mine') == '1':
            query = query.filter(assignee=request.user)
        total = query.count()
        stats = {'open': query.exclude(status__in=['closed', 'resolved', 'cancelled']).count(),
                 'waiting': query.filter(status='waiting_requester').count(), 'resolved': query.filter(status__in=['resolved', 'closed']).count()}
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise ValidationError('Sayfa geçersiz.')
        return Response({'results': [ticket_json(x) for x in query.order_by('-updated_at')[(page - 1) * 20:page * 20]],
                         'total': total, 'page': page, 'pageSize': 20, 'stats': stats})
    require_write(member)
    def create():
        title, description = text(request.data, 'title', 200), text(request.data, 'description', 20000)
        priority = request.data.get('priority', 'normal')
        if priority not in {'low', 'normal', 'high', 'critical'}:
            raise ValidationError('Öncelik geçersiz.')
        tags = request.data.get('tags', [])
        if not isinstance(tags,list) or len(tags)>10 or any(not isinstance(v,str) or len(v)>32 for v in tags):
            raise ValidationError('Etiketler geçersiz.')
        project = Project.objects.select_for_update().get(pk=member.project_id)
        policy, now = snapshot(project), timezone.now()
        ticket = Ticket.objects.create(tenant=tenant, project=project, number=project.next_number, title=title, description=description,
                                       category=text(request.data, 'category', 64, False) or 'Genel', priority=priority, requester=request.user, tags=tags,
                                       policy_snapshot=policy, first_response_due=business_due(now, policy['firstResponseMinutes'], policy),
                                       resolution_due=business_due(now, policy['resolutionMinutes'], policy))
        project.next_number += 1
        project.save(update_fields=['next_number'])
        bind_draft(request, member, ticket)
        event(request, ticket, 'created', 'Talep oluşturuldu')
        AgentWork.objects.create(tenant=tenant, project=project, ticket=ticket, ticket_version=ticket.version)
        from .automation import queue_customer_reply
        queue_customer_reply(ticket)
        return ticket_json(ticket, True, member.role)
    return idempotent(request, member, 'ticket.create', create)

@api_view(['GET', 'PATCH'])
@scoped()
def ticket_detail(request, tenant, member, ticket_id):
    ticket = ticket_access(request.user, member.project, member.role, ticket_id, request.method == 'PATCH')
    if request.method == 'PATCH':
        require_write(member)
        require_staff(member)
        check_version(request, ticket)
        if 'priority' in request.data:
            if request.data['priority'] not in {'low', 'normal', 'high', 'critical'}:
                raise ValidationError('Öncelik geçersiz.')
            ticket.priority = request.data['priority']
        if 'assigneeId' in request.data:
            assignee_id = request.data['assigneeId']
            if assignee_id is None:
                ticket.assignee = None
            else:
                assignment = ProjectMembership.objects.filter(project=member.project, user_id=assignee_id, role__in=STAFF_ROLES, active=True,
                                                               user__tenantmembership__tenant=tenant, user__tenantmembership__active=True).first()
                if not assignment:
                    raise ValidationError('Atanan kişi yetkili destek üyesi değil.')
                ticket.assignee_id = assignee_id
        if 'legalHold' in request.data:
            if member.role != 'manager' or not isinstance(request.data['legalHold'], bool):
                raise PermissionDenied('Hukuki muhafaza için proje yöneticisi gerekiyor.')
            fresh_mfa(request)
            ticket.legal_hold = request.data['legalHold']
        if 'tags' in request.data:
            tags = request.data['tags']
            if not isinstance(tags, list) or len(tags) > 10 or any(not isinstance(tag,str) or len(tag)>32 for tag in tags):
                raise ValidationError('Etiketler geçersiz.')
            ticket.tags = tags
        ticket.version += 1
        ticket.save()
        event(request, ticket, 'updated', 'Atama veya öncelik güncellendi')
    return Response(ticket_json(ticket, True, member.role))

@api_view(['POST'])
@scoped()
def transition(request, tenant, member, ticket_id):
    require_write(member)
    ticket = ticket_access(request.user, member.project, member.role, ticket_id, True)
    check_version(request, ticket)
    target = request.data.get('status')
    allowed = {'new': {'triaged', 'cancelled'}, 'triaged': {'in_progress', 'cancelled'},
               'in_progress': {'waiting_requester', 'waiting_internal', 'resolved', 'cancelled'},
               'waiting_requester': {'in_progress', 'resolved', 'cancelled'}, 'waiting_internal': {'in_progress', 'resolved', 'cancelled'},
               'resolved': {'in_progress', 'closed'}, 'closed': set(), 'cancelled': set()}
    if target not in allowed.get(ticket.status, set()):
        raise ValidationError('Bu durum geçişi mümkün değil.')
    reason = text(request.data, 'reason', 1000)
    if member.role not in STAFF_ROLES:
        if not (ticket.requester_id == request.user.pk and ((ticket.status == 'new' and target == 'cancelled') or
                                                          (ticket.status == 'resolved' and target in {'in_progress', 'closed'}))):
            raise PermissionDenied('Bu geçiş için destek rolü gerekiyor.')
    now = timezone.now()
    if ticket.status == 'resolved' and target == 'in_progress' and ticket.resolved_at and now - ticket.resolved_at > timedelta(days=7):
        raise ValidationError('Yeniden açma süresi doldu; yeni talep açın.')
    if target == 'waiting_requester' and not ticket.comments.filter(visibility='public', author_id=request.user.pk).exists():
        raise ValidationError('Önce müşteriye açık yanıt gönderin.')
    if ticket.waiting_since:
        paused = business_minutes_between(ticket.waiting_since, now, ticket.policy_snapshot)
        ticket.resolution_due = business_due(ticket.resolution_due, paused, ticket.policy_snapshot)
        ticket.waiting_since = None
    if target == 'waiting_requester':
        ticket.waiting_since = now
    if target == 'resolved':
        Comment.objects.create(tenant=tenant, project=member.project, ticket=ticket, author=request.user, visibility='public', body='Çözüm: ' + reason)
        ticket.resolved_at = now
    if ticket.status == 'resolved' and target == 'in_progress':
        ticket.resolved_at = None
        work = AgentWork.objects.filter(ticket=ticket).first()
        if work:
            work.state = 'review'
            work.claim_token = None
            work.lease_until = None
            work.version += 1
            work.save()
    ticket.status = target
    ticket.version += 1
    ticket.save()
    if target in {'resolved', 'closed', 'cancelled'}:
        AgentWork.objects.filter(ticket=ticket).update(state='done', claim_token=None, lease_until=None,
                                                      ticket_version=ticket.version, version=F('version')+1)
    event(request, ticket, 'status_changed', target, reason=reason, visibility='internal' if target=='waiting_internal' else 'public')
    return Response(ticket_json(ticket, True, member.role))

@api_view(['POST'])
@scoped()
def comments(request, tenant, member, ticket_id):
    require_write(member)
    def create():
        ticket = ticket_access(request.user, member.project, member.role, ticket_id, True)
        if ticket.status in {'closed', 'cancelled'}:
            raise ValidationError('Kapalı taleplere yanıt gönderilemez.')
        visibility = request.data.get('visibility', 'public')
        if visibility not in {'public', 'internal'}:
            raise ValidationError('Görünürlük geçersiz.')
        if visibility == 'internal':
            require_staff(member)
        comment = Comment.objects.create(tenant=tenant, project=member.project, ticket=ticket, author=request.user,
                                         visibility=visibility, body=text(request.data, 'body', 20000))
        bind_draft(request, member, ticket, comment)
        if visibility == 'public' and member.role in STAFF_ROLES and not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
        if visibility == 'public' and ticket.requester_id == request.user.pk and ticket.status == 'waiting_requester':
            paused = business_minutes_between(ticket.waiting_since, timezone.now(), ticket.policy_snapshot)
            ticket.resolution_due = business_due(ticket.resolution_due, paused, ticket.policy_snapshot)
            ticket.waiting_since = None
            ticket.status = 'in_progress'
        ticket.version += 1
        ticket.save()
        if visibility == 'internal':
            audit(request.user, tenant, member.project, 'internal_note_created', comment.pk)
        else:
            event(request, ticket, 'reply', 'Yeni yanıt')
            if ticket.requester_id == request.user.pk:
                from .automation import queue_customer_reply
                queue_customer_reply(ticket)
                work = AgentWork.objects.filter(ticket=ticket).first()
                if work and work.state in {'done', 'solution_review'}:
                    work.state = 'review'
                    work.claim_token = None
                    work.lease_until = None
                    work.version += 1
                    work.save()
        return ticket_json(ticket, True, member.role)
    return idempotent(request, member, f'comment.create:{ticket_id}', create)

@api_view(['POST'])
@scoped()
def drafts(request, tenant, member):
    require_write(member)
    visibility = request.data.get('visibility', 'public')
    if visibility not in {'public', 'internal'}:
        raise ValidationError('Görünürlük geçersiz.')
    if visibility == 'internal':
        require_staff(member)
    ticket = ticket_access(request.user, member.project, member.role, request.data['ticketId']) if request.data.get('ticketId') else None
    draft = Draft.objects.create(tenant=tenant, project=member.project, owner=request.user, ticket=ticket,
                                 visibility=visibility, expires_at=timezone.now() + timedelta(hours=24))
    return Response({'id': str(draft.pk)}, status=201)

@api_view(['GET', 'POST'])
@scoped()
def uploads(request, tenant, member, draft_id):
    require_write(member)
    draft = Draft.objects.filter(pk=draft_id, owner=request.user, tenant=tenant, project=member.project,
                                 consumed=False, expires_at__gt=timezone.now()).first()
    if not draft:
        raise Http404
    if draft.ticket_id:
        ticket_access(request.user, member.project, member.role, draft.ticket_id)
    if draft.visibility == 'internal':
        require_staff(member)
    if request.method == 'GET':
        return Response([attachment_json(a) for a in draft.attachments.exclude(state='deleted').order_by('created_at')])
    Draft.objects.select_for_update().get(pk=draft.pk)
    Tenant.objects.select_for_update().get(pk=tenant.pk)
    if draft.attachments.exclude(state='deleted').count() >= 10:
        raise ValidationError('En fazla 10 dosya eklenebilir.')
    upload = request.FILES.get('file')
    if not upload:
        raise ValidationError('Dosya gerekiyor.')
    if Attachment.objects.filter(tenant=tenant, owner=request.user, created_at__gt=timezone.now()-timedelta(hours=1)).count() >= 100:
        raise PermissionDenied('Saatlik yükleme sınırına ulaşıldı.')
    used = Attachment.objects.filter(tenant=tenant).exclude(state__in=['deleted', 'expired']).aggregate(total=Sum('size'))['total'] or 0
    message_size = draft.attachments.exclude(state='deleted').aggregate(total=Sum('size'))['total'] or 0
    if used + upload.size > tenant.quota_bytes or message_size + upload.size > 50 * 1024 * 1024:
        raise ValidationError('Tenant veya mesaj dosya kotası aşıldı.')
    key = str(uuid.uuid4())
    filename, mime, size, digest = ingest(upload, key)
    try:
        persist_blob(key)
        attachment = Attachment.objects.create(tenant=tenant, project=member.project, owner=request.user, draft=draft,
                                               filename=filename, mime_type=mime, size=size, sha256=digest, storage_key=key)
        from .tasks import enqueue_scan
        transaction.on_commit(lambda: enqueue_scan(tenant.pk, attachment.pk))
        audit(request.user, tenant, member.project, 'attachment_uploaded', attachment.pk)
    except Exception:
        remove_blob(key)
        raise
    return Response(attachment_json(attachment), status=201)

@api_view(['GET', 'DELETE'])
@scoped()
def attachment(request, tenant, member, attachment_id):
    item = Attachment.objects.filter(pk=attachment_id, tenant=tenant, project=member.project).select_related('comment', 'draft').first()
    if not item or item.state == 'deleted':
        raise Http404
    if item.draft_id:
        if item.owner_id != request.user.pk or item.draft.consumed or item.draft.expires_at <= timezone.now():
            raise Http404
        if item.draft.ticket_id:
            ticket_access(request.user, member.project, member.role, item.draft.ticket_id)
        if item.draft.visibility == 'internal' and member.role not in STAFF_ROLES:
            raise Http404
    else:
        ticket_access(request.user, member.project, member.role, item.ticket_id or item.comment.ticket_id)
    if item.comment_id and item.comment.visibility == 'internal' and member.role not in STAFF_ROLES:
        raise Http404
    if request.method == 'DELETE':
        require_write(member)
        if not item.draft_id:
            raise PermissionDenied('Yayımlanmış ekler yalnız imha süreciyle kaldırılabilir.')
        erase_attachment(item)
        audit(request.user, tenant, member.project, 'draft_attachment_deleted', item.pk)
        return Response({'ok': True})
    if item.state != 'clean':
        raise PermissionDenied('Dosya güvenlik taramasından geçmedi.')
    audit(request.user, tenant, member.project, 'attachment_download', item.pk)
    try:
        content = open_blob(item.storage_key)
    except FileNotFoundError:
        raise Http404
    response = FileResponse(content, as_attachment=True, filename=item.filename, content_type=item.mime_type)
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response

@api_view(['GET'])
@scoped()
def members(request, tenant, member):
    require_staff(member)
    query = ProjectMembership.objects.filter(project=member.project, active=True, user__tenantmembership__tenant=tenant,
                                              user__tenantmembership__active=True).select_related('user')
    return Response([dict(user_json(m.user,tenant), role=m.role) for m in query])

@api_view(['GET', 'POST', 'PATCH'])
@scoped(False)
def tenant_admin(request, tenant, member):
    if member.role != 'admin':
        raise PermissionDenied('Tenant yöneticisi gerekiyor.')
    if request.method == 'PATCH':
        fresh_mfa(request)
        if 'retentionDays' in request.data:
            value = request.data['retentionDays']
            if not isinstance(value, int) or value < 1 or value > 3650:
                raise ValidationError('Saklama süresi 1 ile 3650 gün arasında olmalı.')
            tenant.retention_days = value
            tenant.retention_approved = True
        tenant.save()
        audit(request.user, tenant, None, 'retention_policy', tenant.pk)
    if request.method == 'POST':
        fresh_mfa(request)
        data = request.data
        target = TenantMembership.objects.filter(tenant=tenant, user__username=data.get('username')).first()
        if not target:
            raise ValidationError('Kullanıcı önce tenant üyesi olmalı.')
        if data.get('action') == 'revoke':
            if target.user_id == request.user.pk:
                raise ValidationError('Kendi yönetici üyeliğinizi bu ekrandan iptal edemezsiniz.')
            target.active = False
            target.save(update_fields=['active'])
            ProjectMembership.objects.filter(tenant=tenant, user=target.user).update(active=False)
            audit(request.user, tenant, None, 'membership_revoked', target.user_id)
        else:
            role = data.get('role')
            project = Project.objects.filter(tenant=tenant, pk=data.get('projectId')).first()
            if role not in ROLES or not project:
                raise ValidationError('Rol veya proje geçersiz.')
            ProjectMembership.objects.update_or_create(tenant=tenant, project=project, user=target.user, defaults={'role': role, 'active': True})
            audit(request.user, tenant, project, 'role_assigned', target.user_id)
    return Response({'members': [dict(user_json(m.user,tenant), role=m.role, active=m.active) for m in TenantMembership.objects.filter(tenant=tenant).select_related('user')],
                     'projects': [{'id': str(p.pk), 'name': p.name, 'code': p.code} for p in Project.objects.filter(tenant=tenant)],
                     'retentionDays': tenant.retention_days, 'retentionApproved': tenant.retention_approved})

@api_view(['GET'])
@scoped(False)
def audit_events(request, tenant, member):
    if member.role not in {'admin', 'auditor'}:
        raise PermissionDenied('Denetim yetkisi gerekiyor.')
    query = AuditEvent.objects.filter(tenant=tenant).order_by('-created_at')[:100]
    return Response([{'id': str(a.pk), 'action': a.action, 'actorId': a.actor_id, 'targetId': a.target_id,
                      'result': a.result, 'createdAt': a.created_at.isoformat()} for a in query])

@api_view(['GET', 'POST'])
@scoped(False)
def privacy(request, tenant, member):
    if request.method == 'POST':
        kind = request.data.get('kind')
        if kind not in {'access', 'erasure', 'correction'}:
            raise ValidationError('Başvuru türü geçersiz.')
        item = PrivacyRequest.objects.create(tenant=tenant, user=request.user, kind=kind, note=text(request.data, 'note', 500, False))
        audit(request.user, tenant, None, 'privacy_requested', item.pk)
    query = PrivacyRequest.objects.filter(tenant=tenant)
    if member.role != 'admin':
        query = query.filter(user=request.user)
    return Response([{'id': str(x.pk), 'username': user_json(x.user,tenant)['username'], 'kind': x.kind, 'status': x.status, 'note': x.note,
                      'createdAt': x.created_at.isoformat()} for x in query.select_related('user').order_by('-created_at')])

@api_view(['POST'])
@scoped(False)
def privacy_action(request, tenant, member, request_id):
    if member.role != 'admin':
        raise PermissionDenied('Tenant yöneticisi gerekiyor.')
    fresh_mfa(request)
    item = PrivacyRequest.objects.select_for_update().filter(pk=request_id, tenant=tenant).first()
    if not item:
        raise Http404
    action = request.data.get('action')
    if item.status in {'completed', 'processing'}:
        raise ValidationError('Tamamlanan veya işlenen başvuru değiştirilemez.')
    if action == 'export' and item.kind == 'access':
        if not item.verified:
            raise ValidationError('Önce ilgili kişinin kimliğini inceleme akışında doğrulayın.')
        # Requesters' own tickets only; internal comments are never exported in this endpoint.
        ticket_query = Ticket.objects.filter(tenant=tenant, requester=item.user).select_related('project', 'requester', 'assignee')
        audit(request.user, tenant, None, 'privacy_export', item.pk)
        item.status = 'completed'
        item.save(update_fields=['status'])
        return Response({'user': user_json(item.user,tenant), 'tickets': [ticket_json(x, True, 'requester') for x in ticket_query]})
    if action == 'review':
        item.status = 'in_review'
        item.verified = request.data.get('identityVerified') is True
        item.review_reason = text(request.data, 'reason', 500)
    elif action == 'approve_erasure' and item.kind == 'erasure':
        if not item.verified:
            raise ValidationError('İlgili kişi kimliği inceleme sırasında doğrulanmalı.')
        item.approved_by = request.user
        item.review_reason = text(request.data, 'reason', 500)
        item.status = 'approved'
    elif action == 'execute_erasure' and item.kind == 'erasure':
        if item.status != 'approved' or item.approved_by_id == request.user.pk:
            raise ValidationError('İmha farklı bir tenant yöneticisinin onayını ve hukuki değerlendirmeyi gerektirir.')
        item.status = 'processing'
        from .tasks import erase_person
        transaction.on_commit(lambda: erase_person.delay(str(tenant.pk), str(item.pk)))
    elif action == 'reject':
        item.status = 'rejected'
    else:
        raise ValidationError('Bu başvuru için işlem geçersiz. İmha başvuruları hukuki değerlendirme sonrası işletim komutuyla tamamlanır.')
    item.save(update_fields=['status', 'verified', 'approved_by', 'review_reason'])
    audit(request.user, tenant, None, 'privacy_review', item.pk)
    return Response({'ok': True})

@api_view(['GET', 'POST'])
@scoped()
def notifications(request, tenant, member):
    query = Notification.objects.filter(tenant=tenant, project=member.project, user=request.user,
                                        ticket__in=tickets_for(request.user, member.project, member.role))
    if request.method == 'POST':
        query.update(read=True)
    return Response([{'id': str(n.pk), 'ticketId': str(n.ticket_id), 'action': n.event.action, 'read': n.read,
                      'title': n.ticket.title} for n in query.select_related('ticket', 'event').order_by('-event__created_at')[:40]])
