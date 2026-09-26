
FROM node:20-alpine
ENV DATABASE_PASSWORD=hunter2
CMD ["node", "index.js"]
