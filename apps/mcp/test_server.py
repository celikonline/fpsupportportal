import asyncio
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters

spec = importlib.util.spec_from_file_location('portal_mcp_server', Path(__file__).with_name('server.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MCPTests(unittest.TestCase):
    def test_legacy_stdio_client_negotiates_and_lists_tools(self):
        import sys
        async def exercise():
            parameters = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name('server.py'))],
                env={'PORTAL_URL': 'http://127.0.0.1:8080', 'PORTAL_TENANT_ID': str(__import__('uuid').uuid4()),
                     'PORTAL_PROJECT_ID': str(__import__('uuid').uuid4()), 'PORTAL_API_KEY': 'synthetic-unusable-key'})
            async with Client(parameters, mode='legacy') as client:
                result = await client.list_tools()
                self.assertIn('claim_work', {tool.name for tool in result.tools})
        asyncio.run(exercise())

    def test_protocol_client_calls_scoped_tools(self):
        class FakePortal:
            def request(self, path, data=None):
                return {'path': path, 'data': data, 'results': []}
        async def exercise():
            async with Client(module.create_server(FakePortal())) as client:
                result = await client.call_tool('list_my_work', {'state': 'queued', 'page': 2})
                self.assertFalse(result.is_error)
                data = result.structured_content or json.loads(result.content[0].text)
                self.assertEqual(data['path'], '/work-items?state=queued&page=2')
        asyncio.run(exercise())

    def test_attachment_tool_returns_native_image_content(self):
        class FakePortal:
            def download(self, work_id, attachment_id):
                return b'synthetic-scanned-image', 'image/png'
        async def exercise():
            async with Client(module.create_server(FakePortal())) as client:
                result = await client.call_tool('read_attachment', {'work_id': '11111111-1111-1111-1111-111111111111', 'attachment_id': '22222222-2222-2222-2222-222222222222'})
                self.assertFalse(result.is_error)
                self.assertEqual(result.content[0].type, 'image')
                self.assertEqual(result.content[0].mime_type, 'image/png')
        asyncio.run(exercise())

    def test_registered_tools_have_schemas_and_no_direct_customer_write(self):
        server = module.create_server(None)
        tools = asyncio.run(server.list_tools())
        self.assertEqual({t.name for t in tools}, {'list_my_work', 'get_my_work', 'claim_work', 'heartbeat', 'submit_solution', 'release_work', 'read_attachment'})
        submit = next(t for t in tools if t.name == 'submit_solution')
        self.assertEqual(set(submit.input_schema['required']), {'work_id', 'claim_token', 'solution'})

    def test_client_requires_scoped_environment_and_secure_origin(self):
        env = {'PORTAL_URL': 'http://127.0.0.1:8080', 'PORTAL_TENANT_ID': '11111111-1111-1111-1111-111111111111',
               'PORTAL_PROJECT_ID': '22222222-2222-2222-2222-222222222222', 'PORTAL_API_KEY': 'synthetic-secret'}
        with patch.dict(os.environ, env):
            client = module.PortalClient()
            self.assertTrue(client.root.endswith('/projects/' + env['PORTAL_PROJECT_ID']))
        for url in ['http://remote.example.test', 'https://user:secret@remote.example.test', 'https://remote.example.test/path', 'https://remote.example.test?key=bad']:
            with patch.dict(os.environ, {**env, 'PORTAL_URL': url}), self.assertRaises(ValueError):
                module.PortalClient()


if __name__ == '__main__':
    unittest.main()
