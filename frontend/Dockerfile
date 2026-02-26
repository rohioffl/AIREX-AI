FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

# Create non-root user for nginx
RUN addgroup -g 1001 -S airex && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G airex -g airex airex

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Change ownership
RUN chown -R airex:airex /usr/share/nginx/html && \
    chown -R airex:airex /var/cache/nginx && \
    chown -R airex:airex /var/log/nginx && \
    chown -R airex:airex /etc/nginx/conf.d

# Update nginx config to run as non-root (if nginx.conf doesn't already specify)
RUN touch /var/run/nginx.pid && \
    chown -R airex:airex /var/run/nginx.pid

USER airex

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
