import os
import json
import queue
import shutil
import threading
import urllib.request
import re
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
import yt_dlp

app = Flask(__name__)

def get_storage_paths():
    """Deteksi otomatis direktori penyimpanan Android (APK/Termux) vs Desktop."""
    android_candidates = [
        "/storage/emulated/0/Download/YT-Downloads",
        "/sdcard/Download/YT-Downloads",
    ]
    for candidate in android_candidates:
        parent = os.path.dirname(candidate)
        if os.path.exists(parent) and os.access(parent, os.W_OK):
            return candidate, os.path.join(candidate, "cookies.txt")

    if "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ:
        base_priv = os.environ.get("ANDROID_PRIVATE", os.path.expanduser("~"))
        dl_dir = os.path.join(base_priv, "YT-Downloads")
        return dl_dir, os.path.join(base_priv, "cookies.txt")

    if os.path.exists("/sdcard"):
        return "/sdcard/Download/YT-Downloads", os.path.expanduser("~/ytdl-web/cookies.txt")

    dl_dir = os.path.join(Path.home(), "Downloads", "YT-Downloads")
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    return dl_dir, cookie_path

DOWNLOAD_DIR, COOKIE_PATH = get_storage_paths()
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
progress_queue = queue.Queue()

def has_ffmpeg():
    """Cek apakah binary ffmpeg tersedia di sistem/perangkat."""
    return shutil.which("ffmpeg") is not None

