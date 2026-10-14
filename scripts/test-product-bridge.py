"""Run the Oto bridge worker tests against a newly created, isolated PostgreSQL DB."""
import os
from pathlib import Path
import subprocess
import uuid
from urllib.parse import quote

import psycopg
from psycopg import sql

root = Path(__file__).resolve().parent.parent
values = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
params = dict(host=values.get('POSTGRES_HOST', '127.0.0.1'), port=values.get('POSTGRES_PORT', '56432'),
              user='support_owner', password=values['POSTGRES_OWNER_PASSWORD'], dbname=values.get('POSTGRES_DB', 'support'))
name = 'support_bridge_test_' + uuid.uuid4().hex
with psycopg.connect(**params, autocommit=True) as owner:
    owner.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        env = dict(os.environ)
        env['FP_SUPPORT_TEST_DATABASE_URL'] = f"postgresql://support_owner:{quote(params['password'], safe='')}@{params['host']}:{params['port']}/{name}"
        broker = root.parent / 'ototeklifall' / 'node-sms-broker'
        result = subprocess.run(['npm.cmd' if os.name == 'nt' else 'npm', 'run', 'test:fp-support-db'], cwd=broker, env=env)
    finally:
        owner.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
raise SystemExit(result.returncode)
