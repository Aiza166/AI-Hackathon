# Frontend container: build the Vite PWA, serve it with nginx on $PORT.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Public URL of the backend API (Railway passes service variables as build args).
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
# Demo persona list on the sign-in screen: only when "true". VITE_DEMO_PIN is the public
# citizen/helper demo PIN for one-tap sign-in (never the officer/admin PINs).
ARG VITE_SHOW_DEMO_ACCOUNTS=false
ARG VITE_DEMO_PIN=
ENV VITE_SHOW_DEMO_ACCOUNTS=$VITE_SHOW_DEMO_ACCOUNTS VITE_DEMO_PIN=$VITE_DEMO_PIN
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
# API_ORIGIN goes into the Content-Security-Policy (connect-src / media-src), e.g.
# https://backend.example.up.railway.app. Empty means same origin only.
ENV PORT=8080 API_ORIGIN=""
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null "http://127.0.0.1:${PORT}/" || exit 1
