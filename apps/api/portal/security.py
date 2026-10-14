import base64
import hashlib
import os
from contextlib import contextmanager
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import connection, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from .models import Tenant, TenantMembership, Project, ProjectMembership, Ticket, AuditEvent

STAFF_ROLES = {'manager', 'lead', 'agent'}
ROLES = STAFF_ROLES | {'requester', 'observer'}

def cipher():
    key = os.environ.get('FIELD_ENCRYPTION_KEY')
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)

@contextmanager
def tenant_context(tenant_id, user_id='system'):
    with transaction.atomic():
        previous = None
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.tenant_id', true), current_setting('app.user_id', true)")
                previous = cursor.fetchone()
                cursor.execute("SELECT set_config('app.tenant_id', %s, true), set_config('app.user_id', %s, true)", [str(tenant_id), str(user_id)])
        try:
            with transaction.atomic():
                yield
        finally:
            if previous is not None and not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, true), set_config('app.user_id', %s, true)", [previous[0] or '', previous[1] or ''])

def tenant_access(user, tenant_id):
    try:
        member = TenantMembership.objects.select_related('tenant').get(tenant_id=tenant_id, user=user, active=True, tenant__active=True)
    except (TenantMembership.DoesNotExist, ValueError):
        raise Http404
    return member

def project_access(user, tenant_id, project_id):
    tenant_access(user, tenant_id)
    try:
        return ProjectMembership.objects.select_related('project').get(tenant_id=tenant_id, project_id=project_id, user=user,
                                                                       active=True, project__tenant_id=tenant_id)
    except (ProjectMembership.DoesNotExist, ValueError):
        raise Http404

def tickets_for(user, project, role):
    query = Ticket.objects.filter(tenant_id=project.tenant_id, project=project).select_related('requester', 'assignee', 'project')
    return query if role in STAFF_ROLES | {'observer'} else query.filter(requester=user)

def ticket_access(user, project, role, ticket_id, lock=False):
    query = tickets_for(user, project, role)
    if lock:
        query = query.select_for_update(of=('self',))
    try:
        return query.get(id=ticket_id)
    except (Ticket.DoesNotExist, ValueError):
        raise Http404

def require_staff(member):
    if member.role not in STAFF_ROLES:
        raise PermissionDenied('Bu işlem için destek rolü gerekiyor.')

def require_write(member):
    if member.role == 'observer' or member.project.archived:
        raise PermissionDenied('Bu proje salt okunur.')

def audit(user, tenant, project, action, target='', result='success'):
    return AuditEvent.objects.create(actor_id=str(getattr(user, 'pk', user)), tenant=tenant, project=project,
                                     action=action, target_id=str(target), result=result)

def fresh_mfa(request):
    stamp = request.session.get('mfa_at', 0)
    if timezone.now().timestamp() - stamp > 600:
        raise PermissionDenied('Bu işlem için son 10 dakika içinde MFA doğrulaması gerekiyor.')
