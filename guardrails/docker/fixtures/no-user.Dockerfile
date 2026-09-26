
FROM node:20-alpine
COPY . /app
CMD ["node", "index.js"]
