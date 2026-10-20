# Dashboard image. Build context = services/dashboard.
#   docker build -t netguard-dashboard services/dashboard
# Stage 1 builds the React app; stage 2 serves the static files and proxies /api/ with nginx.
FROM node:24-alpine AS build
WORKDIR /app
# Dependencies first (change rarely -> cached layer)
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Non-root nginx (security requirement), listens on 8080
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
