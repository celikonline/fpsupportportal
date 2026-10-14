import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('APP_ENV', 'production') == 'development'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'local-only-change-this-before-deployment-2026')
if not DEBUG and (SECRET_KEY.startswith('local-only') or not os.environ.get('FIELD_ENCRYPTION_KEY')):
    raise ImproperlyConfigured('Production requires DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'rest_framework', 'portal']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
              'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware', 'portal.middleware.SecurityHeadersMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DB_ENGINE = os.environ.get('DB_ENGINE', 'postgresql')
if DB_ENGINE == 'sqlite':
    if not DEBUG:
        raise ImproperlyConfigured('SQLite is development-only')
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'local.sqlite3'}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('POSTGRES_DB', 'support'),
                           'USER': os.environ.get('POSTGRES_USER', 'support_app'), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
                           'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'), 'PORT': os.environ.get('POSTGRES_PORT', '56432'),
                           'CONN_MAX_AGE': 0}}
LANGUAGE_CODE = 'tr'
TIME_ZONE = 'UTC'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['portal.api_key_auth.ProjectAPIKeyAuthentication', 'rest_framework.authentication.SessionAuthentication'],
                  'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
                  'EXCEPTION_HANDLER': 'portal.api.exception_handler', 'UNAUTHENTICATED_USER': None}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28800
SESSION_SAVE_EVERY_REQUEST = False
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(',')
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if not DEBUG else None
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
                            {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
                            {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}]
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 22 * 1024 * 1024
PRIVATE_STORAGE_ROOT = Path(os.environ.get('PRIVATE_STORAGE_ROOT', str(BASE_DIR / '../../.runtime/files'))).resolve()
if not DEBUG and not os.environ.get('PRIVATE_STORAGE_ROOT'):
    raise ImproperlyConfigured('Production requires a private storage/scratch path outside the source checkout')
if not DEBUG and PRIVATE_STORAGE_ROOT.is_relative_to(BASE_DIR.parent.parent):
    raise ImproperlyConfigured('Production storage/scratch must be outside the source checkout')
STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local')
S3_BUCKET = os.environ.get('S3_BUCKET', '')
S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL') or None
S3_REGION = os.environ.get('S3_REGION', 'eu-central-1')
if STORAGE_BACKEND == 's3' and not S3_BUCKET:
    raise ImproperlyConfigured('S3_BUCKET is required')
CLAMAV_HOST = os.environ.get('CLAMAV_HOST', '127.0.0.1')
CLAMAV_PORT = int(os.environ.get('CLAMAV_PORT', '53310'))
DEV_SCAN_BYPASS = DEBUG and os.environ.get('DEV_SCAN_BYPASS') == '1'
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:56379/0')
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_EAGER') == '1'
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_TASK_TIME_LIMIT = 90
CELERY_BEAT_SCHEDULE = {'outbox': {'task': 'portal.tasks.dispatch_outbox', 'schedule': 10.0},
                        'customer_replies': {'task': 'portal.automation_tasks.recover_customer_replies', 'schedule': 30.0},
                        'maintenance': {'task': 'portal.tasks.maintenance', 'schedule': 60.0}}
AI_API_URL = os.environ.get('AI_API_URL', '')
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_MODEL = os.environ.get('AI_MODEL', '')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'support@localhost')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
