[app]

# Nama Aplikasi di Android
title = YT Scraper & Player

# Nama paket
package.name = ytscraperplayer

# Domain paket (untuk identifikasi unik APK)
package.domain = org.pythonapp

# Direktori kode sumber utama (tempat main.py dan app.py berada)
source.dir = .

# Ekstensi file yang disertakan ke dalam APK
source.include_exts = py,png,jpg,kv,atlas,txt,json,html,css,js

# Versi aplikasi
version = 1.0.0

# Daftar dependensi Python (python-for-android recipes + paket pure-python)
requirements = python3,kivy==2.3.0,pyjnius,android,openssl,certifi,urllib3,idna,charset-normalizer,requests,click,itsdangerous,jinja2,markupsafe,werkzeug,blinker,flask,yt-dlp

# Ikon dan layar pembuka (splash screen)
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
presplash.color = #0B0F19

# Orientasi layar yang didukung
orientation = portrait,landscape

# Layanan khusus
fullscreen = 0

# Konfigurasi spesifik Android
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,FOREGROUND_SERVICE

# API target Android (Android 13 / API 33 sesuai standar modern)
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True

# Izinkan trafik HTTP lokal (127.0.0.1:5000) di dalam Android WebView
android.uses_cleartext_traffic = True

# Arsitektur prosesor perangkat Android modern (64-bit & 32-bit ARM)
android.archs = arm64-v8a, armeabi-v7a

# Izinkan pencadangan otomatis
android.allow_backup = True

# Mode penyimpanan
android.private_storage = True

[buildozer]

# Level log (0 = error saja, 1 = info, 2 = debug penuh)
log_level = 2

# Peringatan jika dijalankan sebagai root
warn_on_root = 1
