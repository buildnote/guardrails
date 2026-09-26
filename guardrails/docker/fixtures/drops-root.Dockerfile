
FROM node:20-alpine
USER root
RUN apk add --no-cache tini
USER app
CMD ["node", "index.js"]
