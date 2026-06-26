FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TAVAN_TAKIP_SQLITE_DATABASE_PATH=/data/tavan_takip.sqlite3

WORKDIR /app

RUN addgroup --system app && \
    adduser --system --ingroup app app && \
    mkdir -p /data && \
    chown -R app:app /app /data

COPY --chown=app:app pyproject.toml README.md LICENSE ./
COPY --chown=app:app src ./src

RUN pip install --upgrade pip && \
    pip install .

USER app

VOLUME ["/data"]
EXPOSE 8000

CMD ["tavan-takip"]
