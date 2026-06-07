# =============================================================================
# ConfigForge / Devbench — Docker image
#
# Build a slim container (~60 MB) that ships the CLI, the Web UI (--serve),
# and the REST API (--api).  All three entry points are available from a
# single image so users pick the right mode at runtime.
#
# Build:
#   docker build -t devbench .
#
# Run (CLI — convert a file mounted from the host):
#   docker run --rm -v "$PWD:/data" devbench cf /data/config.yaml --to json
#
# Run (Web UI — local browser on port 8080):
#   docker run --rm -p 8080:8080 devbench cf --serve --host 0.0.0.0
#
# Run (REST API — JSON endpoints on port 8081):
#   docker run --rm -p 8081:8081 devbench cf --api --api-port 8081 --host 0.0.0.0
#
# Run (interactive Python):
#   docker run --rm -it devbench python3
#
# Run (full stack):
#   docker compose up
# =============================================================================

# ---- Stage 1 : build the wheel -------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .

# Build a wheel so the runtime image carries exactly what's needed.
RUN python3 -m pip install --no-cache-dir build setuptools wheel && \
    python3 -m build --wheel --outdir /dist

# ---- Stage 2 : runtime ----------------------------------------------------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="ConfigForge"
LABEL org.opencontainers.image.description="9-format config file converter — offline, private, CLI + Web UI + REST API"
LABEL org.opencontainers.image.source="https://github.com/apeters247/devbench"
LABEL org.opencontainers.image.licenses="MIT"

# Tini — tiny init for proper PID 1 behaviour (signal forwarding, zombie reaping).
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /dist/*.whl /tmp/
RUN python3 -m pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Entrypoint wrapper — routes devbench subcommands vs. passthrough.
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'if [ $# -eq 0 ]; then exec devbench --help; fi' \
    'case "$1" in' \
    '  --*|detect|json|base64|jwt|hash|url|timestamp|uuid|diff|cf|list|batch|license)' \
    '    exec devbench "$@";;' \
    '  *) exec "$@";;' \
    'esac' \
    > /usr/local/bin/docker-entrypoint.sh \
    && chmod 755 /usr/local/bin/docker-entrypoint.sh

# Create a non-root user for running servers.
RUN groupadd -r devbench && useradd -r -g devbench -d /data -s /sbin/nologin devbench
RUN mkdir -p /data && chown devbench:devbench /data
USER devbench
WORKDIR /data

# Expose both the web demo and the REST API port.
EXPOSE 8080
EXPOSE 8081

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["--help"]