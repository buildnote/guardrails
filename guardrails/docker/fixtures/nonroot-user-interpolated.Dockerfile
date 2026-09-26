
FROM node:20-alpine
ARG APP_USER
USER $APP_USER
CMD ["node", "index.js"]
