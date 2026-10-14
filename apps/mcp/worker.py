"""Optional external worker supervisor: assigned jobs -> agent process -> PO review.

The operator supplies a trusted command; ticket text is never interpreted as a command.
The agent receives JSON on stdin and must return {"solution": "..."} on stdout.
"""
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

from server import PortalClient


def consume_one(client, work, command, cwd, timeout=3600):
    work_id = str(uuid.UUID(work['id']))
    claim = client.request(f'/work-items/{work_id}/claim', {'version': work['version']})
    token = claim['claimToken']
    child_env = dict(os.environ)
    child_env.pop('PORTAL_API_KEY', None)  # The subprocess needs job context, not the gateway secret.
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = None
    try:
        with tempfile.TemporaryDirectory() as job_dir, tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            # Temporary files avoid pipe deadlocks when an agent writes progress/output before reading stdin.
            context = {key: value for key, value in claim.items() if key != 'claimToken'}
            context['localAttachments'] = []
            attachments = list(claim.get('ticket', {}).get('attachments', []))
            for comment in claim.get('ticket', {}).get('comments', []):
                attachments.extend(comment.get('attachments', []))
            total = 0
            for item in attachments[:10]:
                if item.get('state') != 'clean':
                    continue
                attachment_id = str(uuid.UUID(item['id']))
                data, mime = client.download(work_id, attachment_id)
                total += len(data)
                if total > 50*1024*1024:
                    raise ValueError('Total attachment limit exceeded')
                extension = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'application/pdf': 'pdf', 'text/plain': 'txt', 'text/csv': 'csv'}.get(mime, 'bin')
                path = Path(job_dir) / f'{attachment_id}.{extension}'
                path.write_bytes(data)
                context['localAttachments'].append({'id': attachment_id, 'path': str(path), 'mimeType': mime})
            input_file.write(json.dumps(context, ensure_ascii=False).encode())
            input_file.seek(0)
            process = subprocess.Popen(command, cwd=cwd, env=child_env, stdin=input_file, stdout=output,
                                       stderr=errors, shell=False, creationflags=flags)
            started, renewed = time.monotonic(), time.monotonic()
            while process.poll() is None:
                now = time.monotonic()
                if now - started > timeout:
                    raise TimeoutError('Agent execution timed out')
                if now - renewed >= 120:
                    client.request(f'/work-items/{work_id}/update', {'action': 'heartbeat', 'claimToken': token})
                    renewed = now
                if output.tell() > 256*1024 or errors.tell() > 1024*1024:
                    raise ValueError('Agent output limit exceeded')
                time.sleep(1)
            if process.returncode != 0:
                raise ValueError('Agent process failed')
            output.seek(0)
            raw = output.read(256*1024 + 1)
            if len(raw) > 256*1024:
                raise ValueError('Agent output limit exceeded')
            result = json.loads(raw)
            solution = result.get('solution') if isinstance(result, dict) else None
            if not isinstance(solution, str) or not 1 <= len(solution.strip()) <= 20000:
                raise ValueError('Agent must return a verified solution')
            return client.request(f'/work-items/{work_id}/update', {'action': 'submit', 'claimToken': token, 'solution': solution.strip()})
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        try:
            client.request(f'/work-items/{work_id}/update', {'action': 'release', 'claimToken': token,
                'reason': 'Dış agent çalışması başarısız veya kesildi. Çalışma ortamını ve kabul koşullarını kontrol edin.'})
        except Exception:
            pass  # Expired/reassigned claims must never be overwritten.
        raise


def run():
    command = json.loads(os.environ['FP_WORKER_COMMAND'])
    if not isinstance(command, list) or not command or any(not isinstance(value, str) or not value for value in command):
        raise ValueError('FP_WORKER_COMMAND must be a JSON argv array')
    cwd = os.environ['FP_WORKER_CWD']
    if not os.path.isabs(cwd) or not os.path.isdir(cwd):
        raise ValueError('FP_WORKER_CWD must be an existing absolute work directory')
    client = PortalClient()
    timeout = int(os.environ.get('FP_WORKER_TIMEOUT_SECONDS', '3600'))
    if not 60 <= timeout <= 86400:
        raise ValueError('FP_WORKER_TIMEOUT_SECONDS must be 60..86400')
    while True:
        try:
            # Collect a snapshot before processing; consumption changes state/page membership.
            snapshot = []
            for state in ['queued', 'claimed']:
                page = 1
                while True:
                    batch = client.request(f'/work-items?state={state}&page={page}')
                    snapshot.extend(batch['results'])
                    if page * batch['pageSize'] >= batch['total']:
                        break
                    page += 1
            for work in snapshot:
                if work['state'] == 'claimed' and (not work.get('leaseUntil') or datetime.fromisoformat(work['leaseUntil']) > datetime.now(timezone.utc)):
                    continue
                try:
                    consume_one(client, work, command, cwd, timeout)
                    print('Solution submitted for PO review: ' + work['id'], flush=True)
                except Exception:
                    # No provider stderr, ticket data, keys, or upstream exceptions are logged.
                    print('Work not consumed; ownership changed or agent failed: ' + work['id'], flush=True)
        except Exception:
            print('Portal unavailable; polling will retry.', flush=True)
        time.sleep(45)


if __name__ == '__main__':
    run()
