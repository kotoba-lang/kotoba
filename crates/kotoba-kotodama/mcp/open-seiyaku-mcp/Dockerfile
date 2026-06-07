FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY 20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp ./20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp

RUN npm install -g pnpm && \
    pnpm install --filter @etzhayyim/open-seiyaku-mcp... && \
    cd 20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp && \
    pnpm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp/package.json ./
COPY --from=builder /app/20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp/node_modules ./node_modules
COPY --from=builder /app/20-actors/kotoba-kotodama/mcp/open-seiyaku-mcp/src ./src

ENTRYPOINT ["node", "./src/cli.js"]
