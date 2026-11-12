import os
import sys
import time
import socket
import threading
import webbrowser
from urllib.request import urlopen

# Pastikan sertifikat SSL tersedia untuk yt-dlp di Android
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

from app import start_flask_server, get_storage_paths

PORT = 5000
LOCAL_URL = f"http://127.0.0.1:{PORT}"

def is_android():
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

def request_android_permissions():
    """Meminta izin penyimpanan runtime pada Android."""
    if not is_android():
        return
    try:
        from android.permissions import request_permissions, Permission
        perms = [
            Permission.INTERNET,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ]
        request_permissions(perms)
    except Exception as e:
        print(f"[Android Permission Info] {e}")

def wait_for_server(timeout=15.0):
    """Menunggu hingga server Flask siap menerima koneksi."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False

# Jalankan dengan Kivy + Native Android WebView
try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.utils import platform

    class YTDownloaderAPKApp(App):
        def build(self):
            self.title = "YT Scraper & Downloader"
            self.webview = None

            # 1. Minta izin penyimpanan Android
            request_android_permissions()

            # 2. Jalankan server Flask di background thread
            self.server_thread = threading.Thread(
                target=start_flask_server,
                kwargs={"host": "127.0.0.1", "port": PORT},
                daemon=True,
            )
            self.server_thread.start()

            # 3. Layout splash sementara menunggu server lokal aktif
            root = BoxLayout(orientation="vertical", padding=24, spacing=16)
            self.status_label = Label(
                text="⚡ Menyiapkan Server Lokal YouTube Scraper & Player...\nMohon tunggu sebentar.",
                halign="center",
                valign="middle",
                font_size="16sp",
            )
            root.add_widget(self.status_label)

            btn_open = Button(
                text="Buka Antarmuka Aplikasi",
                size_hint=(1, None),
                height="48dp",
                background_color=(0.14, 0.39, 0.92, 1),
            )
            btn_open.bind(on_release=lambda *_: self.launch_interface())
            root.add_widget(btn_open)

            Clock.schedule_once(lambda dt: self.check_server_and_launch(), 0.6)
            return root

        def check_server_and_launch(self):
            if wait_for_server(timeout=12.0):
                self.status_label.text = (
                    f"✅ Server Aktif di {LOCAL_URL}\n"
                    f"Folder Unduhan: {get_storage_paths()[0]}"
                )
                self.launch_interface()
            else:
                self.status_label.text = "❌ Gagal memulai server Flask lokal."

        def launch_interface(self):
            if platform == "android":
                self.open_android_native_webview()
            else:
                webbrowser.open(LOCAL_URL)

        def open_android_native_webview(self):
            """Membuka WebView Native Android penuh layar dengan dukungan video/audio HTML5."""
            try:
                from jnius import autoclass
                from android.runnable import run_on_ui_thread

                WebView = autoclass("android.webkit.WebView")
                WebViewClient = autoclass("android.webkit.WebViewClient")
                WebChromeClient = autoclass("android.webkit.WebChromeClient")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity

                @run_on_ui_thread
                def create_webview():
                    webview = WebView(activity)
                    settings = webview.getSettings()
                    settings.setJavaScriptEnabled(True)
                    settings.setDomStorageEnabled(True)
                    settings.setDatabaseEnabled(True)
                    settings.setMediaPlaybackRequiresUserGesture(False)
                    settings.setAllowFileAccess(True)
                    settings.setAllowContentAccess(True)
                    settings.setMixedContentMode(0)  # MIXED_CONTENT_ALWAYS_ALLOW

                    webview.setWebViewClient(WebViewClient())
                    webview.setWebChromeClient(WebChromeClient())
                    activity.setContentView(webview)
                    webview.loadUrl(LOCAL_URL)
                    self.webview = webview

                create_webview()
            except Exception as e:
                self.status_label.text = f"Membuka melalui browser eksternal ({e})"
                webbrowser.open(LOCAL_URL)

    if __name__ == "__main__":
        YTDownloaderAPKApp().run()

except ImportError:
    # Fallback jika dijalankan langsung di PC/Termux tanpa Kivy terinstal
    if __name__ == "__main__":
        print(f"Menjalankan server Flask di {LOCAL_URL} ...")
        server_thread = threading.Thread(
            target=start_flask_server,
            kwargs={"host": "0.0.0.0", "port": PORT},
            daemon=True,
        )
        server_thread.start()
        if wait_for_server():
            print(f"Server siap! Buka {LOCAL_URL} di browser.")
            try:
                webbrowser.open(LOCAL_URL)
            except Exception:
                pass
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)
