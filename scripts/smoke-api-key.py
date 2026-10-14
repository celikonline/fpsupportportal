"""Exercise live key issuance, scoped Bearer access and revocation with synthetic data."""

import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pyotp

root = Path(__file__).resolve().parent.parent
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        name, value = line.split('=', 1)
        os.environ[name] = value
sys.path.insert(0, str(root / 'apps' / 'api'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from portal.models import APIKey, Project, ProjectMembership, Tenant, TenantMembership
from portal.security import tenant_context

base = os.environ.get('FP_SUPPORT_API_BASE', 'http://127.0.0.1:8080/api/v1/').rstrip('/') + '/'


def call(opener, path, method='GET', data=None, headers=None):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={'Content-Type': 'application/json', **(headers or {})},
    )
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


user = None
tenant = Tenant.objects.get(name='FaturaPort')
with tenant_context(tenant.pk):
    project = Project.objects.get(tenant=tenant, code='fp')
password = secrets.token_urlsafe(24)
username = 'key-smoke-' + secrets.token_hex(6)
try:
    user = get_user_model().objects.create_user(username=username, password=password)
    TenantMembership.objects.create(tenant=tenant, user=user)
    with tenant_context(tenant.pk):
        ProjectMembership.objects.create(tenant=tenant, project=project, user=user, role='requester')

    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    status, session = call(browser, 'session')
    assert status == 200
    csrf = {'X-CSRFToken': session['csrfToken']}
    status, login = call(browser, 'auth/login', 'POST', {'username': username, 'password': password}, csrf)
    assert status == 200
    csrf = {'X-CSRFToken': login['csrfToken']}
    status, setup = call(browser, 'auth/mfa/setup', 'POST', {'password': password}, csrf)
    assert status == 200
    status, _ = call(browser, 'auth/mfa/verify', 'POST', {'code': pyotp.TOTP(setup['secret']).now()}, csrf)
    assert status == 200
    scope = f'tenants/{tenant.pk}/projects/{project.pk}'
    status, created = call(browser, scope + '/api-keys', 'POST',
                           {'name': 'Sentetik entegrasyon', 'mode': 'read', 'expiresInDays': 1}, csrf)
    assert status == 201
    token = created['key']
    status, listed = call(browser, scope + '/api-keys')
    assert status == 200 and token not in json.dumps(listed) and listed['activeCount'] == 1

    service = urllib.request.build_opener()
    auth = {'Authorization': 'Bearer ' + token}
    status, _ = call(service, scope + '/tickets', headers=auth)
    assert status == 200
    status, _ = call(service, scope + '/tickets', 'POST', {'title': 'Should fail'}, auth)
    assert status == 403
    status, _ = call(service, scope + '/api-keys', headers=auth)
    assert status == 403
    status, _ = call(browser, scope + '/api-keys/' + created['id'], 'DELETE', headers=csrf)
    assert status == 200
    status, _ = call(service, scope + '/tickets', headers=auth)
    assert status == 401
    print('PASS: live MFA issuance, one-time secret, project Bearer read, write/management denial, revocation.')
finally:
    if user is not None:
        with tenant_context(tenant.pk):
            APIKey.objects.filter(tenant=tenant, user=user).delete()
            ProjectMembership.objects.filter(tenant=tenant, user=user).delete()
            TenantMembership.objects.filter(tenant=tenant, user=user).delete()
            user.delete()
