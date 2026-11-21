# Frontend container: build the Vite PWA, serve it with nginx on $PORT.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Public URL of the backend API (Railway passes service variables as build args).
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Becomes /etc/nginx/conf.d/security-headers.inc (not *.conf, so it is only included where named).
COPY security-headers.inc.template /etc/nginx/templates/security-headers.inc.template
# CSP connect-src allows the API origin the bundle was built for.
ARG VITE_API_BASE=""
ENV API_ORIGIN=$VITE_API_BASE
COPY --from=build /app/dist /usr/share/nginx/html
ENV PORT=8080
