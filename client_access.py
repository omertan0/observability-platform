"""Komut satırı istemcileri için yerel .env erişim ayarları; sırları yazdırmaz."""
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
from threading import Lock
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener
from urllib.parse import urlsplit

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Anahtar veya oturum başka adrese yönlendirmeyle taşınmaz.
        return None


def no_redirect_open(request, timeout=15):
    return build_opener(NoRedirect()).open(request, timeout=timeout)


def ingestion_headers():
    key = os.getenv('INGEST_API_KEY', '')
    if len(key) < 32:
        raise ValueError('INGEST_API_KEY hazır değil; scripts/setup_access.py çalıştırılmalı.')
    return {'Authorization': 'Bearer ' + key}


class AdminClient:
    """Yerel işlevsel testlerde gerçek giriş/CSRF kullanır; yetkiyi atlamaz."""
    def __init__(self, base_url='http://127.0.0.1:8000'):
        self.base_url = base_url.rstrip('/')
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies), NoRedirect())
        self.csrf = None
        self.lock = Lock()

    def login(self):
        with self.lock:
            if self.csrf:
                return
            payload = {'username': os.getenv('PANEL_USERNAME', 'admin'), 'password': os.getenv('PANEL_PASSWORD', '')}
            request = Request(self.base_url + '/auth/login', data=json.dumps(payload).encode(), method='POST',
                              headers={'Content-Type': 'application/json', 'X-Requested-With': 'observability'})
            with self.opener.open(request, timeout=15) as response:
                self.csrf = json.load(response)['csrf_token']

    def open(self, request, timeout=15):
        if isinstance(request, str):
            request = Request(request)
        origin = lambda url: (urlsplit(url).scheme, urlsplit(url).netloc)
        if origin(request.full_url) != origin(self.base_url):
            raise ValueError('Yönetici istemcisi yalnızca kendi API adresini kullanır.')
        self.login()
        if request.get_method() in {'POST', 'PATCH', 'PUT', 'DELETE'}:
            request.add_header('X-CSRF-Token', self.csrf)
        return self.opener.open(request, timeout=timeout)

    def logout(self):
        if self.csrf:
            request = Request(self.base_url + '/auth/logout', method='POST', headers={'X-CSRF-Token': self.csrf})
            with self.opener.open(request, timeout=10):
                pass
            self.cookies.clear()
            self.csrf = None
