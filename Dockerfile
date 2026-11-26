# ForgeAI: one container = FastAPI backend + built React dashboard. Port 7860 (Hugging Face Spaces default).
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FORGE_CONFIG=/app/demos/demo_config.yaml FORGE_CACHE=/tmp/forge_cache FORGE_WORK_DIR=/tmp/forge_ws
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY forgeai/ forgeai/
COPY prompts/ prompts/
COPY demos/ demos/
COPY baseline/ baseline/
COPY runs/ runs/
COPY --from=web /web/dist web/dist
# Hugging Face runs containers as a non-root user: everything the app writes goes to /tmp or runs/
RUN useradd -m -u 1000 app && chown -R app /app
USER app
EXPOSE 7860
# GROQ_API_KEY comes from the Space's secrets. Without it the app runs in clearly labelled mock mode.
CMD ["uvicorn", "forgeai.server:app", "--host", "0.0.0.0", "--port", "7860"]
