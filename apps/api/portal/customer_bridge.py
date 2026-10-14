"""Server-to-server product bridge; every read/write is customer-subject scoped."""
import base64
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Sum, F
from django.http import Http404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api import scoped, text, ticket_json, user_json, event, Conflict
from .api_key_auth import ProjectAPIKeyAuthentication
from .models import APIKey, Ticket, Project, ProjectMembership, IdempotencyRecord, AgentWork, Comment, Attachment, Tenant
from .automation import queue_customer_reply
from .files import ingest, persist_blob, remove_blob
from .security import require_write
from .sla import snapshot, business_due, business_minutes_between


def subject_for(request):
    if not isinstance(request.auth, APIKey) or request.auth.mode != 'customer_bridge':
        raise PermissionDenied('Sunucu ürün entegrasyon anahtarı gerekiyor.')
    subject = request.headers.get('X-Support-Subject', '')
    if not subject or not subject.isascii() or len(subject) > 200 or any(ord(c) < 33 for c in subject):
        raise ValidationError('X-Support-Subject zorunlu; ürün sunucusunda doğrulanan sabit müşteri kimliği olmalı.')
    # Stable across key rotation, isolated per service-account and project.
    return hmac.new(settings.SECRET_KEY.encode(), f'{request.auth.user_id}:{subject}'.encode(), hashlib.sha256).hexdigest()


def customer_query(request, member, subject):
    return Ticket.objects.filter(tenant=member.tenant, project=member.project, requester=request.user,
                                 external_subject=subject).select_related('project', 'requester', 'assignee')


def get_ticket(request, member, subject, ticket_id, lock=False):
    query = customer_query(request, member, subject)
    if lock:
        query = query.select_for_update(of=('self',))
    ticket = query.filter(pk=ticket_id).first()
    if not ticket:
        raise Http404
    return ticket


def customer_command(request, member, subject, operation, callback):
    key = request.headers.get('Idempotency-Key', '')
    if not key or len(key) > 128 or not key.isascii():
        raise ValidationError('Idempotency-Key gerekiyor.')
    digest = hashlib.sha256(json.dumps(request.data, sort_keys=True).encode()).hexdigest()
    ProjectMembership.objects.select_for_update().get(pk=member.pk)
    operation = f'bridge.{operation}:{subject}'
    record = IdempotencyRecord.objects.filter(project=member.project, user=request.user, key=key, operation=operation).first()
    if record:
        if record.digest != digest:
            raise Conflict('Aynı işlem anahtarı farklı veriyle kullanıldı.')
        ticket = get_ticket(request, member, subject, record.response['id'])
        return Response(ticket_json(ticket, True, 'requester'))
    ticket = callback()
    IdempotencyRecord.objects.create(tenant=member.tenant, project=member.project, user=request.user,
        key=key, operation=operation, digest=digest, response={'id': str(ticket.pk)})
    return Response(ticket_json(ticket, True, 'requester'), status=201)


def attach_images(request, ticket):
    images = request.data.get('images', [])
    if not isinstance(images, list) or len(images) > 6:
        raise ValidationError('En fazla 6 ekran görüntüsü gönderilebilir.')
    if not images:
        return
    Tenant.objects.select_for_update().get(pk=ticket.tenant_id)
    used = Attachment.objects.filter(tenant=ticket.tenant).exclude(state__in=['deleted', 'expired']).aggregate(total=Sum('size'))['total'] or 0
    stored = []
    try:
        for i, image in enumerate(images):
            if not isinstance(image, dict) or image.get('mimeType') not in {'image/png', 'image/jpeg'} or not isinstance(image.get('base64'), str) or len(image['base64']) > 4*1024*1024:
                raise ValidationError('Ekran görüntüsü biçimi geçersiz.')
            try:
                data = base64.b64decode(image['base64'], validate=True)
            except ValueError:
                raise ValidationError('Ekran görüntüsü base64 biçiminde olmalı.')
            if not 1 <= len(data) <= 3*1024*1024 or used + len(data) > ticket.tenant.quota_bytes:
                raise ValidationError('Ekran görüntüsü veya tenant kotası aşıldı.')
            used += len(data)
            extension = 'png' if image['mimeType'] == 'image/png' else 'jpg'
            key = str(uuid.uuid4())
            stored.append(key)
            name, mime, size, digest = ingest(SimpleUploadedFile(f'screenshot-{i+1}.{extension}', data), key)
            persist_blob(key)
            item = Attachment.objects.create(tenant=ticket.tenant, project=ticket.project, ticket=ticket,
                owner=request.user, filename=name, mime_type=mime, size=size, sha256=digest, storage_key=key)
            from .tasks import enqueue_scan
            transaction.on_commit(lambda item=item: enqueue_scan(ticket.tenant_id, item.pk))
    except Exception:
        for key in stored:
            remove_blob(key)
        raise


