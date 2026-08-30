FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    THERMAL_DROUGHT_RELEASE_STORE=/var/lib/thermal-drought

RUN addgroup --system climate && adduser --system --ingroup climate --home /nonexistent climate

WORKDIR /app
COPY pipeline/pyproject.toml /app/pipeline/pyproject.toml
COPY pipeline/src /app/pipeline/src
RUN python -m pip install --no-cache-dir './pipeline[service]'

RUN mkdir -p /var/lib/thermal-drought && chown -R climate:climate /var/lib/thermal-drought
USER climate

EXPOSE 8000
VOLUME ["/var/lib/thermal-drought"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/v1/ready', timeout=2).read()"]

CMD ["thermal-drought-service", "--host", "0.0.0.0", "--port", "8000"]
