# Frontend image (Section 45). Docker is optional for local development
# (see README: `npm run dev`) — this is for the optional production
# deployment path, matching the backend's Dockerfile.
#
# Vite env vars are baked in at build time, not read at container
# runtime — VITE_API_BASE_URL must be the URL the *browser* (running on
# the host, not inside Docker) can reach the backend at, e.g.
# http://localhost:8000, not an internal Docker DNS name like
# http://backend:8000.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
