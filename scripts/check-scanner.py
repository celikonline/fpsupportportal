import io
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'apps/api'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from portal.files import antivirus
from rest_framework.exceptions import ValidationError

class Probe:
    def __init__(self, value): self.value = value
    def open(self, mode): return io.BytesIO(self.value)

if settings.DEV_SCAN_BYPASS:
    raise SystemExit('Real scan validation requires DEV_SCAN_BYPASS=0')
antivirus(Probe(b'FP Support harmless clean probe'))
signature = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$' + b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
try:
    antivirus(Probe(signature))
except ValidationError:
    print('PASS: real ClamAV allows clean input and rejects the in-memory EICAR test signature.')
else:
    raise SystemExit('FAIL: scanner accepted the antivirus test signature')
