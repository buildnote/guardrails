
FROM node:20-alpine
RUN addgroup -S app && adduser -S -G app app
USER app
CMD ["node", "index.js"]
