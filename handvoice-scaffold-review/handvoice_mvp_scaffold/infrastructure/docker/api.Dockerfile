FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY services ./services
COPY pipelines ./pipelines
COPY configs ./configs
COPY packages ./packages
RUN pip install --no-cache-dir .
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
