# Proyek APK Android Python: YouTube Scraper (Mix & Playlist), Player & Downloader

Proyek ini mengemas skrip aplikasi **YouTube Scraper (Mix & Playlist), Media Player, dan Batch Downloader (`app.py`)** menjadi aplikasi **Android (`.apk`)** menggunakan ekosistem **Kivy / Python-for-Android (`Buildozer`)** dengan tampilan **Native Android WebView**.

## Struktur Direktori Proyek

| Nama File / Folder | Fungsi Utama |
| :--- | :--- |
| `main.py` | Titik masuk (*entry point*) aplikasi Android yang meminta izin penyimpanan (`READ/WRITE_EXTERNAL_STORAGE`), menjalankan server Flask di *background thread* (`127.0.0.1:5000`), dan merender UI langsung di dalam *Native Android WebView*. |
| `app.py` | Modul inti Flask & `yt-dlp` yang telah disesuaikan untuk sistem penyimpanan Android (`/storage/emulated/0/Download/YT-Downloads`), sertifikat SSL (`certifi`), dan *fallback* unduhan otomatis apabila *binary* `ffmpeg` tidak tersedia di perangkat. |
| `buildozer.spec` | Konfigurasi kompilasi APK (Target API 33, arsitektur `arm64-v8a` & `armeabi-v7a`, izin jaringan & penyimpanan, serta `android.uses_cleartext_traffic = True`). |
| `.github/workflows/build-apk.yml` | Workflow **GitHub Actions** untuk mengompilasi `.apk` secara gratis di *cloud* tanpa perlu menginstal Android SDK/NDK di komputer lokal. |
| `Dockerfile` & `build_apk.sh` | Alat bantu kompilasi lokal menggunakan kontainer Docker `kivy/buildozer` atau Linux/WSL2. |
| `assets/icon.png` & `assets/presplash.png` | Aset grafis ikon aplikasi dan layar pembuka (*splash screen*) saat APK dijalankan. |

## Cara Mengompilasi Menjadi File `.apk`

Kompilasi kode Python menjadi `.apk` memerlukan Android SDK, Android NDK (`25b`), dan kompiler silang `python-for-android`. Pilih salah satu dari **3 metode** berikut sesuai perangkat yang Anda gunakan:

### Metode 1: Kompilasi Otomatis via GitHub Actions (Paling Mudah, Bisa dari HP / Windows / Mac)
Anda tidak perlu menginstal SDK/NDK berukuran besar di komputer atau HP:
1. Buat repositori baru di akun GitHub Anda.
2. Unggah seluruh isi folder proyek ini (termasuk folder `.github/workflows/build-apk.yml`) ke repositori tersebut.
3. Buka tab **Actions** di repositori GitHub Anda, lalu klik workflow **Build Android APK (Buildozer)**.
4. Tunggu proses *build* selesai (sekitar 12–18 menit pada *run* pertama), lalu unduh file **`ytscraperplayer-debug-apk`** pada bagian **Artifacts**.

### Metode 2: Kompilasi Menggunakan Docker (Linux / Windows WSL2 / macOS)
Jika komputer Anda sudah terinstal Docker, jalankan satu perintah berikut di terminal pada folder proyek:
```bash
docker run --rm -v "$PWD":/home/user/hostcwd kivy/buildozer android debug
```
Atau jalankan skrip pembantu:
```bash
chmod +x build_apk.sh
./build_apk.sh
```
File `.apk` hasil kompilasi akan muncul di dalam folder `bin/ytscraperplayer-1.0.0-arm64-v8a_armeabi-v7a-debug.apk`.

### Metode 3: Kompilasi Langsung di Ubuntu / Debian / WSL2
1. Instal paket dependensi sistem dan Buildozer:
   ```bash
   sudo apt update
   sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   pip3 install --upgrade buildozer cython==0.29.36
   ```
2. Jalankan kompilasi APK di dalam direktori proyek:
   ```bash
   buildozer -v android debug
   ```
3. Ambil file `.apk` di dalam direktori `bin/`.

## Cara Menjalankan Langsung di Termux (Android) atau Desktop Tanpa Build APK
Jika Anda ingin langsung menjalankan aplikasinya di Termux Android atau PC:
```bash
pip install -r requirements.txt
python main.py
```
Aplikasi akan otomatis membuka antarmuka di `http://127.0.0.1:5000` dan menyimpan hasil unduhan di `/storage/emulated/0/Download/YT-Downloads` (Android) atau `~/Downloads/YT-Downloads` (PC).
