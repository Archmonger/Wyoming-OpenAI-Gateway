# Stage 1: Build wheel
FROM python:3.13-slim AS builder

WORKDIR /build
COPY . .
RUN pip install hatchling && pip wheel --no-cache-dir --wheel-dir /wheels .

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

EXPOSE 8555

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8555/healthz')" || exit 1

ENTRYPOINT ["wyoming-openai-gateway"]
