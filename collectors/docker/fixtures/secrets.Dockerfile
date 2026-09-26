FROM alpine:3.20
ARG NPM_TOKEN=npm_hunter2mostsecret
ENV DATABASE_URL="postgres://widget:hunter2mostsecret@db/widget" API_KEY=hunter2mostsecret
ENV LEGACY_HOME /opt/widget
RUN npm ci
