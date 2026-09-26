
FROM node:20-alpine AS build
RUN npm ci

FROM nginx:1.27
COPY --from=build /app /usr/share/nginx/html