@api_view(['GET', 'POST'])
@scoped()
def tickets(request, tenant, member):
    subject = subject_for(request)
    if request.method == 'GET':
        query = customer_query(request, member, subject)
        if status := request.query_params.get('status'):
            query = query.filter(status=status)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise ValidationError('Sayfa geçersiz.')
        results = []
        for ticket in query.order_by('-updated_at', 'id')[(page-1)*20:page*20]:
            data = ticket_json(ticket)
            if request.query_params.get('includeComments') == '1':
                public = ticket.comments.filter(visibility='public').select_related('author').order_by('-created_at', '-id')
                recent = list(public[:6])
                data['commentsTruncated'] = len(recent) > 5
                data['comments'] = [{'id': str(comment.pk), 'body': comment.body, 'visibility': 'public',
                    'source': comment.source, 'createdAt': comment.created_at.isoformat(),
                    'author': user_json(comment.author, ticket.tenant)} for comment in reversed(recent[:5])]
            results.append(data)
        return Response({'results': results,
                         'total': query.count(), 'page': page, 'pageSize': 20})
    require_write(member)
    def create():
        title, description = text(request.data, 'title', 200), text(request.data, 'description', 20000)
        origin = request.data.get('sourceProduct')
        if origin not in {'ototeklif', 'fphr', 'fpfinansman'}:
            raise ValidationError('Kaynak ürün geçersiz.')
        reference = text(request.data, 'externalReference', 128)
        priority = request.data.get('priority', 'normal')
        if priority not in {'low', 'normal', 'high', 'critical'}:
            raise ValidationError('Öncelik geçersiz.')
        project = Project.objects.select_for_update().get(pk=member.project_id)
        policy, now = snapshot(project), timezone.now()
        ticket = Ticket.objects.create(tenant=tenant, project=project, number=project.next_number, title=title,
            description=description, requester=request.user, priority=priority, category=origin,
            external_subject=subject, external_origin=origin, external_reference=reference, policy_snapshot=policy,
            first_response_due=business_due(now, policy['firstResponseMinutes'], policy),
            resolution_due=business_due(now, policy['resolutionMinutes'], policy))
        project.next_number += 1
        project.save(update_fields=['next_number'])
        attach_images(request, ticket)
        AgentWork.objects.create(tenant=tenant, project=project, ticket=ticket)
        event(request, ticket, 'created', f'{origin} ürününden talep oluşturuldu')
        queue_customer_reply(ticket)
        return ticket
    return customer_command(request, member, subject, 'create', create)


@api_view(['GET'])
@scoped()
def detail(request, tenant, member, ticket_id):
    ticket = get_ticket(request, member, subject_for(request), ticket_id)
    return Response(ticket_json(ticket, True, 'requester'))


@api_view(['POST'])
@scoped()
def comments(request, tenant, member, ticket_id):
    subject = subject_for(request)
    require_write(member)
    def create():
        ticket = get_ticket(request, member, subject, ticket_id, True)
        if ticket.status in {'closed', 'cancelled', 'resolved'}:
            raise ValidationError('Aktif olmayan talebe yanıt gönderilemez.')
        Comment.objects.create(tenant=tenant, project=member.project, ticket=ticket, author=request.user,
                               visibility='public', body=text(request.data, 'body', 20000))
        if ticket.waiting_since:
            paused = business_minutes_between(ticket.waiting_since, timezone.now(), ticket.policy_snapshot)
            ticket.resolution_due = business_due(ticket.resolution_due, paused, ticket.policy_snapshot)
            ticket.waiting_since = None
            ticket.status = 'in_progress'
        ticket.version += 1
        ticket.save()
        event(request, ticket, 'reply', 'Ürün müşterisi yanıtladı')
        queue_customer_reply(ticket)
        return ticket
    return customer_command(request, member, subject, f'comment:{ticket_id}', create)


@api_view(['POST'])
@scoped()
def cancel(request, tenant, member, ticket_id):
    subject = subject_for(request)
    require_write(member)
    def create():
        ticket = get_ticket(request, member, subject, ticket_id, True)
        if ticket.status == 'cancelled':
            return ticket
        if ticket.status not in {'new', 'triaged'}:
            raise Conflict('Çalışılmaya başlanmış talep iptal edilemez.')
        ticket.status = 'cancelled'
        ticket.version += 1
        ticket.save()
        AgentWork.objects.filter(ticket=ticket).update(state='done', claim_token=None, lease_until=None, version=F('version')+1)
        event(request, ticket, 'status_changed', 'cancelled', reason='Ürün müşterisi iptal etti')
        return ticket
    return customer_command(request, member, subject, f'cancel:{ticket_id}', create)
