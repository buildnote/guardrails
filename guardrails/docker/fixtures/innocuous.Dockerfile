
FROM node:20-alpine
ARG NODE_VERSION=20.11.1
ENV NODE_ENV=production
RUN npm ci
