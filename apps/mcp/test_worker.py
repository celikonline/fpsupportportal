import json
import sys
import tempfile
import unittest
import uuid

from worker import consume_one


class WorkerTests(unittest.TestCase):
    def test_process_consumes_assigned_work_and_submits_to_po(self):
        calls = []
        work_id, token = str(uuid.uuid4()), str(uuid.uuid4())
        class Client:
            def request(self, path, data=None):
                calls.append((path, data))
                if path.endswith('/claim'):
                    return {'id': work_id, 'claimToken': token, 'ticket': {'title': 'Synthetic'}, 'reason': 'Verify tests'}
                return {'state': 'solution_review'}
        with tempfile.TemporaryDirectory() as cwd:
            result = consume_one(Client(), {'id': work_id, 'version': 2}, [sys.executable, '-c',
                'import sys,json; job=json.load(sys.stdin); assert "claimToken" not in job; print(json.dumps({"solution":"Verified synthetic solution"}))'], cwd)
        self.assertEqual(result['state'], 'solution_review')
        self.assertEqual(calls[-1][1]['action'], 'submit')
        self.assertEqual(calls[-1][1]['claimToken'], token)

    def test_invalid_agent_output_returns_job_to_po(self):
        calls = []
        work_id, token = str(uuid.uuid4()), str(uuid.uuid4())
        class Client:
            def request(self, path, data=None):
                calls.append((path, data))
                return {'id': work_id, 'claimToken': token} if path.endswith('/claim') else {'state': 'review'}
        with tempfile.TemporaryDirectory() as cwd, self.assertRaises(ValueError):
            consume_one(Client(), {'id': work_id, 'version': 1}, [sys.executable, '-c', 'print("{\\\"solution\\\":\\\"\\\"}")'], cwd)
        self.assertEqual(calls[-1][1]['action'], 'release')
        self.assertNotIn('solution', calls[-1][1])
