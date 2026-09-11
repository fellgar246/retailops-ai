# syntax=docker/dockerfile:1

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci


FROM node:22-alpine AS builder
WORKDIR /app

# The API origin is read at runtime by the server-side proxy, so the image is
# not built for one environment.
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


# The standalone server needs Node and nothing else. Shipping a full image
# would carry npm and a package manager's own dependencies into production,
# which is where every finding in this image came from and none of it runs.
FROM gcr.io/distroless/nodejs22-debian12:nonroot AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder --chown=nonroot:nonroot /app/.next/standalone ./
COPY --from=builder --chown=nonroot:nonroot /app/.next/static ./.next/static

EXPOSE 3000

CMD ["server.js"]
