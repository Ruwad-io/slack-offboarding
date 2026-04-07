FROM python:3.12-slim AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Production image
FROM base AS runner
WORKDIR /app

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --home /home/appuser appuser

COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY . .

USER appuser

ENV PORT=8000

CMD uvicorn "src.app:create_app" --factory --host "0.0.0.0" --port "${PORT}" --workers 2 --timeout-keep-alive 0
