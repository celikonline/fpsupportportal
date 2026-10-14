import hashlib
import io
import socket
import struct
import warnings
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from rest_framework.exceptions import ValidationError

ALLOWED = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
           '.pdf': 'application/pdf', '.txt': 'text/plain', '.csv': 'text/csv'}
Image.MAX_IMAGE_PIXELS = 20_000_000

def file_path(key):
    # Only server-generated UUID keys are accepted.
    import uuid
    try:
        uuid.UUID(key)
    except ValueError:
        raise ValidationError('Geçersiz dosya kimliği.')
    return settings.PRIVATE_STORAGE_ROOT / key

def s3_client():
    import boto3
    return boto3.client('s3', endpoint_url=settings.S3_ENDPOINT_URL, region_name=settings.S3_REGION)

def persist_blob(key, clean=False):
    if settings.STORAGE_BACKEND != 's3':
        return
    path = file_path(key)
    prefix = 'clean' if clean else 'quarantine'
    with path.open('rb') as content:
        s3_client().put_object(Bucket=settings.S3_BUCKET, Key=f'{prefix}/{key}', Body=content, ServerSideEncryption='AES256')
    path.unlink(missing_ok=True)

def cleanup_quarantine(key):
    if settings.STORAGE_BACKEND == 's3':
        s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=f'quarantine/{key}')

def hydrate_blob(key):
    path = file_path(key)
    if settings.STORAGE_BACKEND == 's3':
        path.parent.mkdir(parents=True, exist_ok=True)
        s3_client().download_file(settings.S3_BUCKET, f'quarantine/{key}', str(path))
    return path

def open_blob(key):
    if settings.STORAGE_BACKEND == 's3':
        return s3_client().get_object(Bucket=settings.S3_BUCKET, Key=f'clean/{key}')['Body']
    return file_path(key).open('rb')

def remove_blob(key):
    if settings.STORAGE_BACKEND == 's3':
        for prefix in ['quarantine', 'clean']:
            s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=f'{prefix}/{key}')
    file_path(key).unlink(missing_ok=True)

def ingest(upload, key):
    filename = Path(upload.name.replace('\\', '/')).name[:200]
    extension = Path(filename).suffix.lower()
    mime = ALLOWED.get(extension)
    if not mime:
        raise ValidationError('Bu dosya türüne izin verilmiyor.')
    limit = 10 * 1024 * 1024 if mime.startswith('image/') else 20 * 1024 * 1024
    path = file_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    try:
        with path.open('wb') as output:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > limit:
                    raise ValidationError('Dosya boyutu sınırı aşıldı.')
                digest.update(chunk)
                output.write(chunk)
        if not size:
            raise ValidationError('Boş dosya yüklenemez.')
        with path.open('rb') as source:
            header = source.read(16)
        if mime.startswith('image/'):
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    expected = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP'}[mime]
                    if image.format != expected or image.width * image.height > 20_000_000:
                        raise ValidationError('Resim türü veya piksel sınırı geçersiz.')
                    image.verify()
        elif mime == 'application/pdf' and not header.startswith(b'%PDF-'):
            raise ValidationError('PDF içerik imzası geçersiz.')
        elif mime in {'text/plain', 'text/csv'}:
            with path.open('r', encoding='utf-8-sig') as source:
                while chunk := source.read(65536):
                    if '\x00' in chunk:
                        raise ValidationError('Metin dosyası geçersiz.')
        return filename, mime, size, digest.hexdigest()
    except (UnidentifiedImageError, UnicodeDecodeError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        path.unlink(missing_ok=True)
        raise ValidationError('Dosya içeriği doğrulanamadı.') from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise

def antivirus(path):
    if settings.DEV_SCAN_BYPASS:
        return
    with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=10) as client:
        client.settimeout(45)
        client.sendall(b'zINSTREAM\0')
        with path.open('rb') as source:
            while chunk := source.read(65536):
                client.sendall(struct.pack('!I', len(chunk)) + chunk)
        client.sendall(struct.pack('!I', 0))
        result = b''
        while b'\0' not in result and len(result) < 4096:
            chunk = client.recv(4096)
            if not chunk:
                break
            result += chunk
        if b'FOUND' in result:
            raise ValidationError('Zararlı dosya tespit edildi.')
        if not result.strip(b'\0\n').endswith(b'OK'):
            raise OSError('Scanner did not return a clean verdict')

def sanitize_image(path, mime):
    if not mime.startswith('image/'):
        return
    with Image.open(path) as image:
        pixels = image.convert('RGB') if mime == 'image/jpeg' else image.convert('RGBA')
        temporary = path.with_suffix('.tmp')
        pixels.save(temporary, format={'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP'}[mime])
    temporary.replace(path)

def erase_attachment(attachment):
    remove_blob(attachment.storage_key)
    attachment.state = 'deleted'
    attachment.filename = 'silindi'
    attachment.size = 0
    attachment.sha256 = ''
    attachment.save(update_fields=['state', 'filename', 'size', 'sha256'])
