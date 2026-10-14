"""PO routing and leased, project-scoped work for external MCP workers."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import Http404, FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api import scoped, text, ticket_json, event, Conflict
from .models import AutomationConfig, AutomationReply, AgentWork, ProjectMembership, Comment, Ticket, Attachment
from .security import require_staff, require_write, ticket_access, fresh_mfa, audit, STAFF_ROLES
from .sla import business_minutes_between, business_due

TERMINAL = {'closed', 'cancelled', 'resolved'}


def config_for(member):
    return AutomationConfig.objects.filter(project=member.project, tenant=member.tenant).first()


def require_po(request, member):
    config = config_for(member)
    if request.auth or member.role not in {'manager', 'lead'} or (config and (
        request.user.pk == config.bot_id or request.user.pk in config.external_agents
    )):
        raise PermissionDenied('PO işlemleri için proje yöneticisi veya destek lideri gerekiyor.')


def staff_assignment(tenant, project, user_id):
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        raise ValidationError('Destek üyesi geçersiz.')
    assignment = ProjectMembership.objects.select_related('user').filter(
        tenant=tenant, project=project, user_id=user_id, active=True, role__in=STAFF_ROLES,
        user__is_active=True, user__tenantmembership__tenant=tenant,
        user__tenantmembership__active=True,
    ).first()
    if not assignment:
        raise ValidationError('Etkin bir destek üyesi seçin.')
    return assignment


def work_json(work, detail=False):
    data = {'id': str(work.pk), 'ticketId': str(work.ticket_id), 'state': work.state,
            'version': work.version, 'ticketVersion': work.ticket_version,
            'assigneeId': work.assignee_id, 'reason': work.reason, 'solution': work.solution,
            'leaseUntil': work.lease_until.isoformat() if work.lease_until else None,
            'updatedAt': work.updated_at.isoformat()}
    data['ticket'] = ticket_json(work.ticket, detail, 'agent')
    return data


def queue_customer_reply(ticket):
    """Called inside the same ticket transaction; beat recovers broker failures."""
    config = AutomationConfig.objects.filter(project=ticket.project, enabled=True).first()
    if not config or ticket.status in TERMINAL or ticket.requester_id == config.bot_id:
        return
    job, _ = AutomationReply.objects.get_or_create(
        tenant=ticket.tenant, project=ticket.project, ticket=ticket,
        defaults={'requested_version': ticket.version},
    )
    job.requested_version = ticket.version
    job.attempts = 0
    job.error = ''
    job.retry_at = None
    job.save(update_fields=['requested_version', 'attempts', 'error', 'retry_at'])
    transaction.on_commit(lambda: enqueue_reply(str(ticket.tenant_id), str(ticket.pk)))


def enqueue_reply(tenant_id, ticket_id):
    import logging
    from .automation_tasks import customer_reply
    try:
        customer_reply.delay(tenant_id, ticket_id)
    except Exception:
        logging.getLogger(__name__).warning('Customer reply queue unavailable; beat will recover')


@api_view(['GET', 'PUT'])
@scoped()
def automation_settings(request, tenant, member):
    require_po(request, member)
    config = config_for(member)
    if request.method == 'PUT':
        require_write(member)
        fresh_mfa(request)
        enabled = request.data.get('enabled', False)
        if not isinstance(enabled, bool):
            raise ValidationError('enabled boolean olmalı.')
        bot_id = request.data.get('botId')
        external = request.data.get('externalAgentIds', [])
        if not isinstance(external, list) or len(external) > 20:
            raise ValidationError('Dış agent listesi geçersiz.')
        for user_id in external:
            staff_assignment(tenant, member.project, user_id)
        if bot_id is not None:
            staff_assignment(tenant, member.project, bot_id)
        if bot_id in external or request.user.pk == bot_id or request.user.pk in external:
            raise ValidationError('PO, müşteri agentı ve dış agentlar ayrı hesaplar olmalı.')
        if enabled and (bot_id is None or not settings.AI_MODEL or not settings.AI_API_URL or not settings.AI_API_KEY):
            raise ValidationError('Önce model API ayarlarını ve müşteri agentı hesabını yapılandırın.')
        config, _ = AutomationConfig.objects.update_or_create(
            tenant=tenant, project=member.project,
            defaults={'enabled': enabled, 'bot_id': bot_id, 'external_agents': list(dict.fromkeys(external)),
                      'instructions': text(request.data, 'instructions', 8000, False)},
        )
        audit(request.user, tenant, member.project, 'automation_configured', member.project_id)
    return Response({'enabled': config.enabled if config else False, 'botId': config.bot_id if config else None,
                     'externalAgentIds': config.external_agents if config else [],
                     'instructions': config.instructions if config else '',
                     'modelReady': bool(settings.AI_MODEL and settings.AI_API_URL and settings.AI_API_KEY),
                     'model': settings.AI_MODEL,
                     'replyErrors': [{'ticketId': str(job.ticket_id), 'error': job.error, 'attempts': job.attempts}
                                     for job in AutomationReply.objects.filter(project=member.project).exclude(error='')[:20]]})


@api_view(['POST'])
@scoped()
def retry_reply(request, tenant, member, ticket_id):
    require_po(request, member)
    require_write(member)
    ticket = ticket_access(request.user, member.project, member.role, ticket_id, True)
    job = AutomationReply.objects.filter(ticket=ticket).first()
    config = config_for(member)
    if not config or not config.enabled or not job or not job.error or ticket.status in TERMINAL:
        raise ValidationError('Yeniden denenecek etkin yanıt işi bulunamadı.')
    queue_customer_reply(ticket)
    audit(request.user, tenant, member.project, 'ai_reply_retry', ticket.pk)
    return Response({'status': 'queued'})


@api_view(['GET'])
@scoped()
def work_items(request, tenant, member):
    require_staff(member)
    query = AgentWork.objects.filter(tenant=tenant, project=member.project).select_related('ticket__project', 'ticket__requester', 'ticket__assignee')
    config = config_for(member)
    if member.role not in {'manager', 'lead'} or request.auth or (config and (request.user.pk in config.external_agents or request.user.pk == config.bot_id)):
        query = query.filter(assignee=request.user)
    if state := request.query_params.get('state'):
        query = query.filter(state=state)
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except ValueError:
        raise ValidationError('Sayfa geçersiz.')
    return Response({'results': [work_json(w) for w in query.order_by('updated_at', 'id')[(page-1)*20:page*20]],
                     'total': query.count(), 'page': page, 'pageSize': 20})


@api_view(['GET', 'POST'])
@scoped()
def work_detail(request, tenant, member, ticket_id):
    require_staff(member)
    ticket = ticket_access(request.user, member.project, member.role, ticket_id, request.method == 'POST')
    work = AgentWork.objects.filter(tenant=tenant, project=member.project, ticket=ticket).first()
    if request.method == 'GET':
        if not work:
            raise Http404
        config = config_for(member)
        if (member.role not in {'manager', 'lead'} or request.auth or (config and (request.user.pk in config.external_agents or request.user.pk == config.bot_id))) and work.assignee_id != request.user.pk:
            raise Http404
        return Response(work_json(work, True))
    require_write(member)
    require_po(request, member)
    if ticket.status in TERMINAL:
        raise ValidationError('Bu talep aktif değil.')
    if request.data.get('ticketVersion') != ticket.version or request.data.get('version') != (work.version if work else 0):
        raise Conflict()
    action = request.data.get('action')
    reason = text(request.data, 'reason', 4000)
    if action in {'external', 'human'}:
        assignee = staff_assignment(tenant, member.project, request.data.get('assigneeId'))
        config = config_for(member)
        external = config.external_agents if config else []
        if action == 'external' and assignee.user_id not in external:
            raise ValidationError('Seçilen hesap dış agent olarak tanımlı değil.')
        if action == 'human' and (assignee.user_id in external or (config and assignee.user_id == config.bot_id)):
            raise ValidationError('İnsan destek üyesi seçin.')
        if not work:
            work = AgentWork(tenant=tenant, project=member.project, ticket=ticket, version=0)
        work.state = 'queued' if action == 'external' else 'human'
        work.assignee = assignee.user
        work.reason = reason
        work.solution = ''
        work.claim_token = None
        work.lease_until = None
        ticket.assignee = assignee.user
        if ticket.status == 'new':
            ticket.status = 'triaged'
    elif action == 'approve':
        if not work or work.state != 'solution_review' or work.ticket_version != ticket.version:
            raise Conflict('Onaylanacak güncel çözüm bulunamadı.')
        Comment.objects.create(tenant=tenant, project=member.project, ticket=ticket,
                               author=request.user, body=work.solution, source='external_agent')
        ticket.status = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.first_response_at = ticket.first_response_at or timezone.now()
        work.state = 'done'
    else:
        raise ValidationError('Geçersiz PO işlemi.')
    if ticket.waiting_since:
        paused = business_minutes_between(ticket.waiting_since, timezone.now(), ticket.policy_snapshot)
        ticket.resolution_due = business_due(ticket.resolution_due, paused, ticket.policy_snapshot)
        ticket.waiting_since = None
    ticket.version += 1
    ticket.save()
    work.ticket_version = ticket.version
    work.version += 1
    work.save()
    event(request, ticket, 'po_' + action, 'PO değerlendirmesi', reason=reason,
          visibility='public' if action == 'approve' else 'internal')
    return Response(work_json(work, True))


def external_work(request, tenant, member, work_id):
    require_staff(member)
    require_write(member)
    config = config_for(member)
    if not config or request.user.pk not in config.external_agents:
        raise PermissionDenied('Dış agent hesabı gerekiyor.')
    # Always lock ticket before work, matching the PO and comment lock order.
    lookup = AgentWork.objects.filter(pk=work_id, tenant=tenant, project=member.project, assignee=request.user).first()
    if not lookup:
        raise Http404
    ticket = ticket_access(request.user, member.project, member.role, lookup.ticket_id, True)
    work = AgentWork.objects.select_for_update().get(pk=lookup.pk)
    if work.assignee_id != request.user.pk:
        raise Http404
    if ticket.status in TERMINAL:
        raise Conflict('Talep artık aktif değil.')
    return work, ticket


@api_view(['POST'])
@scoped()
def claim_work(request, tenant, member, work_id):
    work, ticket = external_work(request, tenant, member, work_id)
    now = timezone.now()
    if work.state != 'queued' and not (work.state == 'claimed' and work.lease_until <= now):
        raise Conflict('İş başka bir oturumda çalışılıyor veya kuyrukta değil.')
    if request.data.get('version') != work.version:
        raise Conflict()
    if work.ticket_version != ticket.version:
        raise Conflict('Talep değişti; PO işi yeniden değerlendirmeli.')
    work.state = 'claimed'
    work.claim_token = uuid.uuid4()
    work.lease_until = now + timedelta(minutes=15)
    ticket.status = 'in_progress'
    ticket.version += 1
    ticket.save()
    work.ticket_version = ticket.version
    work.version += 1
    work.save()
    event(request, ticket, 'agent_claimed', 'Dış agent işi aldı', visibility='internal', notify=False)
    return Response({**work_json(work, True), 'claimToken': str(work.claim_token)})


@api_view(['POST'])
@scoped()
def update_work(request, tenant, member, work_id):
    work, ticket = external_work(request, tenant, member, work_id)
    token = request.data.get('claimToken')
    if not work.claim_token or token != str(work.claim_token):
        raise Conflict('İş sahipliği geçersiz.')
    action = request.data.get('action')
    if action == 'submit' and work.state == 'solution_review':
        if text(request.data, 'solution', 20000) != work.solution:
            raise Conflict('Bu sahiplik anahtarı farklı çözümle kullanıldı.')
        return Response(work_json(work, True))
    if work.state != 'claimed' or work.lease_until <= timezone.now():
        raise Conflict('İş sahipliği sona erdi; işi yeniden alın.')
    if work.ticket_version != ticket.version:
        raise Conflict('Talep değişti; PO işi yeniden değerlendirmeli.')
    if action == 'heartbeat':
        work.lease_until = timezone.now() + timedelta(minutes=15)
    elif action in {'submit', 'release'}:
        if action == 'submit':
            work.solution = text(request.data, 'solution', 20000)
            work.state = 'solution_review'
        else:
            work.reason = text(request.data, 'reason', 4000)
            work.state = 'review'
            work.claim_token = None
        work.lease_until = None
        event(request, ticket, 'agent_' + action, 'Dış agent sonucu PO değerlendirmesinde',
              visibility='internal', notify=False)
    else:
        raise ValidationError('Geçersiz iş işlemi.')
    work.version += 1
    work.save()
    return Response(work_json(work, True))


@api_view(['GET'])
@scoped()
def work_attachment(request, tenant, member, work_id, attachment_id):
    require_staff(member)
    config = config_for(member)
    work = AgentWork.objects.filter(pk=work_id, tenant=tenant, project=member.project, assignee=request.user).first()
    if not config or request.user.pk not in config.external_agents or not work:
        raise Http404
    item = Attachment.objects.filter(pk=attachment_id, tenant=tenant, project=member.project).filter(
        Q(ticket_id=work.ticket_id) | Q(comment__ticket_id=work.ticket_id)).first()
    if not item:
        raise Http404
    if item.state != 'clean':
        raise PermissionDenied('Dosya güvenlik taramasından geçmedi.')
    from .files import open_blob
    try:
        content = open_blob(item.storage_key)
    except FileNotFoundError:
        raise Http404
    audit(request.user, tenant, member.project, 'agent_attachment_download', item.pk)
    response = FileResponse(content, as_attachment=True, filename=item.filename, content_type=item.mime_type)
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response
