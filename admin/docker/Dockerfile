## Multi‑stage Dockerfile for the EPS admin panel

### Stage 1: build the React SPA using Node & Vite
FROM node:18-alpine as builder
WORKDIR /app

# Copy only package manifests first to maximise cache reuse
COPY admin/package*.json ./

RUN npm install --frozen-lockfile || npm install

# Copy the rest of the source code
COPY admin .

# Build the production bundle
RUN npm run build

### Stage 2: serve static files with Caddy
FROM caddy:2-alpine

# Copy the Caddy configuration
COPY admin/docker/Caddyfile /etc/caddy/Caddyfile

# Copy the built assets from the builder stage
COPY --from=builder /app/dist /usr/share/caddy

EXPOSE 80

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]