HTML_PAGE = """
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>YouTube Scraper (Mix & Playlist), Player & Downloader</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; padding: 14px; margin: 0; -webkit-tap-highlight-color: transparent; }
    .card { max-width: 800px; margin: 0 auto; background: #131b2e; padding: 18px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); border: 1px solid #1e293b; }
    h2 { margin: 0 0 10px; text-align: center; font-size: 1.25rem; color: #38bdf8; }
    .sub-bar { text-align: center; font-size: 11px; color: #64748b; margin-bottom: 14px; word-break: break-all; }

    /* Navigasi Tab */
    .tab-bar { display: flex; border-bottom: 2px solid #1e293b; margin-bottom: 16px; gap: 6px; }
    .tab-btn { flex: 1; padding: 10px; background: transparent; border: none; color: #94a3b8; font-size: 14px; font-weight: bold; cursor: pointer; border-radius: 8px 8px 0 0; transition: all 0.2s; }
    .tab-btn.active { color: #38bdf8; background: #0b0f19; border-bottom: 3px solid #38bdf8; }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    input[type="text"], select, .btn-primary { width: 100%; box-sizing: border-box; padding: 11px; margin-top: 8px; border-radius: 8px; border: 1px solid #334155; font-size: 14px; }
    input[type="text"], select { background: #0b0f19; color: #fff; }
    button { cursor: pointer; border: none; font-weight: bold; border-radius: 8px; }
    .btn-primary { background: #2563eb; color: #fff; margin-top: 10px; }
    .btn-primary:disabled { background: #475569; cursor: not-allowed; }

    /* Scraper Bar & Tag Filter */
    .scraper-bar { display: grid; grid-template-columns: 2fr 1fr; gap: 8px; margin-bottom: 6px; }
    @media (max-width: 520px) { .scraper-bar { grid-template-columns: 1fr; } }
    .filter-tags { display: flex; gap: 6px; overflow-x: auto; padding: 6px 0 10px 0; }
    .tag-btn { background: #1e293b; color: #cbd5e1; padding: 6px 12px; font-size: 12px; border-radius: 16px; border: 1px solid #334155; white-space: nowrap; }
    .tag-btn:hover { background: #0284c7; color: #fff; border-color: #38bdf8; }

    /* List Item */
    .list-container { max-height: 460px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; margin-top: 12px; padding-right: 4px; }
    .item-card { display: flex; align-items: center; gap: 12px; background: #0b0f19; padding: 10px; border-radius: 8px; border: 1px solid #1e293b; }
    .item-card.active-track { border-color: #38bdf8; background: #0f2347; }
    .item-card img { width: 105px; height: 60px; object-fit: cover; border-radius: 6px; background: #1e293b; flex-shrink: 0; }
    .item-info { flex: 1; min-width: 0; }
    .item-title { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #f1f5f9; }
    .item-meta { font-size: 11px; color: #94a3b8; margin-top: 4px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    
    .badge-type { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
    .badge-mix { background: #7c2d12; color: #fdba74; }
    .badge-playlist { background: #854d0e; color: #fef08a; }
    .badge-video { background: #1e3a8a; color: #bfdbfe; }

    .btn-action-group { display: flex; gap: 5px; flex-shrink: 0; }
    .btn-action { background: #059669; color: white; padding: 6px 10px; font-size: 11px; border-radius: 6px; }
    .btn-action:hover { background: #10b981; }
    .btn-mix { background: #d97706; color: white; padding: 6px 10px; font-size: 11px; border-radius: 6px; }
    .btn-mix:hover { background: #f59e0b; }

    /* Media Player */
    #player-section { margin-top: 14px; padding: 12px; background: #070a12; border-radius: 10px; display: none; border: 1px solid #334155; }
    #video-screen { width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 6px; display: none; margin-bottom: 6px; }
    #audio-screen { width: 100%; height: 38px; display: none; margin-top: 6px; }
    .player-controls { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
    .nav-btn { background: #1e293b; color: #fff; padding: 6px 12px; font-size: 12px; border-radius: 6px; }

    /* Progress Box */
    .progress-box { margin-top: 16px; display: none; background: #0b0f19; padding: 12px; border-radius: 8px; border: 1px solid #1e293b; }
    .progress-container { width: 100%; background-color: #334155; border-radius: 8px; overflow: hidden; height: 14px; margin-top: 6px; }
    .progress-bar { width: 0%; height: 100%; background-color: #10b981; transition: width 0.2s ease; }
    .metrics { display: flex; justify-content: space-between; font-size: 11px; margin-top: 5px; color: #cbd5e1; }
    .status-text { font-size: 11px; color: #94a3b8; margin-top: 5px; word-break: break-all; }
  </style>
</head>
<body>
  <div class="card">
    <h2>⚡ YouTube Scraper (Mix & Playlist) & Player</h2>
    <div class="sub-bar">📂 Lokasi Simpan: {{ download_dir }}</div>

    <!-- Navigasi Tab -->
    <div class="tab-bar">
      <button class="tab-btn active" onclick="switchTab('tab-scraper')">🌐 Scraper & Mix YouTube</button>
      <button class="tab-btn" onclick="switchTab('tab-downloader')">🎵 Player & Downloader</button>
    </div>

    <!-- TAB 1: SCRAPER MIX & PLAYLIST -->
    <div id="tab-scraper" class="tab-content active">
      <div class="scraper-bar">
        <input type="text" id="scrape-query" placeholder="Ketik judul lagu, artis, atau paste link Mix (RD...)" onkeydown="if(event.key==='Enter') executeScrape()">
        <select id="scrape-mode" style="margin-top: 8px;">
          <option value="all_mixed">Semua (Mix, Playlist & Video)</option>
          <option value="playlist_only">Playlist Saja</option>
          <option value="video_only">Video Saja</option>
        </select>
      </div>

      <!-- Quick Mix & Trending Buttons -->
      <div class="filter-tags">
        <button class="tag-btn" onclick="quickScrape('Mix Indonesia Populer', 'all_mixed')">🔀 Mix Populer</button>
        <button class="tag-btn" onclick="quickScrape('Lagu Galau Indonesia Mix', 'all_mixed')">💔 Mix Galau</button>
        <button class="tag-btn" onclick="quickScrape('Kompilasi Dangdut Koplo Mix', 'all_mixed')">💃 Mix Koplo</button>
        <button class="tag-btn" onclick="quickScrape('Top Hits Indonesia 2026', 'playlist_only')">🎧 Playlist Hits</button>
        <button class="tag-btn" onclick="quickScrape('Lofi Hip Hop Radio Beats', 'video_only')">☕ Lofi Live</button>
      </div>

      <button class="btn-primary" id="btn-scrape" onclick="executeScrape()" style="background: #0284c7;">Scrape YouTube</button>
      
      <div id="scrape-status" style="font-size: 12px; color: #94a3b8; margin-top: 8px;"></div>
      <div class="list-container" id="scrape-results"></div>
    </div>

    <!-- TAB 2: DOWNLOADER & MEDIA PLAYER -->
    <div id="tab-downloader" class="tab-content">
      <input type="text" id="url-input" placeholder="Tempel URL Video / Playlist / Mix YouTube (cth: https://youtube.com/playlist?list=RD...)">
      <button class="btn-primary" id="btn-load" onclick="fetchInfo()">Muat Playlist / Mix</button>

      <!-- Player Section -->
      <div id="player-section">
        <div id="player-title" style="font-size: 12px; font-weight: 600; color: #38bdf8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 6px;">
          Media Player Siap
        </div>
        <video id="video-screen" controls playsinline></video>
        <audio id="audio-screen" controls></audio>
        
        <div class="player-controls">
          <div style="display: flex; gap: 6px;">
            <button class="nav-btn" onclick="playPrevious()">⏮ Sebelumnya</button>
            <button class="nav-btn" onclick="playNext()">⏭ Selanjutnya</button>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; font-size: 12px;">
            <label>Mode:</label>
            <select id="playback-mode" onchange="changePlaybackMode()" style="width: auto; padding: 3px 6px; margin: 0; font-size: 12px;">
              <option value="audio">Audio Saja</option>
              <option value="video">Video</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Playlist / Mix Container -->
      <div id="playlist-panel" style="display: none; margin-top: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; background: #0b0f19; padding: 8px 12px; border-radius: 8px; font-size: 12px; border: 1px solid #1e293b;">
          <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
            <input type="checkbox" id="select-all" checked onchange="toggleSelectAll(this)">
            <b>Pilih Semua</b>
          </label>
          <div>
            <button onclick="playIndex(0)" class="btn-action">▶ Putar Semua</button>
            <span id="item-count" style="color: #94a3b8; margin-left: 6px;">0 item</span>
          </div>
        </div>

        <div class="list-container" id="video-list"></div>

        <label style="font-size: 12px; margin-top: 12px; display: block;">Kualitas Unduhan:</label>
        <select id="quality">
          <optgroup label="Video (MP4)">
            <option value="1080p">Video 1080p Full HD</option>
            <option value="720p" selected>Video 720p HD</option>
            <option value="480p">Video 480p</option>
          </optgroup>
          <optgroup label="Audio Saja (MP3 / M4A)">
            <option value="mp3_320">Audio MP3/M4A - 320 kbps</option>
            <option value="mp3_192">Audio MP3/M4A - 192 kbps</option>
          </optgroup>
        </select>

        <button class="btn-primary" id="download-btn" onclick="startDownload()" style="background: #16a34a;">Unduh Media Terpilih</button>
      </div>

      <!-- Progress Realtime -->
      <div class="progress-box" id="progress-box">
        <div id="dl-title" style="font-size: 12px; font-weight: 600;">Menyiapkan proses...</div>
        <div class="progress-container">
          <div class="progress-bar" id="progress-bar"></div>
        </div>
        <div class="metrics">
          <span id="percent-text">0%</span>
          <span id="speed-text">--</span>
          <span id="eta-text">ETA: --</span>
        </div>
        <div class="status-text" id="status-detail">Menunggu server...</div>
      </div>
    </div>
  </div>

  <script>
    let playlistItems = [];
    let currentIndex = -1;
    let evtSource = null;

    const videoScreen = document.getElementById('video-screen');
    const audioScreen = document.getElementById('audio-screen');
    const playerSection = document.getElementById('player-section');
    const playerTitle = document.getElementById('player-title');
    const playbackMode = document.getElementById('playback-mode');

    videoScreen.addEventListener('ended', playNext);
    audioScreen.addEventListener('ended', playNext);

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      if (tabId === 'tab-scraper') {
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
      } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
      }
      document.getElementById(tabId).classList.add('active');
    }

    function formatDuration(sec) {
      if (!sec) return '--:--';
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    function quickScrape(query, mode) {
      document.getElementById('scrape-query').value = query;
      document.getElementById('scrape-mode').value = mode;
      executeScrape();
    }

    // TAB 1: SCRAPER UTUH DENGAN DUKUNGAN MIX
    async function executeScrape() {
      const query = document.getElementById('scrape-query').value.trim();
      const mode = document.getElementById('scrape-mode').value;
      const status = document.getElementById('scrape-status');
      const container = document.getElementById('scrape-results');
      const btn = document.getElementById('btn-scrape');

      if (!query) {
        alert("Masukkan kata kunci atau link Mix/Playlist!");
        return;
      }

      btn.disabled = true;
      status.innerText = "⏳ Sedang melakukan scraping data YouTube & Mix...";
      container.innerHTML = "";

      try {
        const res = await fetch('/scrape_youtube', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, mode })
        });
        const data = await res.json();

        if (data.error) {
          status.innerText = "❌ Scraper Error: " + data.error;
          return;
        }

        status.innerText = `✅ Ditemukan ${data.results.length} hasil (termasuk Mix & Playlist).`;

        data.results.forEach(item => {
          const card = document.createElement('div');
          card.className = 'item-card';

          let badgeClass = 'badge-video';
          let badgeText = 'VIDEO';
          if (item.type === 'mix') {
            badgeClass = 'badge-mix';
            badgeText = '🔀 YT MIX';
          } else if (item.type === 'playlist') {
            badgeClass = 'badge-playlist';
            badgeText = '📁 PLAYLIST';
          }

          let mixBtnHtml = '';
          if (item.type === 'video' && item.video_id) {
            const mixUrl = `https://www.youtube.com/watch?v=${item.video_id}&list=RD${item.video_id}`;
            mixBtnHtml = `<button class="btn-mix" onclick="transferToPlayer('${mixUrl}')" title="Buat playlist otomatis berdasarkan lagu ini">🔀 Buka Mix</button>`;
          }

          card.innerHTML = `
            <img src="${item.thumbnail || ''}" onerror="this.src='https://placehold.co/105x60/1e293b/fff?text=No+Img'">
            <div class="item-info">
              <div class="item-title" title="${item.title}">${item.title}</div>
              <div class="item-meta">
                <span class="badge-type ${badgeClass}">${badgeText}</span>
                <span>👤 ${item.channel || 'YouTube'}</span>
                ${item.duration ? `<span>⏱ ${formatDuration(item.duration)}</span>` : ''}
              </div>
            </div>
            <div class="btn-action-group">
              ${mixBtnHtml}
              <button class="btn-action" onclick="transferToPlayer('${item.url}')">Buka ➡</button>
            </div>
          `;
          container.appendChild(card);
        });
      } catch (e) {
        status.innerText = "❌ Terjadi kesalahan pada scraper.";
      } finally {
        btn.disabled = false;
      }
    }

    function transferToPlayer(url) {
      document.getElementById('url-input').value = url;
      switchTab('tab-downloader');
      fetchInfo();
    }

    // TAB 2: EKSTRAKSI PLAYLIST / MIX LENGKAP
    async function fetchInfo() {
      const url = document.getElementById('url-input').value.trim();
      const btn = document.getElementById('btn-load');
      const panel = document.getElementById('playlist-panel');
      const list = document.getElementById('video-list');
      const countLabel = document.getElementById('item-count');

      if (!url) {
        alert("Masukkan URL YouTube atau Mix terlebih dahulu!");
        return;
      }

      btn.disabled = true;
      btn.innerText = "Mengekstrak list...";
      panel.style.display = "none";
      list.innerHTML = "";

      try {
        const res = await fetch('/get_info', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
        const data = await res.json();

        if (data.error) {
          alert("Gagal memuat: " + data.error);
          return;
        }

        playlistItems = data.items;
        countLabel.innerText = `${playlistItems.length} item`;

        playlistItems.forEach((item, idx) => {
          const div = document.createElement('div');
          div.className = 'item-card';
          div.id = 'track-' + idx;
          div.innerHTML = `
            <input type="checkbox" class="video-checkbox" value="${item.url}" checked>
            <img src="${item.thumbnail || ''}" onclick="playIndex(${idx})" onerror="this.src='https://placehold.co/105x60/1e293b/fff?text=No+Img'">
            <div class="item-info" onclick="playIndex(${idx})">
              <div class="item-title" title="${item.title}">${idx + 1}. ${item.title}</div>
              <div class="item-meta">
                <span>⏱ ${formatDuration(item.duration)}</span>
                <button class="btn-action" onclick="event.stopPropagation(); playIndex(${idx})">▶ Putar</button>
              </div>
            </div>
          `;
          list.appendChild(div);
        });

        document.getElementById('select-all').checked = true;
        panel.style.display = "block";
      } catch (err) {
        alert("Gagal memuat playlist/mix.");
      } finally {
        btn.disabled = false;
        btn.innerText = "Muat Playlist / Mix";
      }
    }

    // MEDIA PLAYER CONTROLS
    function playIndex(index) {
      if (!playlistItems || index < 0 || index >= playlistItems.length) return;
      currentIndex = index;

      const item = playlistItems[currentIndex];
      playerSection.style.display = 'block';
      playerTitle.innerText = `Memutar [${currentIndex + 1}/${playlistItems.length}]: ${item.title}`;

      document.querySelectorAll('#video-list .item-card').forEach(el => el.classList.remove('active-track'));
      const activeEl = document.getElementById('track-' + currentIndex);
      if (activeEl) {
        activeEl.classList.add('active-track');
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }

      const streamUrl = `/stream_media?url=${encodeURIComponent(item.url)}&mode=${playbackMode.value}`;

      if (playbackMode.value === 'video') {
        audioScreen.pause();
        audioScreen.style.display = 'none';
        videoScreen.style.display = 'block';
        videoScreen.src = streamUrl;
        videoScreen.play().catch(e => console.log('Autoplay ditahan browser'));
      } else {
        videoScreen.pause();
        videoScreen.style.display = 'none';
        audioScreen.style.display = 'block';
        audioScreen.src = streamUrl;
        audioScreen.play().catch(e => console.log('Autoplay ditahan browser'));
      }
    }

    function playNext() {
      if (currentIndex + 1 < playlistItems.length) playIndex(currentIndex + 1);
      else playerTitle.innerText = "Playlist selesai diputar.";
    }

    function playPrevious() {
      if (currentIndex - 1 >= 0) playIndex(currentIndex - 1);
    }

    function changePlaybackMode() {
      if (currentIndex >= 0) playIndex(currentIndex);
    }

    function toggleSelectAll(master) {
      document.querySelectorAll('.video-checkbox').forEach(cb => cb.checked = master.checked);
    }

    // DOWNLOAD REALTIME
    function connectSSE() {
      if (evtSource) return;
      evtSource = new EventSource('/stream');
      evtSource.onmessage = function(e) {
        const data = JSON.parse(e.data);
        const progressBar = document.getElementById('progress-bar');
        const percentText = document.getElementById('percent-text');
        const speedText = document.getElementById('speed-text');
        const etaText = document.getElementById('eta-text');
        const statusDetail = document.getElementById('status-detail');
        const dlTitle = document.getElementById('dl-title');
        const dlBtn = document.getElementById('download-btn');

        if (data.status === 'downloading') {
          dlTitle.innerText = data.filename || "Mengunduh...";
          progressBar.style.width = data.percent + '%';
          percentText.innerText = data.percent.toFixed(1) + '%';
          speedText.innerText = data.speed || '--';
          etaText.innerText = 'ETA: ' + (data.eta || '--');
          statusDetail.innerText = 'Mengunduh stream...';
        } else if (data.status === 'finished_file') {
          progressBar.style.width = '100%';
          statusDetail.innerText = 'Memproses media...';
        } else if (data.status === 'done') {
          progressBar.style.width = '100%';
          percentText.innerText = '100%';
          statusDetail.innerText = '✅ Semua file selesai diunduh ke ' + (data.dir || 'folder unduhan') + '!';
          dlBtn.disabled = false;
        } else if (data.status === 'error') {
          statusDetail.innerText = '❌ Gagal: ' + data.message;
          dlBtn.disabled = false;
        }
      };
    }

    async function startDownload() {
      const checkboxes = document.querySelectorAll('.video-checkbox:checked');
      const selectedUrls = Array.from(checkboxes).map(cb => cb.value);
      const quality = document.getElementById('quality').value;
      const dlBtn = document.getElementById('download-btn');
      const progressBox = document.getElementById('progress-box');

      if (selectedUrls.length === 0) {
        alert("Pilih minimal satu media untuk diunduh!");
        return;
      }

      dlBtn.disabled = true;
      progressBox.style.display = 'block';
      document.getElementById('progress-bar').style.width = '0%';
      document.getElementById('percent-text').innerText = '0%';
      document.getElementById('status-detail').innerText = `Memulai download ${selectedUrls.length} file...`;

      connectSSE();

      try {
        await fetch('/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ urls: selectedUrls, quality })
        });
      } catch (err) {
        alert("Gagal koneksi ke server");
        dlBtn.disabled = false;
      }
    }
  </script>
</body>
</html>
"""

