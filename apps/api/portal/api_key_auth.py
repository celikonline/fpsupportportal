"""Authentication for project API keys, isolated from DRF view imports."""

import hashlib
import hmac
import re
from datetime import timedelta

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import SAFE_METHODS

from .models import APIKey, AutomationConfig
from .security import project_access, tenant_context

TOKEN_PATTERN = re.compile(r"fpsk_([0-9a-f]{12})_([A-Za-z0-9_-]{43})\Z")
KEY_ENDPOINTS = {"tickets", "drafts", "attachments", "capabilities", "notifications", "work-items", "customer-tickets"}


def digest(token):
    return hmac.new(settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


class ProjectAPIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        try:
            header = get_authorization_header(request).decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Geçersiz Authorization başlığı.") from exc
        if not header or not header.lower().startswith("bearer "):
            return None
        parts = header.split()
        if len(parts) != 2:
            raise AuthenticationFailed("Geçersiz API anahtarı.")
        match = TOKEN_PATTERN.fullmatch(parts[1])
        if not match:
            raise AuthenticationFailed("Geçersiz API anahtarı.")

        route = request.resolver_match
        values = route.kwargs if route else {}
        tenant_id, project_id = values.get("t"), values.get("p")
        if not tenant_id or not project_id:
            raise PermissionDenied("API anahtarı yalnız proje uç noktalarında kullanılabilir.")
        root = f"/api/v1/tenants/{tenant_id}/projects/{project_id}/"
        if not request.path.startswith(root) or request.path[len(root):].split("/", 1)[0] not in KEY_ENDPOINTS:
            raise PermissionDenied("Bu uç noktada API anahtarı kullanılamaz.")

        with tenant_context(tenant_id, "api-key"):
            key = APIKey.objects.select_related("user").filter(
                tenant_id=tenant_id, project_id=project_id, prefix=match.group(1)
            ).first()
            now = timezone.now()
            if (
                not key
                or key.revoked_at
                or key.expires_at <= now
                or not key.user.is_active
                or not hmac.compare_digest(key.secret_hash, digest(parts[1]))
            ):
                raise AuthenticationFailed("API anahtarı geçersiz veya süresi dolmuş.")
            try:
                project_access(key.user, tenant_id, project_id)
            except Http404 as exc:
                raise AuthenticationFailed("API anahtarı geçersiz veya erişim kaldırılmış.") from exc
            if key.mode == "read" and request.method not in SAFE_METHODS:
                raise PermissionDenied("Bu API anahtarı salt okunur.")
            endpoint = request.path[len(root):].split('/', 1)[0]
            if key.mode == 'customer_bridge' and endpoint != 'customer-tickets':
                raise PermissionDenied('Ürün anahtarı yalnız müşteri destek köprüsünde kullanılabilir.')
            if endpoint == 'customer-tickets' and key.mode != 'customer_bridge':
                raise PermissionDenied('Ürün entegrasyon anahtarı gerekiyor.')
            config = AutomationConfig.objects.filter(tenant_id=tenant_id, project_id=project_id).first()
            if config and key.user_id in config.external_agents and request.path[len(root):].split('/', 1)[0] not in {'work-items', 'capabilities'}:
                raise PermissionDenied('Dış agent anahtarı yalnız atanan iş akışına erişebilir.')
            if not key.last_used_at or now - key.last_used_at > timedelta(minutes=5):
                APIKey.objects.filter(pk=key.pk, revoked_at__isnull=True).update(last_used_at=now)
            return key.user, key

    def authenticate_header(self, request):
        return "Bearer"
