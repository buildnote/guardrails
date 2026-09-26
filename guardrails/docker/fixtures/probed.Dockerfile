
FROM alpine@sha256:aaaa
HEALTHCHECK --interval=30s CMD curl -fsS http://localhost:8080/health || exit 1
USER app
