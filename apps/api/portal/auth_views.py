import hashlib
from datetime import timedelta
import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import MFADevice, LoginAttempt
from .security import cipher, audit
from .api import user_json

@api_view(['GET'])
@permission_classes([AllowAny])
def session(request):
    device = MFADevice.objects.filter(user=request.user).first() if request.user else None
    return Response({'user': user_json(request.user) if request.user and request.user.is_authenticated else None,
                     'csrfToken': get_token(request), 'mfaEnabled': bool(device and device.enabled),
                     'development': settings.DEBUG, 'scanBypass': settings.DEV_SCAN_BYPASS,
                     'enrollmentRequired': bool(request.session.get('enrollment_only'))})

def verify_device(device, code):
    totp = pyotp.TOTP(cipher().decrypt(device.encrypted_secret.encode()).decode())
    counter = int(timezone.now().timestamp()) // 30
    matched = next((step for step in [counter - 1, counter, counter + 1] if step > device.last_counter and
                    pyotp.utils.strings_equal(totp.at(step * 30), str(code))), None)
    if matched is None:
        return False
    device.last_counter = matched
    device.save(update_fields=['last_counter'])
    return True

@csrf_protect
@api_view(['POST'])
@permission_classes([AllowAny])
def sign_in(request):
    from rest_framework.authentication import SessionAuthentication
    SessionAuthentication().enforce_csrf(request)
    name = str(request.data.get('username', ''))[:150]
    ip = request.META.get('REMOTE_ADDR', '')
    key = hashlib.sha256((ip + ':' + name.lower()).encode()).hexdigest()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(key=key, defaults={'last_at': timezone.now()})
        if attempt.failures >= 5 and timezone.now() - attempt.last_at < timedelta(minutes=15):
            return Response({'detail': 'Çok fazla deneme. 15 dakika sonra tekrar deneyin.'}, status=429)
        if timezone.now() - attempt.last_at >= timedelta(minutes=15):
            attempt.failures = 0
        user = authenticate(request, username=name, password=request.data.get('password', ''))
        device = MFADevice.objects.select_for_update().filter(user=user, enabled=True).first() if user else None
        if not user or (device and not verify_device(device, request.data.get('code', ''))):
            attempt.failures += 1
            attempt.last_at = timezone.now()
            attempt.save()
            audit('anonymous', None, None, 'login', result='denied')
            return Response({'detail': 'Kullanıcı bilgileri veya doğrulama kodu geçersiz.'}, status=400)
        attempt.delete()
        login(request, user)
        if not settings.DEBUG and not device:
            request.session['enrollment_only'] = True
        if device:
            request.session['mfa_at'] = timezone.now().timestamp()
        audit(user, None, None, 'login')
    return Response({'user': user_json(user), 'csrfToken': get_token(request)})

@api_view(['POST'])
def sign_out(request):
    audit(request.user, None, None, 'logout')
    logout(request)
    return Response({'ok': True})

@api_view(['POST'])
def mfa_setup(request):
    if not request.user.check_password(request.data.get('password', '')):
        raise PermissionDenied('Parola doğrulanamadı.')
    with transaction.atomic():
        device, _ = MFADevice.objects.select_for_update().get_or_create(user=request.user)
        if device.enabled:
            raise ValidationError('MFA zaten etkin.')
        secret = pyotp.random_base32()
        device.encrypted_secret = cipher().encrypt(secret.encode()).decode()
        device.last_counter = -1
        device.save()
    return Response({'secret': secret, 'uri': pyotp.TOTP(secret).provisioning_uri(request.user.username, issuer_name='FP Support')})

@api_view(['POST'])
def mfa_verify(request):
    with transaction.atomic():
        key = hashlib.sha256(f'mfa:{request.user.pk}'.encode()).hexdigest()
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(key=key, defaults={'last_at': timezone.now()})
        if attempt.failures >= 5 and timezone.now()-attempt.last_at < timedelta(minutes=15):
            return Response({'detail':'Doğrulama deneme sınırı aşıldı. 15 dakika sonra tekrar deneyin.'},status=429)
        device = MFADevice.objects.select_for_update().filter(user=request.user).first()
        if not device or not verify_device(device, request.data.get('code', '')):
            if timezone.now()-attempt.last_at >= timedelta(minutes=15):
                attempt.failures = 0
            attempt.failures += 1
            attempt.last_at = timezone.now()
            attempt.save()
            return Response({'detail':'Doğrulama kodu geçersiz veya kullanılmış.'},status=400)
        attempt.delete()
        device.enabled = True
        device.save(update_fields=['enabled'])
        request.session['mfa_at'] = timezone.now().timestamp()
        request.session.pop('enrollment_only', None)
        audit(request.user, None, None, 'mfa_verified')
    return Response({'ok': True})

@api_view(['POST'])
def change_password(request):
    if not request.user.check_password(request.data.get('currentPassword', '')):
        raise PermissionDenied('Parola doğrulanamadı.')
    password = request.data.get('newPassword', '')
    try:
        validate_password(password, request.user)
    except Exception as exc:
        raise ValidationError(getattr(exc, 'messages', ['Parola uygun değil.']))
    request.user.set_password(password)
    request.user.save()
    audit(request.user, None, None, 'password_changed')
    logout(request)
    return Response({'ok': True})
