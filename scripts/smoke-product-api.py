"""Exercise the running central customer API with synthetic records and an in-memory key."""
import json
import os
import secrets
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

root = Path(__file__).resolve().parent.parent
for line in (root / '.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        name, value = line.split('=', 1)
        os.environ.setdefault(name, value)
sys.path.insert(0, str(root / 'apps/api'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.utils import timezone
from portal.api_key_auth import digest
from portal.models import APIKey, ProjectMembership, Comment
from portal.security import tenant_context

if not settings.DEBUG:
    raise SystemExit('Synthetic smoke test is development-only.')
member = ProjectMembership.objects.none()
# Find a project through the non-RLS tenant directory, then enter its context.
from portal.models import Tenant
tenant = Tenant.objects.get(name='FaturaPort')
with tenant_context(tenant.pk):
    member = ProjectMembership.objects.select_related('project', 'user').filter(tenant=tenant, user__username='admin').first()
    prefix = secrets.token_hex(6)
    token = f'fpsk_{prefix}_{secrets.token_urlsafe(32)}'
    key = APIKey.objects.create(tenant=tenant, project=member.project, user=member.user, name='Synthetic bridge smoke',
                               prefix=prefix, mode='customer_bridge', secret_hash=digest(token), expires_at=timezone.now()+timedelta(minutes=10))
base = f'http://127.0.0.1:8080/api/v1/tenants/{tenant.pk}/projects/{member.project_id}/customer-tickets'
subject = 'smoke:' + uuid.uuid4().hex

def call(path='', data=None, operation=None, other=False):
    headers = {'Authorization': 'Bearer ' + token, 'X-Support-Subject': subject + (':other' if other else ''), 'Content-Type': 'application/json'}
    if operation:
        headers['Idempotency-Key'] = operation
    with urlopen(Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=20) as response:
        return json.loads(response.read())

try:
    operation = str(uuid.uuid4())
    payload = {'title': 'Synthetic product bridge', 'description': 'Synthetic test only', 'sourceProduct': 'ototeklif', 'externalReference': operation}
    ticket = call(data=payload, operation=operation)
    assert call(data=payload, operation=operation)['id'] == ticket['id']
    with tenant_context(tenant.pk):
        Comment.objects.create(tenant=tenant, project=member.project, ticket_id=ticket['id'], author=member.user, body='PRIVATE-SMOKE', visibility='internal')
    detail = call('/' + ticket['id'])
    assert 'PRIVATE-SMOKE' not in json.dumps(detail)
    try:
        call('/' + ticket['id'], other=True)
        raise AssertionError('Cross-customer detail allowed')
    except HTTPError as error:
        assert error.code == 404
    replied = call('/' + ticket['id'] + '/comments', {'body': 'Synthetic customer followup'}, str(uuid.uuid4()))
    assert len(replied['comments']) == 1
    cancelled = call('/' + ticket['id'] + '/cancel', {}, str(uuid.uuid4()))
    assert cancelled['status'] == 'cancelled'
    print('PASS: running HTTP customer bridge, deduplicated create, public-only messages, cross-customer rejection, followup and cancellation')
finally:
    with tenant_context(tenant.pk):
        APIKey.objects.filter(pk=key.pk).update(revoked_at=timezone.now())
