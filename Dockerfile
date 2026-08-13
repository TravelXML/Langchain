# Backend image. Docker is optional for local development (see README) —
# this is intended for the optional production deployment path.
FROM python:3.12-slim

WORKDIR /srv/app

COPY pyproject.toml README.md ./
COPY app ./app
COPY config ./config
COPY prompts ./prompts
COPY migrations ./migrations

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
