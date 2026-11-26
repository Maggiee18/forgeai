# Deploying ForgeAI on a free Hugging Face Space

ForgeAI ships as one Docker image: FastAPI serves the API and the built React dashboard on port 7860.

1. Create a Space at huggingface.co/new-space: SDK **Docker**, template **Blank**, hardware **CPU basic (free)**.
2. Push this repository to the Space (or add the Space as a git remote and `git push space main`).
3. Make sure the Space's `README.md` starts with this front matter (the repository's own README already does):

```yaml
---
title: ForgeAI
emoji: 🛠️
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---
```

4. Settings → Variables and secrets → **New secret** `GROQ_API_KEY`. Never commit the key.
5. The Space builds the image (about 4 minutes) and opens on the Overview page with the committed demo runs.

Without the secret the app still starts, in clearly labelled **mock mode**: the committed runs stay browsable, and new
builds run on the deterministic offline stand-in instead of a real model.

Notes
- Free CPU Spaces sleep after inactivity; the first request after sleep takes about 30 seconds.
- Builds made on the Space are written inside the container and are lost when it restarts. Commit runs you want to keep.
- Embeddings use WordLlama, which ships inside its pip package, so nothing is downloaded at runtime.

## Local Docker
```bash
docker build -t forgeai .
docker run -p 7860:7860 -e GROQ_API_KEY=$GROQ_API_KEY forgeai
# open http://localhost:7860
```
