FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages change rarely and should stay in an early cached layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependency install is the expensive AI layer. Keep it before app code
# so normal dashboard/API edits reuse Docker cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code changes frequently, so copy it last.
COPY . .

RUN mkdir -p /app/logs /app/snapshots /app/models /app/database

EXPOSE 8080

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8080"]