def progress_hook(d):
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        percent = (downloaded / total * 100) if total > 0 else 0
        
        filename = os.path.basename(d.get('filename', 'Media'))
        speed = d.get('speed')
        speed_str = f"{(speed / 1024 / 1024):.2f} MB/s" if speed else "--"
        eta = d.get('eta')
        eta_str = f"{eta}s" if eta else "--"

        progress_queue.put({
            'status': 'downloading',
            'filename': filename,
            'percent': round(percent, 2),
            'speed': speed_str,
            'eta': eta_str
        })
    elif d['status'] == 'finished':
        progress_queue.put({'status': 'finished_file'})

def build_ydl_quality_opts(quality_choice):
    opts = {}
    ffmpeg_available = has_ffmpeg()

    if quality_choice.startswith('mp3_'):
        bitrate = quality_choice.split('_')[1]
        if ffmpeg_available:
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                }],
            })
        else:
            # Fallback Android tanpa binary FFmpeg: unduh stream audio m4a/webm langsung
            opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    else:
        res = quality_choice.replace('p', '')
        if ffmpeg_available:
            fmt_string = f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[height<={res}][ext=mp4]/best[height<={res}]/best"
            opts.update({
                'format': fmt_string,
                'merge_output_format': 'mp4',
            })
        else:
            # Fallback Android tanpa FFmpeg: pilih single-file progressive MP4
            fmt_string = f"best[height<={res}][ext=mp4]/best[ext=mp4]/best"
            opts.update({
                'format': fmt_string,
            })
    return opts

