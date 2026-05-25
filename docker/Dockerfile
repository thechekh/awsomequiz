# Streamlit app container. Talks to a local Supabase stack (started by the
# Supabase CLI) over host.docker.internal, or to a real Supabase project in prod.
FROM python:3.11-slim

# Pin uv to a known good version; multi-stage copy keeps the final image small.
COPY --from=ghcr.io/astral-sh/uv:0.5.20 /uv /uvx /bin/

# curl for the healthcheck; rm cache to keep image lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy lockfiles first so Docker layer cache survives source-only edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source last.
COPY streamlit_app.py ./
COPY app ./app
COPY pages ./pages
COPY .streamlit ./.streamlit

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["uv", "run", "--no-dev", "streamlit", "run", "streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
