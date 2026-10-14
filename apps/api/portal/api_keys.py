"""Project-scoped personal API keys. Raw credentials are never persisted."""

import secrets
from datetime import timedelta

from django.http import Http404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api import scoped
from .api_key_auth import digest
from .models import APIKey, ProjectMembership
from .security import audit, fresh_mfa


def key_json(item):
    return {
        "id": str(item.pk),
        "name": item.name,
        "prefix": f"fpsk_{item.prefix}",
        "mode": item.mode,
        "createdAt": item.created_at.isoformat(),
        "expiresAt": item.expires_at.isoformat(),
        "lastUsedAt": item.last_used_at.isoformat() if item.last_used_at else None,
        "revokedAt": item.revoked_at.isoformat() if item.revoked_at else None,
    }


@api_view(["GET", "POST"])
@scoped()
def api_keys(request, tenant, member):
    query = APIKey.objects.filter(tenant=tenant, project=member.project, user=request.user)
    if request.method == "GET":
        active_count = query.filter(revoked_at__isnull=True, expires_at__gt=timezone.now()).count()
        return Response({"items": [key_json(item) for item in query.order_by("-created_at")[:100]],
                         "activeCount": active_count})

    fresh_mfa(request)
    name = request.data.get("name")
    mode = request.data.get("mode")
    days = request.data.get("expiresInDays")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValidationError("Anahtar adı 1-80 karakter olmalı.")
    if mode not in {"read", "read_write", "customer_bridge"}:
        raise ValidationError("Erişim türü geçersiz.")
    if mode in {"read_write", "customer_bridge"} and (member.role == "observer" or member.project.archived):
        raise PermissionDenied("Bu projede yazma yetkiniz yok.")
    if mode == 'customer_bridge' and member.role != 'manager':
        raise PermissionDenied('Ürün entegrasyon anahtarı için proje yöneticisi gerekiyor.')
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 365:
        raise ValidationError("Geçerlilik süresi 1-365 gün olmalı.")
    ProjectMembership.objects.select_for_update().get(pk=member.pk)
    if query.filter(revoked_at__isnull=True, expires_at__gt=timezone.now()).count() >= 10:
        raise ValidationError("Bir projede en fazla 10 etkin anahtar bulunabilir.")
    prefix = secrets.token_hex(6)
    token = f"fpsk_{prefix}_{secrets.token_urlsafe(32)}"
    item = APIKey.objects.create(
        tenant=tenant,
        project=member.project,
        user=request.user,
        name=name.strip(),
        prefix=prefix,
        secret_hash=digest(token),
        mode=mode,
        expires_at=timezone.now() + timedelta(days=days),
    )
    audit(request.user, tenant, member.project, "api_key_created", item.pk)
    return Response({**key_json(item), "key": token}, status=201)


@api_view(["DELETE"])
@scoped()
def api_key_detail(request, tenant, member, key_id):
    fresh_mfa(request)
    item = APIKey.objects.select_for_update().filter(
        pk=key_id, tenant=tenant, project=member.project, user=request.user
    ).first()
    if not item:
        raise Http404
    if item.revoked_at is None:
        item.revoked_at = timezone.now()
        item.save(update_fields=["revoked_at"])
        audit(request.user, tenant, member.project, "api_key_revoked", item.pk)
    return Response(key_json(item))
