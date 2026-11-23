FROM node:20-slim AS builder

# Install dependencies required for building the app
RUN apt-get update && \
    apt-get install -y tini && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json package-lock.json* ./
RUN npm ci --quiet

RUN npm install --save-dev update-browserslist-db
RUN npx update-browserslist-db@latest

COPY ./ ./
RUN npm run build
RUN npm prune --omit=dev

FROM node:20-slim AS production

ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/out ./out
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.* ./
COPY --from=builder /usr/bin/tini /usr/bin/tini
RUN mkdir ./certificates

RUN npm ci --omit=dev --quiet

EXPOSE 3000
EXPOSE 9095

# Use tini to handle signals properly, see https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md#handling-kernel-signals
ENTRYPOINT ["/usr/bin/tini", "-p", "SIGKILL", "--" ]
CMD ["npx", "serve@latest", "out"]
