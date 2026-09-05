# Vision & Voice — Free Render Deployment

This version is prepared for deployment as a Flask web service on Render's Free plan.

## Features
- Image + optional browser voice question
- Gemini multimodal answer
- gTTS spoken answer
- No FFmpeg
- Browser recordings are sent to Gemini as inline audio bytes
- Uses `PORT` for hosted environments
- Uses Gunicorn in production

## Deploy
1. Create a GitHub repository and upload the contents of this folder.
2. In Render, choose **New → Web Service** and connect the repository.
3. Render can use `render.yaml`, or enter:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Plan: `Free`
4. Add environment variables:
   - `GEMINI_API_KEY` = your Gemini API key
   - `FLASK_SECRET_KEY` = a long random secret (Render can generate this)
5. Deploy and open the generated `https://...onrender.com` URL.

## Important
- Do NOT put the Gemini API key in JavaScript or HTML.
- Browser microphone access works over HTTPS, which the Render URL provides.
- Render Free services can sleep after inactivity and may take about a minute to wake.
- SQLite data and generated/uploaded files are on an ephemeral filesystem on Render Free. This means user accounts can be lost after a restart/redeploy. For a class/demo project this is acceptable; use a persistent database for a production app.
- Inline audio is intended for small requests; keep image + audio comfortably below 20 MB.
