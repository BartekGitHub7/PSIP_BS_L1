FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-venv \
        gdal-bin \
        python3-gdal \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir "h3==4.5.0"

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app