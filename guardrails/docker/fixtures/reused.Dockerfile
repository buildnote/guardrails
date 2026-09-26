
FROM node:20-alpine@%s AS build
RUN npm ci

FROM build
CMD ["node", "index.js"]
