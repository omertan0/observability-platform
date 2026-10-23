"""Yerel yönetici bilgilerini ve uygulama anahtarını .env içinde hazırlar."""
import argparse
from getpass import getpass
from pathlib import Path
import secrets
from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser(description='Giriş bilgilerini oluştur; mevcut değerleri korur.')
    parser.add_argument('--generate', action='store_true', help='Şifre sorulmadan rastgele yerel şifre üret')
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / '.env'
    existing = dotenv_values(path)
    values = {}
    if not existing.get('PANEL_USERNAME'):
        values['PANEL_USERNAME'] = 'admin'
    if not existing.get('PANEL_PASSWORD'):
        password = secrets.token_urlsafe(24) if args.generate else getpass('Panel şifresi (en az 16 karakter): ')
        if not 16 <= len(password) <= 256:
            parser.error('Şifre 16–256 karakter olmalı.')
        values['PANEL_PASSWORD'] = password
    if not existing.get('INGEST_API_KEY'):
        values['INGEST_API_KEY'] = secrets.token_urlsafe(32)
    for key, value in values.items():
        set_key(path, key, value, quote_mode='always')
    print('Erişim ayarları .env içinde hazırlandı. Kullanıcı adı/şifre: PANEL_USERNAME / PANEL_PASSWORD.')
    print('INGEST_API_KEY veri gönderen uygulamalar içindir. Değerler terminale yazılmadı.')
    print('API açıksa yeniden başlat. .env dosyasını GitHub veya rapora ekleme.')


if __name__ == '__main__':
    main()
