
FROM node:20-alpine
ARG NPM_TOKEN
RUN npm ci
