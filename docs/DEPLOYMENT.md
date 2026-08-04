# Deployment Guide

1. Set `DATABASE_URL`, camera credentials, `GEMINI_API_KEY`, and allowed origins.
2. Install `requirements.txt` in an isolated Python environment.
3. Run database initialization by starting the API once.
4. Start the API with `uvicorn api.server:app --host 0.0.0.0 --port 8000`.
5. Start one pipeline worker per configured GPU allocation.
6. Verify `/api/status`, camera health, and a live test frame before enabling counts.

Run containers as a non-root user, mount models read-only, keep evidence storage
separate from model inputs, terminate TLS upstream, and rotate database/API keys.
