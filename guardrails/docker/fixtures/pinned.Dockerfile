
FROM node:20-alpine@%s AS build
RUN npm ci

FROM gcr.io/distroless/nodejs20-debian12@%s
COPY --from=build /app /app
