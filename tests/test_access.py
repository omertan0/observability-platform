"""Erişim sınırları: ASGI kontrolleri ve çalışan API/Redis üzerinden gerçek oturum."""
import asyncio
from datetime import datetime, timezone
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
load_dotenv()
from fastapi import HTTPException
from starlette.requests import Request as ASGIRequest
from redis.exceptions import ConnectionError as RedisConnectionError
from client_access import AdminClient, ingestion_headers
import security

BASE = os.getenv('TEST_API_URL', 'http://127.0.0.1:8000')


def scope(method='GET', path='/logs', headers=()):
    return {'type': 'http', 'method': method, 'path': path, 'query_string': b'', 'scheme': 'http',
            'server': ('localhost', 8000), 'client': ('access-unit-test', 1234),
            'headers': [(name.lower().encode(), value.encode()) for name, value in headers]}


def middleware_status(method, path, headers=()):
    async def run():
        messages = []
        async def app(s, receive, send):
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})
        async def receive():
            return {'type': 'http.request', 'body': b''}
        async def send(message):
            messages.append(message)
        await security.AccessMiddleware(app)(scope(method, path, headers), receive, send)
        return messages[0]['status']
    return asyncio.run(run())


class AccessUnitChecks(unittest.TestCase):
    def test_public_health_and_default_closed_routes(self):
        self.assertEqual(middleware_status('GET', '/health'), 204)
        for path in ['/logs', '/metrics', '/alerts', '/alert-rules', '/docs', '/openapi.json', '/stream/logs', '/new-route']:
            with self.subTest(path=path):
                self.assertEqual(middleware_status('GET', path), 401)

    def test_ingest_key_has_only_explicit_permissions(self):
        header = [('Authorization', ingestion_headers()['Authorization'])]
        for path in security.INGEST_PATHS:
            self.assertEqual(middleware_status('POST', path, header), 204)
        self.assertEqual(middleware_status('GET', '/ready', header), 204)
        self.assertEqual(middleware_status('GET', '/tasks/00000000-0000-0000-0000-000000000000', header), 204)
        for method, path in [('GET', '/logs'), ('POST', '/alert-rules'), ('PATCH', '/alerts/1/acknowledge'),
                             ('GET', '/docs'), ('GET', '/auth/session'), ('GET', '/stream/metrics')]:
            self.assertEqual(middleware_status(method, path, header), 403)
        self.assertEqual(middleware_status('POST', '/logs', [('Authorization', 'Bearer wrong')]), 401)

    def test_cookie_mutations_require_csrf_and_allowed_origin(self):
        data = {'username': 'admin', 'csrf_token': 'c' * 43}
        with patch.object(security, 'read_session', return_value=data):
            self.assertEqual(middleware_status('GET', '/logs'), 204)
            self.assertEqual(middleware_status('PATCH', '/alert-rules/1'), 403)
            headers = [('X-CSRF-Token', data['csrf_token']), ('Origin', 'http://127.0.0.1:5173')]
            self.assertEqual(middleware_status('PATCH', '/alert-rules/1', headers), 204)
            for origin in ['https://attacker.example', 'null']:
                self.assertEqual(middleware_status('PATCH', '/alert-rules/1', [('X-CSRF-Token', data['csrf_token']), ('Origin', origin)]), 403)
            self.assertEqual(middleware_status('PATCH', '/alert-rules/1', [('X-CSRF-Token', data['csrf_token']), ('Sec-Fetch-Site', 'cross-site')]), 403)

    def test_missing_configuration_and_redis_outage_fail_closed(self):
        with patch.dict(os.environ, {'PANEL_PASSWORD': ''}):
            self.assertEqual(middleware_status('GET', '/logs'), 503)
            self.assertEqual(middleware_status('GET', '/health'), 204)
        with patch.object(security, 'redis_client', side_effect=RedisConnectionError()):
            self.assertEqual(middleware_status('GET', '/logs', [('Cookie', security.COOKIE + '=' + 't' * 43)]), 503)

    def test_session_expiry_rotation_and_hashed_storage_key(self):
        user, password, _ = security.settings()
        token = 't' * 43
        request = ASGIRequest(scope(headers=[('Cookie', security.COOKIE + '=' + token)]))
        data = {'username': user, 'csrf_token': 'c' * 43, 'expires_at': time.time() + 60,
                'credential': security.digest(user + '\0' + password)}
        client = MagicMock()
        client.get.return_value = json.dumps(data)
        with patch.object(security, 'redis_client') as factory:
            factory.return_value.__enter__.return_value = client
            self.assertEqual(security.read_session(request)['username'], user)
            self.assertNotIn(token, client.get.call_args.args[0])
            for change in [{'expires_at': 0}, {'credential': 'old'}, {'csrf_token': None}]:
                client.get.return_value = json.dumps({**data, **change})
                with self.assertRaises(HTTPException) as error:
                    security.read_session(request)
                self.assertEqual(error.exception.status_code, 401)

    def test_login_rate_limit_and_secure_cookie_options(self):
        user, password, _ = security.settings()
        request = ASGIRequest(scope('POST', '/auth/login'))
        client = MagicMock()
        with patch.object(security, 'redis_client') as factory:
            factory.return_value.__enter__.return_value = client
            client.eval.return_value = 11
            with self.assertRaises(HTTPException) as error:
                security.login_session(request, security.LoginInput(username=user, password=password))
            self.assertEqual(error.exception.status_code, 429)
            client.eval.return_value = 1
            with patch.dict(os.environ, {'SESSION_COOKIE_SECURE': 'true'}):
                response = security.login_session(request, security.LoginInput(username=user, password=password))
            cookie = response.headers['set-cookie']
            for flag in ['HttpOnly', 'Secure', 'SameSite=strict', 'Max-Age=28800']:
                self.assertIn(flag, cookie)
            self.assertNotIn(password, cookie)


class AccessHTTPChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = AdminClient(BASE)
        cls.client.login()

    @classmethod
    def tearDownClass(cls):
        cls.client.logout()

    def status(self, req, client=None):
        try:
            with (client.open(req, timeout=10) if client else urlopen(req, timeout=10)) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_anonymous_and_invalid_credentials(self):
        for path in ['/logs', '/metrics', '/alert-rules', '/alerts', '/docs', '/openapi.json', '/stream/logs', '/ready']:
            self.assertEqual(self.status(BASE + path)[0], 401)
        self.assertEqual(self.status(BASE + '/health')[0], 200)
        headers = {'Content-Type': 'application/json', 'X-Requested-With': 'observability'}
        req = Request(BASE + '/auth/login', data=json.dumps({'username': 'unknown', 'password': 'wrong'}).encode(), headers=headers)
        code, body = self.status(req)
        self.assertEqual(code, 401)
        self.assertNotIn('wrong', json.dumps(body))
        req = Request(BASE + '/auth/login', data=b'{}', headers={'Content-Type': 'application/json'})
        self.assertEqual(self.status(req)[0], 403)
        req = Request(BASE + '/auth/login', data=b'x' * 4097, headers=headers)
        self.assertEqual(self.status(req)[0], 413)

    def test_session_csrf_origin_and_openapi_permissions(self):
        code, body = self.status(BASE + '/auth/session', self.client)
        self.assertEqual(code, 200)
        self.assertEqual(body['username'], os.getenv('PANEL_USERNAME'))
        self.assertGreater(datetime.fromisoformat(body['expires_at']), datetime.now(timezone.utc))
        # Aynı çerezle fakat CSRF başlığı olmadan gerçek PATCH reddedilmeli.
        raw = Request(BASE + '/alert-rules/9223372036854775807', data=b'{"enabled":true}', method='PATCH', headers={'Content-Type': 'application/json'})
        try:
            self.client.opener.open(raw, timeout=10)
            self.fail('CSRF olmadan kabul edildi')
        except HTTPError as error:
            with error:
                self.assertEqual(error.code, 403)
        raw.add_header('Origin', 'https://attacker.example')
        self.assertEqual(self.status(raw, self.client)[0], 403)
        raw.remove_header('Origin')
        self.assertEqual(self.status(raw, self.client)[0], 404)
        code, schema = self.status(BASE + '/openapi.json', self.client)
        self.assertEqual(code, 200)
        self.assertIn({'IngestKey': []}, schema['paths']['/logs']['post']['security'])
        self.assertNotIn({'IngestKey': []}, schema['paths']['/alert-rules']['post']['security'])
        self.assertIn('CsrfToken', schema['paths']['/alert-rules']['post']['security'][0])

    def test_ingest_key_cannot_read_or_manage(self):
        headers = {'Content-Type': 'application/json', **ingestion_headers()}
        self.assertEqual(self.status(Request(BASE + '/ready', headers=headers))[0], 200)
        self.assertEqual(self.status(Request(BASE + '/logs', headers=headers))[0], 403)
        self.assertEqual(self.status(Request(BASE + '/logs', data=b'{}', headers=headers))[0], 422)
        self.assertEqual(self.status(Request(BASE + '/alert-rules', data=b'{}', headers=headers))[0], 403)

    def test_logout_revokes_cookie_and_open_sse(self):
        client = AdminClient(BASE)
        client.login()
        old_token = next(cookie.value for cookie in client.cookies if cookie.name == security.COOKIE)
        from test_stream import next_event
        with client.open(BASE + '/stream/logs', timeout=10) as response:
            self.assertEqual(next_event(response)['event'], 'logs_changed')
            client.logout()
            self.assertEqual(next_event(response)['event'], 'auth_expired')
            self.assertEqual(response.read(), b'')
        req = Request(BASE + '/logs', headers={'Cookie': security.COOKIE + '=' + old_token})
        self.assertEqual(self.status(req)[0], 401)
