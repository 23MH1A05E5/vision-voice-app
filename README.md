# Vision & Voice — Multimodal Flask App

Combines your three notebook scripts (image+audio→text+speech, image+audio→text,
image-only→text) into one web app with:

- **Login / signup** (SQLite + hashed passwords, no third-party auth needed)
- **Image upload** with preview
- **One-click audio recording** in the browser (no file needed — uses the mic directly)
- Sends image (+ optional recorded question) to Gemini, shows the text answer,
  and — when you asked a spoken question — plays back a spoken (TTS) answer

## 1. File layout

```
multimodal_app/
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── signup.html
│   └── index.html
├── static/
│   ├── style.css
│   ├── script.js
│   └── generated_audio/   (created automatically)
└── uploads/                (created automatically)
```

Keep this folder structure exactly as-is — Flask looks for `templates/` and
`static/` next to `app.py`.

## 2. Install dependencies

Open a terminal / command prompt (not IDLE itself — IDLE has no terminal, see
step 4 for how to actually run it) in the `multimodal_app` folder and run:

```
pip install -r requirements.txt
```

`pydub` (used to convert browser-recorded audio to `.wav`) also needs
**ffmpeg** installed on your system and available on PATH:
- Windows: download from https://ffmpeg.org/download.html, unzip, add the
  `bin` folder to your PATH, then restart your terminal.
- Mac: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

If ffmpeg isn't installed, recording still works but Gemini may occasionally
reject the raw `.webm` clip — uploading a `.wav`/`.mp3` file instead of
recording will always work regardless.

## 3. Add your Gemini API key

Open `app.py` and replace:

```python
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "your_api_key")
```

with your real key, e.g. `"AIzaSy..."` — or, better, set it as an environment
variable instead of hardcoding it:

```
# Windows (cmd)
set GEMINI_API_KEY=AIzaSy...

# Windows (PowerShell)
$env:GEMINI_API_KEY="AIzaSy..."

# Mac/Linux
export GEMINI_API_KEY=AIzaSy...
```

## 4. Run it from IDLE

1. Open `app.py` in IDLE (File → Open).
2. Press **F5** (Run → Run Module).
3. IDLE's Shell window will print something like:
   ```
    * Running on http://127.0.0.1:5000
    * Running on http://0.0.0.0:5000
   ```
4. Open **http://127.0.0.1:5000** in your browser. Sign up, log in, and use it.

Leave the IDLE shell window open — closing it stops the server.

## 5. Give other people a working URL

Running on `127.0.0.1` only works on your own computer. To let others use it
too, you have two options:

### Option A — same Wi-Fi / LAN (quick, free, no signup)
1. Find your computer's local IP (Windows: `ipconfig`, Mac/Linux: `ifconfig`
   or `ip addr`) — something like `192.168.1.23`.
2. Since `app.run(host="0.0.0.0", ...)` is already set in `app.py`, anyone on
   the **same network** can open `http://192.168.1.23:5000` in their browser.
3. **Note:** browsers only allow microphone access (`getUserMedia`) on
   `https://` or on `localhost` — a plain `http://192.168.1.23:5000` link
   will let people upload images and use image-only mode, but most browsers
   will **block the record button** for security. Use Option B for a proper
   HTTPS URL that works fully, including recording, from anywhere.

### Option B — a public HTTPS URL anyone can use (recommended)
Use a free tunnel like **ngrok**:

1. Sign up at https://ngrok.com and download ngrok for your OS.
2. Authenticate once: `ngrok config add-authtoken <your token>`
3. With `app.py` still running (step 4 above), open a **second** terminal and run:
   ```
   ngrok http 5000
   ```
4. ngrok prints a public URL like `https://a1b2-203-0-113-5.ngrok-free.app`.
   Share that link — it's HTTPS, so the record button will work for anyone,
   anywhere, as long as your computer and `app.py` stay running.

For something that stays online after you close your laptop, deploy `app.py`
to a host like Render, Railway, PythonAnywhere, or a small VPS instead — the
code doesn't change, only where it runs.

## 6. How the pieces map to your original scripts

| Original script | Where it lives now |
|---|---|
| Image + audio → text + TTS audio | `/process` route, when an audio file is attached |
| Image + audio → text only | Same route/model call; TTS is just added on top |
| Image only → text | `/process` route, when no audio is attached |

All three now share one Gemini call path in `app.py`, so you only maintain
one place instead of three separate scripts.
