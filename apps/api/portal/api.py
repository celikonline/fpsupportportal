import hashlib
import json
import uuid
from datetime import timedelta
from functools import wraps
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from .models import *
from .security import *

class Conflict(APIException):
    status_code = 409
    default_detail = 'Kayıt değişti. Sayfayı yenileyip tekrar deneyin.'

def exception_handler(exc, context):
    result = drf_handler(exc, context)
    if result:
        original = result.data
        result.data = {'type': 'about:blank', 'status': result.status_code, 'title': 'İşlem tamamlanamadı',
                       'detail': str(original.get('detail', original)) if isinstance(original, dict) else str(original),
                       'requestId': str(uuid.uuid4())}
        request = context.get('request')
        result.data['authenticationRequired'] = not bool(request and request.user and request.user.is_authenticated)
    return result

def scoped(project_required=True):
    def decorate(function):
        @wraps(function)
        def wrapped(request, t, p=None, **kwargs):
            tenant_member = tenant_access(request.user, t)
            with tenant_context(t, request.user.pk):
                member = project_access(request.user, t, p) if project_required else tenant_member
                return function(request, tenant_member.tenant, member, **kwargs)
        return wrapped
    return decorate

def text(data, name, limit, required=True):
    value = data.get(name, '')
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValidationError(f'{name} alanı zorunlu veya uzunluğu geçersiz.')
    return value.strip()

def user_json(user, tenant=None):
    if tenant and TenantMembership.objects.filter(tenant=tenant, user=user, anonymized=True).exists():
        return {'id': user.pk, 'name': 'Anonim kullanıcı', 'username': 'anonim'}
    return {'id': user.pk, 'name': user.get_full_name() or user.username, 'username': user.username}

def attachment_json(item):
    return {'id': str(item.pk), 'filename': item.filename, 'mimeType': item.mime_type, 'size': item.size,
            'state': item.state, 'reason': item.reason}

def project_json(project, role):
    return {'id': str(project.pk), 'name': project.name, 'code': project.code, 'role': role, 'archived': project.archived,
            'timezone': project.timezone, 'firstResponseMinutes': project.first_response_minutes,
            'resolutionMinutes': project.resolution_minutes, 'businessStart': project.business_start, 'businessEnd': project.business_end,
            'holidays': project.holidays, 'categories': project.categories}

def ticket_json(ticket, detail=False, role='requester'):
    now = timezone.now()
    result = {'id': str(ticket.pk), 'number': f'{ticket.project.code.upper()}-{ticket.number:04}', 'title': ticket.title,
              'category': ticket.category, 'priority': ticket.priority, 'status': ticket.status, 'version': ticket.version,
              'requester': user_json(ticket.requester, ticket.tenant), 'assignee': user_json(ticket.assignee, ticket.tenant) if ticket.assignee else None,
              'createdAt': ticket.created_at.isoformat(), 'updatedAt': ticket.updated_at.isoformat(), 'tags': ticket.tags,
              'firstResponseDue': ticket.first_response_due.isoformat(), 'resolutionDue': ticket.resolution_due.isoformat(),
              'legalHold': ticket.legal_hold,
              'sourceProduct': ticket.external_origin,
              'externalReference': ticket.external_reference,
              'slaRisk': (not ticket.first_response_at and now > ticket.first_response_due) or
                         (ticket.status not in {'closed', 'cancelled', 'resolved', 'waiting_requester'} and now > ticket.resolution_due)}
    if detail:
        result['description'] = ticket.description
        result['attachments'] = [attachment_json(x) for x in ticket.attachments.all() if x.state != 'deleted']
        comments = ticket.comments.select_related('author').order_by('created_at')
        if role not in STAFF_ROLES:
            comments = comments.filter(visibility='public')
        result['comments'] = [{'id': str(x.pk), 'body': x.body, 'visibility': x.visibility, 'source': x.source, 'author': user_json(x.author, ticket.tenant),
                               'createdAt': x.created_at.isoformat(), 'attachments': [attachment_json(a) for a in x.attachments.all() if a.state != 'deleted']} for x in comments]
        events = ticket.events.order_by('created_at')
        if role not in STAFF_ROLES:
            events = events.filter(visibility='public')
        result['events'] = [{'id': str(e.pk), 'action': e.action, 'detail': e.detail, 'reason':e.reason, 'createdAt': e.created_at.isoformat()} for e in events]
    return result

def event(request, ticket, action, detail='', notify=True, reason='', visibility='public'):
    TicketEvent.objects.create(tenant=ticket.tenant, project=ticket.project, ticket=ticket, actor=request.user, action=action, detail=detail, reason=reason, visibility=visibility)
    audit(request.user, ticket.tenant, ticket.project, action, ticket.pk)
    if notify:
        Outbox.objects.create(tenant=ticket.tenant, project=ticket.project, ticket=ticket, action=action)

def idempotent(request, member, operation, callback):
    key = request.headers.get('Idempotency-Key', '')
    if not key or len(key) > 128 or not key.isascii():
        raise ValidationError('Idempotency-Key gerekiyor.')
    digest = hashlib.sha256(json.dumps(request.data, sort_keys=True, default=str).encode()).hexdigest()
    # Per-membership lock serializes same-user commands and concurrent upload quotas.
    ProjectMembership.objects.select_for_update().get(pk=member.pk)
    previous = IdempotencyRecord.objects.filter(project=member.project, user=request.user, key=key, operation=operation).first()
    if previous:
        if previous.digest != digest:
            raise Conflict('Aynı işlem anahtarı farklı veriyle kullanıldı.')
        ticket_id = previous.response.get('ticketId') or previous.response.get('id')
        current = ticket_access(request.user, member.project, member.role, ticket_id)
        return Response(ticket_json(current, True, member.role))
    response = callback()
    IdempotencyRecord.objects.create(tenant=member.tenant, project=member.project, user=request.user, key=key,
                                    operation=operation, digest=digest, response={'ticketId': response['id']})
    return Response(response, status=201)

def check_version(request, ticket):
    if request.headers.get('If-Match') != f'"{ticket.version}"':
        raise Conflict()

def bind_draft(request, member, ticket, comment=None):
    draft_id = request.data.get('draftId')
    if not draft_id:
        return
    draft = Draft.objects.select_for_update().filter(id=draft_id, tenant=member.tenant, project=member.project,
                                                      owner=request.user, consumed=False, expires_at__gt=timezone.now()).first()
    if not draft or (comment and draft.ticket_id != ticket.pk) or (not comment and draft.ticket_id is not None):
        raise ValidationError('Taslak bu işleme ait değil veya süresi dolmuş.')
    if comment and draft.visibility != comment.visibility:
        raise ValidationError('Ek görünürlüğü yanıt türüyle eşleşmiyor.')
    attachments = list(draft.attachments.exclude(state__in=['deleted', 'expired']).select_for_update())
    if any(a.state != 'clean' for a in attachments):
        raise ValidationError('Dosyaların güvenlik taraması tamamlanmalı veya ekler kaldırılmalı.')
    for attachment in attachments:
        attachment.draft = None
        attachment.ticket = None if comment else ticket
        attachment.comment = comment
        attachment.save(update_fields=['draft', 'ticket', 'comment'])
    draft.consumed = True
    draft.save(update_fields=['consumed'])
