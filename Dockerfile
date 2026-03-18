FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY docs/ docs/

RUN pip install --no-cache-dir -e . gunicorn

EXPOSE 8050

CMD ["gunicorn", "mpd_overwatch.wsgi:server", "--bind", "0.0.0.0:8050", "--workers", "2", "--timeout", "120"]
