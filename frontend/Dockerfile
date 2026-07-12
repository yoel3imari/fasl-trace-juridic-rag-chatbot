# ---- Stage 1: Install dependencies ----
FROM oven/bun:1-alpine AS deps
WORKDIR /app

COPY package.json ./
RUN bun install

# ---- Stage 2: Build the application ----
FROM oven/bun:1-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=production

RUN bun run build

# ---- Stage 3: Production runner ----
FROM oven/bun:1-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    HOSTNAME="0.0.0.0" \
    PORT=3000

# Create a non-root user for security
RUN addgroup --system --gid 1001 bunjs && \
    adduser --system --uid 1001 nextjs

# Copy only the necessary artifacts from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:bunjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:bunjs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["bun", "server.js"]
