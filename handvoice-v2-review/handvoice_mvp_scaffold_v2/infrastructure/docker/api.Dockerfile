FROM node:20-slim AS capture-build
WORKDIR /capture
COPY apps/capture-web/package.json apps/capture-web/package-lock.json ./
RUN npm ci
COPY apps/capture-web ./
RUN npm run build

FROM python:3.12-slim AS python-base
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY services ./services
COPY pipelines ./pipelines
COPY configs ./configs
COPY packages ./packages
COPY --from=capture-build /capture/dist ./apps/capture-web/dist
RUN pip install --no-cache-dir .

FROM python-base AS test
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"
CMD ["pytest", "-q"]

FROM python-base AS runtime
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
