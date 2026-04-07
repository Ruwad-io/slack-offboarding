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
COPY --from=deps /usr/local/bin/gunicorn /usr/local/bin/gunicorn
COPY . .

USER appuser

EXPOSE 8000
ENV PORT=8000

# Use gthread worker for SSE streaming support
CMD ["gunicorn", "src.app:create_app()", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "0", "--worker-class", "gthread"]
