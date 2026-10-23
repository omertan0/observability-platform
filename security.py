"""Tek yönetici oturumu, CSRF kontrolü ve sınırlı veri gönderim anahtarı."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import secrets
import time

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError

COOKIE = 'observability_session'
SESSION_SECONDS = 8 * 60 * 60
TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{32,128}')
MUTATIONS = {'POST', 'PUT', 'PATCH', 'DELETE'}
INGEST_PATHS = {'/logs', '/metrics', '/logs/batch', '/metrics/batch'}
router = APIRouter(prefix='/auth', tags=['Erişim'])


def settings():
    username = os.getenv('PANEL_USERNAME', 'admin')
    password = os.getenv('PANEL_PASSWORD', '')
    key = os.getenv('INGEST_API_KEY', '')
    if not username or len(username) > 64 or not 16 <= len(password) <= 256 or len(key) < 32 or password == key:
        raise HTTPException(503, 'Erişim ayarları hazır değil. Sunucuda setup_access.py çalıştırılmalı.')
    return username, password, key


def redis_client():
    return Redis.from_url(os.getenv('AUTH_REDIS_URL', os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')),
                          socket_connect_timeout=2, socket_timeout=2, decode_responses=True)


def digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def session_key(token):
    return 'observability:auth:session:' + digest(token)


def equal(left, right):
    # Unicode girdilerde de sabit uzunlukta bayt dizilerini karşılaştırır.
    return secrets.compare_digest(digest(left), digest(right))


def check_origin(request):
    origins = {value.strip().rstrip('/') for value in os.getenv(
        'PANEL_ALLOWED_ORIGINS',
        'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000',
    ).split(',') if value.strip()}
    origin = request.headers.get('origin')
    if request.headers.get('sec-fetch-site') == 'cross-site' or (origin is not None and origin not in origins):
        raise HTTPException(403, 'Bu kaynaktan işlem yapılamaz.')


def read_session(request):
    username, password, _ = settings()
    token = request.cookies.get(COOKIE, '')
    if not TOKEN_PATTERN.fullmatch(token):
        raise HTTPException(401, 'Giriş yapmalısın.')
    with redis_client() as client:
        raw = client.get(session_key(token))
    try:
        data = json.loads(raw) if raw else {}
        valid = (data.get('username') == username and data.get('expires_at', 0) > time.time()
                 and equal(data.get('credential', ''), digest(username + '\0' + password))
                 and isinstance(data.get('csrf_token'), str) and TOKEN_PATTERN.fullmatch(data['csrf_token']))
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(401, 'Oturum sona erdi. Yeniden giriş yapmalısın.')
    return data


def authorize(request):
    _, _, key = settings()
    authorization = request.headers.get('authorization')
    if authorization:
        scheme, _, supplied = authorization.partition(' ')
        if scheme.lower() != 'bearer' or not equal(supplied, key):
            raise HTTPException(401, 'Geçerli bir veri gönderim anahtarı gerekli.', headers={'WWW-Authenticate': 'Bearer'})
        allowed = ((request.method == 'POST' and request.url.path in INGEST_PATHS)
                   or (request.method == 'GET' and (request.url.path == '/ready' or re.fullmatch(r'/tasks/[0-9a-fA-F-]{36}', request.url.path))))
        if not allowed:
            raise HTTPException(403, 'Veri gönderim anahtarının bu işleme yetkisi yok.')
        return {'kind': 'ingest'}
    data = read_session(request)
    if request.method in MUTATIONS:
        check_origin(request)
        if not equal(request.headers.get('x-csrf-token', ''), data['csrf_token']):
            raise HTTPException(403, 'İşlem doğrulaması başarısız. Oturumu yenile.')
    return {'kind': 'session', **data}


class AccessMiddleware:
    """Docs ve yeni eklenecek yollar dahil varsayılan olarak erişimi kapatır."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        try:
            public = (request.method, request.url.path) in {('GET', '/health'), ('POST', '/auth/login')}
            if public and request.url.path == '/auth/login':
                check_origin(request)
                if request.headers.get('x-requested-with') != 'observability':
                    raise HTTPException(403, 'Giriş isteği doğrulanamadı.')
                # Büyük gövdeyi Pydantic okumadan önce reddeder.
                length = request.headers.get('content-length')
                if length and (not length.isdigit() or int(length) > 4096):
                    raise HTTPException(413, 'Giriş isteği çok büyük.')
            if not public:
                scope.setdefault('state', {})['access'] = await anyio.to_thread.run_sync(authorize, request)
        except (HTTPException, RedisError) as exc:
            code = exc.status_code if isinstance(exc, HTTPException) else 503
            detail = exc.detail if isinstance(exc, HTTPException) else 'Oturum servisine erişilemiyor.'
            response = JSONResponse({'detail': detail}, status_code=code, headers=getattr(exc, 'headers', None))
            response.headers['Cache-Control'] = 'no-store'
            await response(scope, receive, send)
            return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if request.url.path == '/auth/login' and message['type'] == 'http.request':
                received_bytes += len(message.get('body', b''))
                if received_bytes > 4096:
                    raise HTTPException(413, 'Giriş isteği çok büyük.')
            return message

        async def secured_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                if not any(name.lower() == b'cache-control' for name, _ in headers):
                    headers.append((b'cache-control', b'no-store'))
                headers.extend([(b'x-content-type-options', b'nosniff'), (b'x-frame-options', b'DENY')])
                message['headers'] = headers
            await send(message)
        await self.app(scope, limited_receive, secured_send)


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256, repr=False)


