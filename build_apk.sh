#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  Pembantu Kompilasi Proyek APK: YT Scraper & Player"
echo "=========================================================="

if command -v buildozer >/dev/null 2>&1; then
    echo "[+] Buildozer terdeteksi di sistem lokal. Memulai kompilasi APK..."
    buildozer -v android debug
    echo "[✓] Selesai! File APK tersedia di dalam folder ./bin/"
elif command -v docker >/dev/null 2>&1; then
    echo "[+] Menggunakan Docker (kivy/buildozer) untuk kompilasi APK..."
    docker run --rm -v "$PWD":/home/user/hostcwd kivy/buildozer android debug
    echo "[✓] Selesai! File APK tersedia di dalam folder ./bin/"
else
    echo "[!] Buildozer atau Docker belum terinstal di perangkat ini."
    echo "    Silakan ikuti langkah di README.md untuk:"
    echo "    1. Kompilasi otomatis via GitHub Actions (Tanpa instalasi lokal), atau"
    echo "    2. Instalasi Buildozer di Ubuntu/WSL2."
    exit 1
fi
