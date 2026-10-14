class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.utils import timezone
        from django.contrib.auth import logout
        from django.http import JsonResponse
        if request.session.get('enrollment_only') and request.path not in {
                '/api/v1/session', '/api/v1/auth/mfa/setup', '/api/v1/auth/mfa/verify', '/api/v1/auth/logout'}:
            return JsonResponse({'detail': 'Önce MFA kurulumunu tamamlayın.', 'enrollmentRequired': True}, status=403)
        if request.user.is_authenticated:
            stamp = timezone.now().timestamp()
            previous = request.session.get('last_activity', stamp)
            if stamp - previous > 1800:
                logout(request)
            elif not request.path.endswith('/notifications') and (stamp - previous > 60 or 'last_activity' not in request.session):
                request.session['last_activity'] = stamp
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        response['Cache-Control'] = 'no-store'
        return response