def public_session(data):
    return {'username': data['username'], 'csrf_token': data['csrf_token'],
            'expires_at': datetime.fromtimestamp(data['expires_at'], timezone.utc).isoformat()}


def login_session(request, credentials):
    username, password, _ = settings()
    peer = request.client.host if request.client else 'unknown'
    limit_key = 'observability:auth:login:' + digest(peer)
    with redis_client() as client:
        # Aynı IP için 60 saniyede en fazla 10 giriş denemesi; tüm API süreçleri ortak sayar.
        count = client.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", 1, limit_key)
        if count > 10:
            raise HTTPException(429, 'Çok fazla giriş denemesi. Bir dakika sonra yeniden dene.', headers={'Retry-After': '60'})
        user_ok = equal(credentials.username, username)
        password_ok = equal(credentials.password, password)
        if not (user_ok and password_ok):
            raise HTTPException(401, 'Kullanıcı adı veya şifre yanlış.')
        token = secrets.token_urlsafe(32)
        data = {'username': username, 'csrf_token': secrets.token_urlsafe(32),
                'expires_at': int(time.time()) + SESSION_SECONDS, 'credential': digest(username + '\0' + password)}
        old = request.cookies.get(COOKIE, '')
        with client.pipeline(transaction=True) as pipe:
            if TOKEN_PATTERN.fullmatch(old):
                pipe.delete(session_key(old))
            pipe.set(session_key(token), json.dumps(data), ex=SESSION_SECONDS)
            pipe.execute()
    response = JSONResponse(public_session(data))
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite='strict',
                        secure=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true', path='/')
    return response


@router.post('/login')
def login(request: Request, credentials: LoginInput):
    try:
        return login_session(request, credentials)
    except RedisError:
        raise HTTPException(503, 'Oturum servisine erişilemiyor.') from None


@router.get('/session')
def current_session(request: Request):
    return public_session(request.state.access)


@router.post('/logout')
def logout(request: Request):
    try:
        with redis_client() as client:
            client.delete(session_key(request.cookies[COOKIE]))
    except RedisError:
        raise HTTPException(503, 'Çıkış doğrulanamadı; yeniden dene.') from None
    response = JSONResponse({'status': 'signed_out'})
    response.delete_cookie(COOKIE, path='/', httponly=True, samesite='strict',
                           secure=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true')
    return response


async def stream_access_valid(request):
    # Doğrudan generator birim testleri ASGI oturumu oluşturmaz.
    if not isinstance(getattr(request, 'scope', None), dict) or not request.scope.get('state', {}).get('access'):
        return True
    try:
        await anyio.to_thread.run_sync(authorize, request)
        return True
    except HTTPException as exc:
        if exc.status_code == 503:
            raise RedisError('access unavailable') from None
        return False


def install_access(app):
    app.add_middleware(AccessMiddleware)
    app.include_router(router)
    original = app.openapi

    def openapi():
        schema = original()
        schemes = schema.setdefault('components', {}).setdefault('securitySchemes', {})
        schemes.update({'IngestKey': {'type': 'http', 'scheme': 'bearer', 'description': 'INGEST_API_KEY; yalnızca veri gönderimi, görev durumu ve hazır olma kontrolü.'},
                        'PanelSession': {'type': 'apiKey', 'in': 'cookie', 'name': COOKIE},
                        'CsrfToken': {'type': 'apiKey', 'in': 'header', 'name': 'X-CSRF-Token', 'description': 'Giriş sonrası GET /auth/session yanıtındaki csrf_token. Değişiklik istekleri için gereklidir.'}})
        for path, methods in schema['paths'].items():
            for method, operation in methods.items():
                if method not in {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}:
                    continue
                if path in {'/health', '/auth/login'}:
                    operation['security'] = []
                    continue
                security = {'PanelSession': []}
                if method.upper() in MUTATIONS:
                    security['CsrfToken'] = []
                operation['security'] = [security]
                if (path in INGEST_PATHS and method == 'post') or (path in {'/ready', '/tasks/{task_id}'} and method == 'get'):
                    operation['security'].append({'IngestKey': []})
        return schema
    app.openapi = openapi
