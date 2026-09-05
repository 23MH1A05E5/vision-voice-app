import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from gtts import gTTS

from google import genai
from google.genai import types

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
AUDIO_OUT_DIR = os.path.join(BASE_DIR, "static", "generated_audio")
DB_PATH = os.path.join(BASE_DIR, "users.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_OUT_DIR, exist_ok=True)

# Put your real Gemini API key here, OR set an environment variable
# called GEMINI_API_KEY before running the app.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

client = genai.Client(api_key=GEMINI_API_KEY)

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png"}
ALLOWED_AUDIO_EXT = {"wav", "mp3", "m4a", "ogg", "webm"}


# ------------------------------------------------------------
# DATABASE HELPERS
# ------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


# ------------------------------------------------------------
# AUTH ROUTES
# ------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            return render_template("signup.html", error="Username and password are required.")
        if password != confirm:
            return render_template("signup.html", error="Passwords do not match.")
        if len(password) < 4:
            return render_template("signup.html", error="Password must be at least 4 characters.")

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.close()
            return render_template("signup.html", error="That username is already taken.")

        pw_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, pw_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("login", signed_up="1"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid username or password.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("index"))

    signed_up = request.args.get("signed_up")
    return render_template("login.html", signed_up=signed_up)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------
# MAIN PAGE
# ------------------------------------------------------------
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


# ------------------------------------------------------------
# CORE MULTIMODAL PROCESSING
# ------------------------------------------------------------
@app.route("/process", methods=["POST"])
@login_required
def process():
    """
    Accepts:
      - image (required)  -> multipart file field "image"
      - audio (optional)   -> multipart file field "audio"
                               (either a recorded browser clip or an uploaded file)

    Behaviour mirrors the three original notebook scripts:
      - image only              -> text description of the image
      - image + audio question  -> text answer AND a spoken (TTS) answer
    """
    if "image" not in request.files or request.files["image"].filename == "":
        return jsonify({"error": "Please upload an image."}), 400

    image_fs = request.files["image"]
    if not allowed_file(image_fs.filename, ALLOWED_IMAGE_EXT):
        return jsonify({"error": "Image must be .jpg, .jpeg or .png"}), 400

    session_id = uuid.uuid4().hex
    image_filename = secure_filename(f"{session_id}_{image_fs.filename}")
    image_path = os.path.join(UPLOAD_DIR, image_filename)
    image_fs.save(image_path)

    audio_path = None
    audio_fs = request.files.get("audio")
    if audio_fs and audio_fs.filename != "":
        audio_name = audio_fs.filename if "." in audio_fs.filename else audio_fs.filename + ".webm"
        if not allowed_file(audio_name, ALLOWED_AUDIO_EXT):
            return jsonify({"error": "Audio must be .wav, .mp3, .m4a, .ogg or .webm"}), 400
        audio_filename = secure_filename(f"{session_id}_{audio_name}")
        audio_path = os.path.join(UPLOAD_DIR, audio_filename)
        audio_fs.save(audio_path)

    try:
        image = Image.open(image_path)
    except Exception as e:
        return jsonify({"error": f"Could not open image: {e}"}), 400

    try:
        if audio_path:
            # Browser recordings are sent as WebM/Opus. Gemini can accept the
            # WebM audio directly, so no FFmpeg or local audio conversion is needed.
            # Send small browser recordings directly to Gemini as inline bytes.
            # This avoids the Gemini Files API processing state and requires no FFmpeg.
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            # Preserve the actual browser-uploaded MIME type.
            audio_mime = audio_fs.mimetype or "audio/webm"
            if audio_mime == "application/octet-stream":
                ext = audio_name.rsplit(".", 1)[-1].lower()
                audio_mime = {
                    "webm": "audio/webm",
                    "ogg": "audio/ogg",
                    "mp3": "audio/mpeg",
                    "wav": "audio/wav",
                    "m4a": "audio/mp4",
                }.get(ext, "audio/webm")

            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=audio_mime,
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    image,
                    audio_part,
                    "Listen to the audio question and answer the question based on "
                    "the image. Give a short and simple answer.",
                ],
            )
            answer_text = response.text

            tts_filename = f"{session_id}_answer.mp3"
            tts_path = os.path.join(AUDIO_OUT_DIR, tts_filename)
            gTTS(text=answer_text, lang="en").save(tts_path)
            audio_url = url_for("static", filename=f"generated_audio/{tts_filename}")

        else:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[image, "What is shown in this image? Explain in simple words."],
            )
            answer_text = response.text
            audio_url = None

    except Exception as e:
        return jsonify({"error": f"Gemini API error: {e}"}), 500

    return jsonify({
        "answer": answer_text,
        "audio_url": audio_url,
        "image_url": url_for("uploaded_file", filename=image_filename),
    })


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