def run_batch_download(urls, quality_choice):
    global DOWNLOAD_DIR, COOKIE_PATH
    DOWNLOAD_DIR, COOKIE_PATH = get_storage_paths()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'nocheckcertificate': True,
    }

    if os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    ydl_opts.update(build_ydl_quality_opts(quality_choice))

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(urls)
        progress_queue.put({'status': 'done', 'dir': DOWNLOAD_DIR})
    except Exception as e:
        progress_queue.put({'status': 'error', 'message': str(e)})

@app.route('/')
def home():
    dl_dir, _ = get_storage_paths()
    return render_template_string(HTML_PAGE, download_dir=dl_dir)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'download_dir': DOWNLOAD_DIR})

# ENDPOINT: SCRAPER DENGAN DETEKSI MIX & PLAYLIST KHUSUS
@app.route('/scrape_youtube', methods=['POST'])
def scrape_youtube():
    data = request.get_json()
    query = data.get('query', '').strip()
    mode = data.get('mode', 'all_mixed')

    if not query:
        return jsonify({'results': []})

    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'ignoreerrors': True,
        'nocheckcertificate': True,
    }
    if os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    is_direct_url = query.startswith('http://') or query.startswith('https://')
    if is_direct_url:
        target = query
    elif mode == 'playlist_only':
        target = f"ytsearch15:{query} playlist"
    elif mode == 'video_only':
        target = f"ytsearch15:{query}"
    else:
        target = f"ytsearch15:{query} mix"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=False)
            results = []

            entries = info.get('entries', []) if 'entries' in info else [info]

            for entry in entries:
                if not entry:
                    continue

                thumb = entry.get('thumbnail')
                if not thumb and entry.get('thumbnails'):
                    thumb = entry['thumbnails'][0].get('url')

                raw_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                entry_id = entry.get('id', '')

                is_mix = 'list=RD' in raw_url or 'list=RD' in query or (entry.get('title') and 'mix' in entry.get('title').lower())
                is_playlist = (
                    entry.get('_type') == 'playlist' or 
                    'entries' in entry or 
                    'playlist' in raw_url.lower() or 
                    'list=' in raw_url.lower()
                )

                if is_mix:
                    media_type = 'mix'
                elif is_playlist:
                    media_type = 'playlist'
                else:
                    media_type = 'video'

                results.append({
                    'title': entry.get('title', 'Unknown Title'),
                    'url': raw_url,
                    'video_id': entry_id,
                    'thumbnail': thumb,
                    'channel': entry.get('uploader') or entry.get('channel') or entry.get('uploader_id') or 'YouTube',
                    'duration': entry.get('duration'),
                    'type': media_type
                })

            return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/stream_media')
