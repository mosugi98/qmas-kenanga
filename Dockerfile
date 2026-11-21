FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TOKOEMAS_ONLINE=1 TOKOEMAS_DATA=/data PORT=8000

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY run.py .
COPY app ./app

RUN useradd --create-home --uid 10001 qmas && mkdir -p /data && chown qmas /data
USER qmas
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'), timeout=4)"

CMD ["python", "run.py"]
