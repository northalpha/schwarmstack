# Image für Staging und Produktion (ADR 0001): App mit gunicorn, statische Dateien über WhiteNoise.
FROM python:3.13-slim-trixie AS build
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
# Statische Dateien gehören ins Image, nicht ins Datenverzeichnis.
RUN DEBUG=1 DATA_DIR=/tmp/data STATIC_ROOT=/app/static \
    .venv/bin/python src/manage.py collectstatic --noinput

FROM python:3.13-slim-trixie
RUN groupadd --system --gid 10001 schwarmstack \
 && useradd --system --uid 10001 --gid schwarmstack --no-create-home schwarmstack \
 && mkdir /data && chown schwarmstack:schwarmstack /data
# pip braucht die Laufzeit nicht; seine mitgelieferten Bibliotheken (msgpack, urllib3, setuptools)
# meldet der Image-Scan sonst als Schwachstellen. Debian-Sicherheitskorrekturen werden nachgezogen.
RUN pip uninstall --yes pip \
 && apt-get update \
 && apt-get upgrade --yes --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/src
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/static /app/static
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    STATIC_ROOT=/app/static
USER schwarmstack
EXPOSE 8000
CMD ["gunicorn", "schwarmstack.wsgi", "--bind", "0.0.0.0:8000", "--no-control-socket", "--workers", "3", "--timeout", "60"]
