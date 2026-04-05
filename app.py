import re
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()


def extract_video_id(url: str) -> str | None:
    m = re.search(r"loom\.com/share/([a-f0-9]+)", url)
    return m.group(1) if m else None


async def get_video_info(video_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        # 動画メタデータ取得
        meta = await client.get(f"https://www.loom.com/v1/videos/{video_id}")
        meta.raise_for_status()
        info = meta.json()

        # MP4 URL取得
        resp = await client.post(
            f"https://www.loom.com/api/campaigns/sessions/{video_id}/transcoded-url",
            json={},
        )
        resp.raise_for_status()
        mp4_url = resp.json()["url"]

    return {
        "title": info.get("name", video_id),
        "duration": info.get("video_properties", {}).get("duration", 0),
        "width": info.get("video_properties", {}).get("width", 0),
        "height": info.get("video_properties", {}).get("height", 0),
        "mp4_url": mp4_url,
    }


async def get_transcript(video_id: str) -> str | None:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # 共有ページHTMLからトランスクリプトの署名付きURLを取得
        page = await client.get(f"https://www.loom.com/share/{video_id}")
        page.raise_for_status()

        m = re.search(
            r"(https://cdn\.loom\.com/mediametadata/transcription/[^\"\\\s]+)",
            page.text,
        )
        if not m:
            return None

        # 署名付きURLからトランスクリプトJSON取得
        transcript_url = m.group(1)
        resp = await client.get(transcript_url)
        resp.raise_for_status()
        data = resp.json()

        # フレーズを結合してテキストに変換
        phrases = data.get("phrases", [])
        return "\n\n".join(p["value"] for p in phrases if p.get("value"))


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.get("/api/video")
async def api_video(url: str):
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "無効なLoom URLです"}
    try:
        return await get_video_info(video_id)
    except httpx.HTTPStatusError as e:
        return {"error": f"動画の取得に失敗しました (HTTP {e.response.status_code})"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/transcript")
async def api_transcript(url: str):
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "無効なLoom URLです"}
    try:
        text = await get_transcript(video_id)
        if text is None:
            return {"error": "この動画には文字起こしデータがありません"}
        return {"transcript": text}
    except httpx.HTTPStatusError as e:
        return {"error": f"文字起こしの取得に失敗しました (HTTP {e.response.status_code})"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/download")
async def api_download(url: str, title: str = "loom_video"):
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "無効なLoom URLです"}

    info = await get_video_info(video_id)
    mp4_url = info["mp4_url"]
    filename = re.sub(r'[\\/:*?"<>|]', "_", info["title"]) + ".mp4"

    async def stream():
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", mp4_url) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )


HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Loom動画ダウンローダー</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .container {
    width: 100%;
    max-width: 600px;
    padding: 2rem;
  }
  h1 {
    text-align: center;
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
    background: linear-gradient(135deg, #625df5, #b24bf3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .subtitle {
    text-align: center;
    color: #888;
    margin-bottom: 2rem;
    font-size: 0.9rem;
  }
  .input-group {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
  }
  input[type="text"] {
    flex: 1;
    padding: 0.85rem 1rem;
    border: 2px solid #2a2a3e;
    border-radius: 10px;
    background: #1a1a2e;
    color: #fff;
    font-size: 1rem;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="text"]:focus { border-color: #625df5; }
  input[type="text"]::placeholder { color: #555; }
  button {
    padding: 0.85rem 1.5rem;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #625df5, #8b5cf6);
    color: #fff;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
    white-space: nowrap;
  }
  button:hover { opacity: 0.9; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .result {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 1.5rem;
    display: none;
  }
  .result.show { display: block; }
  .video-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    word-break: break-word;
  }
  .video-meta {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 1rem;
  }
  .video-meta span { margin-right: 1rem; }
  .download-btn {
    display: inline-block;
    width: 100%;
    text-align: center;
    padding: 0.85rem;
    background: linear-gradient(135deg, #10b981, #059669);
    border-radius: 10px;
    color: #fff;
    text-decoration: none;
    font-weight: 600;
    font-size: 1rem;
    transition: opacity 0.2s;
  }
  .download-btn:hover { opacity: 0.9; }
  .btn-row {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .btn-row a, .btn-row button {
    flex: 1;
    text-align: center;
    padding: 0.85rem;
    border-radius: 10px;
    color: #fff;
    text-decoration: none;
    font-weight: 600;
    font-size: 1rem;
    transition: opacity 0.2s;
    cursor: pointer;
    border: none;
  }
  .transcript-btn {
    background: linear-gradient(135deg, #625df5, #8b5cf6);
  }
  .transcript-btn:hover { opacity: 0.9; }
  .transcript-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .transcript-box {
    margin-top: 1rem;
    padding: 1rem;
    background: #12121f;
    border-radius: 10px;
    max-height: 300px;
    overflow-y: auto;
    font-size: 0.9rem;
    line-height: 1.7;
    white-space: pre-wrap;
    display: none;
  }
  .transcript-box.show { display: block; }
  .copy-btn {
    margin-top: 0.5rem;
    padding: 0.5rem 1rem;
    background: #2a2a3e;
    border: 1px solid #3a3a5e;
    border-radius: 8px;
    color: #ccc;
    font-size: 0.8rem;
    cursor: pointer;
    display: none;
  }
  .copy-btn.show { display: inline-block; }
  .copy-btn:hover { background: #3a3a5e; }
  .error {
    background: #2d1a1a;
    border: 1px solid #5c2a2a;
    color: #f87171;
    padding: 1rem;
    border-radius: 10px;
    text-align: center;
    display: none;
  }
  .error.show { display: block; }
  .spinner {
    display: none;
    text-align: center;
    padding: 1rem;
    color: #888;
  }
  .spinner.show { display: block; }
  .spinner::after {
    content: "";
    display: inline-block;
    width: 24px; height: 24px;
    border: 3px solid #333;
    border-top-color: #625df5;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    vertical-align: middle;
    margin-right: 0.5rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <h1>Loom Downloader</h1>
  <p class="subtitle">LoomのURLを貼り付けてMP4でダウンロード</p>
  <div class="input-group">
    <input type="text" id="url" placeholder="https://www.loom.com/share/..." autofocus>
    <button id="btn" onclick="fetchVideo()">取得</button>
  </div>
  <div class="spinner" id="spinner">動画情報を取得中...</div>
  <div class="error" id="error"></div>
  <div class="result" id="result">
    <div class="video-title" id="title"></div>
    <div class="video-meta">
      <span id="resolution"></span>
      <span id="duration"></span>
    </div>
    <div class="btn-row">
      <a class="download-btn" id="dlBtn" href="#">ダウンロード</a>
      <button class="transcript-btn" id="transcriptBtn" onclick="fetchTranscript()">文字起こし</button>
    </div>
    <div class="transcript-box" id="transcriptBox"></div>
    <button class="copy-btn" id="copyBtn" onclick="copyTranscript()">コピー</button>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);

$("url").addEventListener("keydown", e => {
  if (e.key === "Enter") fetchVideo();
});

async function fetchVideo() {
  const url = $("url").value.trim();
  if (!url) return;

  $("btn").disabled = true;
  $("result").classList.remove("show");
  $("error").classList.remove("show");
  $("spinner").classList.add("show");

  try {
    const resp = await fetch("/api/video?url=" + encodeURIComponent(url));
    const data = await resp.json();

    if (data.error) {
      $("error").textContent = data.error;
      $("error").classList.add("show");
      return;
    }

    $("title").textContent = data.title;
    $("resolution").textContent = data.width + " x " + data.height;
    const min = Math.floor(data.duration / 60);
    const sec = data.duration % 60;
    $("duration").textContent = min + "分" + String(sec).padStart(2, "0") + "秒";
    $("dlBtn").href = "/api/download?url=" + encodeURIComponent(url);
    $("result").classList.add("show");
  } catch (e) {
    $("error").textContent = "エラーが発生しました: " + e.message;
    $("error").classList.add("show");
  } finally {
    $("btn").disabled = false;
    $("spinner").classList.remove("show");
  }
}

async function fetchTranscript() {
  const url = $("url").value.trim();
  if (!url) return;

  const btn = $("transcriptBtn");
  btn.disabled = true;
  btn.textContent = "取得中...";
  $("transcriptBox").classList.remove("show");
  $("copyBtn").classList.remove("show");

  try {
    const resp = await fetch("/api/transcript?url=" + encodeURIComponent(url));
    const data = await resp.json();

    if (data.error) {
      $("error").textContent = data.error;
      $("error").classList.add("show");
      return;
    }

    $("transcriptBox").textContent = data.transcript;
    $("transcriptBox").classList.add("show");
    $("copyBtn").classList.add("show");
  } catch (e) {
    $("error").textContent = "エラーが発生しました: " + e.message;
    $("error").classList.add("show");
  } finally {
    btn.disabled = false;
    btn.textContent = "文字起こし";
  }
}

function copyTranscript() {
  const text = $("transcriptBox").textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = $("copyBtn");
    btn.textContent = "コピーしました!";
    setTimeout(() => { btn.textContent = "コピー"; }, 1500);
  });
}
</script>
</body>
</html>
"""