def stream_media():
    media_url = request.args.get('url')
    mode = request.args.get('mode', 'audio')

    if not media_url:
        return "URL diperlukan", 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    if mode == 'video':
        ydl_opts['format'] = 'best[ext=mp4]/best/b'
    else:
        ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'

    if os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(media_url, download=False)
            stream_url = info.get('url')
            http_headers = info.get('http_headers', {})

            if not stream_url:
                return "Stream tidak ditemukan", 404

            req = urllib.request.Request(stream_url, headers=http_headers)
            response_stream = urllib.request.urlopen(req)

            def generate():
                while True:
                    chunk = response_stream.read(1024 * 64)
                    if not chunk:
                        break
                    yield chunk

            ext = info.get('ext', 'mp4')
            mime_type = f'video/{ext}' if mode == 'video' else 'audio/mp4'
            return Response(stream_with_context(generate()), content_type=mime_type)

    except Exception as e:
        return f"Error: {e}", 500

@app.route('/get_info', methods=['POST'])
def get_info():
    """Mendukung penguraian YouTube Mix (RD...) hingga 50 item secara otomatis."""
    data = request.get_json()
    url = data.get('url', '')

    ydl_opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'playlistend': 50,
    }
    if os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            items = []
            
            if 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if not entry:
                        continue
                    title = entry.get('title', '')
                    if title in ['[Deleted video]', '[Private video]', None]:
                        continue

                    thumb = entry.get('thumbnail')
                    if not thumb and entry.get('thumbnails'):
                        thumb = entry['thumbnails'][0].get('url')

                    items.append({
                        'title': title,
                        'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'thumbnail': thumb,
                        'duration': entry.get('duration')
                    })
            else:
                thumb = info.get('thumbnail')
                items.append({
                    'title': info.get('title', 'Unknown Title'),
                    'url': url,
                    'thumbnail': thumb,
                    'duration': info.get('duration')
                })

            return jsonify({'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    urls = data.get('urls', [])
    quality = data.get('quality', '720p')

    thread = threading.Thread(target=run_batch_download, args=(urls, quality), daemon=True)
    thread.start()

    return jsonify({"status": "started"})

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            data = progress_queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            if data.get('status') in ['done', 'error']:
                break
    return Response(event_stream(), mimetype="text/event-stream")

def start_flask_server(host='127.0.0.1', port=5000):
    app.run(host=host, port=port, threaded=True, use_reloader=False)

if __name__ == '__main__':
    start_flask_server(host='0.0.0.0', port=5000)
