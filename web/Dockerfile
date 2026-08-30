FROM node:22-alpine AS build

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/index.html web/tsconfig.json web/vite.config.ts ./
COPY web/src ./src
COPY config /build/config
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY web/nginx.conf /etc/nginx/nginx.conf
COPY --from=build --chown=nginx:nginx /build/web/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "-", "http://127.0.0.1:8080/healthz"]

CMD ["nginx", "-g", "daemon off;"]
