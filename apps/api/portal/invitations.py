import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from .models import Invitation, Tenant, TenantMembership, ProjectMembership, Project
from .api import scoped, text
from .security import fresh_mfa, audit, ROLES, tenant_context

@api_view(['GET', 'POST'])
@scoped(False)
def invitations(request, tenant, member):
    if member.role != 'admin':
        raise PermissionDenied('Tenant yöneticisi gerekiyor.')
    if request.method == 'GET':
        return Response([{'id': str(i.pk), 'email': i.email, 'role': i.role, 'accepted': i.accepted,
                          'expiresAt': i.expires_at.isoformat()} for i in Invitation.objects.filter(tenant=tenant).order_by('-expires_at')[:100]])
    fresh_mfa(request)
    email = text(request.data, 'email', 254).lower()
    try:
        validate_email(email)
    except DjangoValidationError:
        raise ValidationError('E-posta adresi geçersiz.')
    role = request.data.get('role', 'requester')
    project = Project.objects.filter(tenant=tenant, pk=request.data.get('projectId')).first()
    if role not in ROLES or not project:
        raise ValidationError('Rol veya proje geçersiz.')
    token = secrets.token_urlsafe(32)
    item = Invitation.objects.create(tenant=tenant, project=project, email=email, role=role,
                                      token_digest=hashlib.sha256(token.encode()).hexdigest(),
                                      expires_at=timezone.now()+timedelta(days=3), created_by=request.user)
    audit(request.user, tenant, project, 'invitation_created', item.pk)
    # Secret is returned only once. Browser uses a fragment URL; token never enters access logs.
    return Response({'id': str(item.pk), 'token': token}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
def accept(request):
    SessionAuthentication().enforce_csrf(request)
    token = text(request.data, 'token', 128)
    digest = hashlib.sha256(token.encode()).hexdigest()
    # Invitation table is discoverable only by high-entropy token; rows are never publicly listed.
    item = Invitation.objects.filter(token_digest=digest, accepted=False, expires_at__gt=timezone.now(), tenant__active=True).first()
    if not item:
        raise ValidationError('Davet geçersiz veya süresi dolmuş.')
    with tenant_context(item.tenant_id):
        Tenant.objects.select_for_update().get(pk=item.tenant_id)
        item = Invitation.objects.select_for_update().get(pk=item.pk)
        if item.accepted:
            raise ValidationError('Davet kullanılmış.')
        existing = get_user_model().objects.filter(email__iexact=item.email).first()
        if existing:
            if not request.user or not request.user.is_authenticated or request.user.pk != existing.pk:
                raise PermissionDenied('Bu e-postaya ait hesabınızla giriş yaparak daveti kabul edin.')
            user = existing
        else:
            name = text(request.data, 'username', 150)
            if get_user_model().objects.filter(username=name).exists():
                raise ValidationError('Kullanıcı adı kullanılıyor.')
            password = text(request.data, 'password', 200)
            user = get_user_model()(username=name, email=item.email, first_name=text(request.data,'name',150))
            try:
                validate_password(password, user)
            except DjangoValidationError as exc:
                raise ValidationError(exc.messages)
            user.set_password(password)
            user.save()
        membership, _ = TenantMembership.objects.get_or_create(tenant=item.tenant, user=user)
        if not membership.active:
            raise PermissionDenied('Üyeliğiniz askıya alınmış. Yöneticiyle iletişime geçin.')
        ProjectMembership.objects.update_or_create(tenant=item.tenant, project=item.project, user=user, defaults={'role': item.role,'active':True})
        item.accepted = True
        item.save(update_fields=['accepted'])
        audit(user, item.tenant, item.project, 'invitation_accepted', item.pk)
    return Response({'ok': True})
