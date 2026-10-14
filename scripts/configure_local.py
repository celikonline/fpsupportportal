from pathlib import Path
import secrets
import base64

root = Path(__file__).resolve().parent.parent
target = root / '.env'
if not target.exists():
    values = {'APP_ENV': 'development', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(48),
              'FIELD_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
              'POSTGRES_DB': 'support', 'POSTGRES_HOST': '127.0.0.1', 'POSTGRES_PORT': '56432', 'POSTGRES_USER': 'support_app',
              'POSTGRES_PASSWORD': secrets.token_urlsafe(24), 'POSTGRES_OWNER_PASSWORD': secrets.token_urlsafe(24),
              'REDIS_URL': 'redis://127.0.0.1:56379/0', 'CLAMAV_HOST': '127.0.0.1', 'CLAMAV_PORT': '53310',
              'DEMO_PASSWORD': secrets.token_urlsafe(18), 'DEV_SCAN_BYPASS': '0'}
    target.write_text('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n', encoding='utf-8')
print('Local configuration ready. Secrets stored only in ignored .env.')
