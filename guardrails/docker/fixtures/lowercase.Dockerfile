
FROM node:20-alpine
ARG npm_token
RUN npm ci
