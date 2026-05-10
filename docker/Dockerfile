FROM ubuntu:24.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asterisk \
        ca-certificates \
        python3.12 \
        python3.12-venv \
        sqlite3 \
        tini \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/minipbx

COPY requirements.txt .
RUN python3.12 -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY alembic.ini .
COPY alembic ./alembic
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p /var/lib/minipbx /var/log/asterisk /var/spool/asterisk /var/run/asterisk /var/lib/asterisk /etc/asterisk \
    && chown -R asterisk:asterisk /var/lib/minipbx /var/log/asterisk /var/spool/asterisk /var/run/asterisk /var/lib/asterisk /etc/asterisk

VOLUME ["/var/lib/minipbx", "/etc/asterisk", "/var/spool/asterisk", "/var/log/asterisk"]

EXPOSE 8080/tcp 5060/udp 10000-10100/udp

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
