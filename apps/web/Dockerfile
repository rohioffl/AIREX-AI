FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/ .
RUN npm run build

FROM nginx:alpine

RUN addgroup -g 1001 -S airex && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G airex -g airex airex

COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/web/nginx-main.conf /etc/nginx/nginx.conf
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R airex:airex /usr/share/nginx/html && \
    chown -R airex:airex /var/cache/nginx && \
    chown -R airex:airex /var/log/nginx && \
    chown -R airex:airex /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R airex:airex /var/run/nginx.pid

USER airex

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
