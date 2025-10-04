FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPROXY_PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY web ./

EXPOSE 8000

CMD [ \
  "sh", "-c", \
  "gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${UPROXY_PORT:-8000} --timeout 360 main:app" \
]
