FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8001
# Shell form so Render's injected $PORT is honored; defaults to 8001 locally.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
