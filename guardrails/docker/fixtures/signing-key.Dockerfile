
FROM node:20-alpine
ARG SIGNING_KEY
RUN npm ci
