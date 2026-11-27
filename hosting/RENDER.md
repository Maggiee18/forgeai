# Deploying ForgeAI on Render (free web service)

Hugging Face stopped offering free CPU Docker Spaces to new accounts in mid 2026, so the hosted demo runs on Render's
free web service instead. The same Dockerfile works on both: the container listens on `$PORT` when the host sets it
(Render does) and falls back to 7860 (Hugging Face).

1. Sign in at render.com with GitHub. No credit card is needed for the free plan.
2. **New → Web Service**, pick the `forgeai` repository, branch `main`.
3. Language / runtime: **Docker** (Render finds the `Dockerfile` in the repo root). Instance type: **Free**.
4. **Environment variables**: add `GROQ_API_KEY` (your Groq key) and `FORGE_BACKEND=groq`. Never commit the key.
5. Create the service. The first build takes about 5 to 8 minutes; the app is then live at `https://<name>.onrender.com`.

Measured footprint: about 170 MB of RAM while answering chat requests, well inside the free 512 MB.

What to expect
- The free service sleeps after 15 minutes without traffic. The next visit shows Render's loading page for about a
  minute while the container wakes. This is the host, not a crash.
- The filesystem is ephemeral: builds started on the hosted app work, but are lost when the service restarts. The
  committed demo runs are baked into the image and are always there.
- Without `GROQ_API_KEY` the app still starts, in clearly labelled **mock mode**, so the committed runs stay browsable.
