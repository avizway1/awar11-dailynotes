# syntax=docker/dockerfile:1.7

###############################################################################
# To-Do list app -- nginx edition
#
# One image, two processes:
#
#   nginx :80  ->  serves the website from /usr/share/nginx/html   (EFS volume)
#              ->  reverse-proxies /api/ to 127.0.0.1:3000
#   node  :3000 -> the Express API, talks to Amazon DynamoDB (table "Tasks")
#
# The web root is deliberately EMPTY-able: on ECS an EFS volume is mounted over
# /usr/share/nginx/html, which hides anything baked into the image at that path.
# The site therefore ships in /opt/app/site and the entrypoint copies it into
# the web root on first start. See docker-entrypoint.sh.
#
# Build:  docker build -t todo-nginx:1.0.0 .
# Run:    docker run -d -p 8080:80 --name todo todo-nginx:1.0.0
###############################################################################

# Pinned as tags so the build works out of the box. For a regulated pipeline,
# override with immutable digests:
#   docker build --build-arg NGINX_VERSION=1.27-alpine@sha256:<digest> .
ARG NODE_VERSION=22-alpine
ARG NGINX_VERSION=1.27-alpine


###############################################################################
# Stage 1 - deps: production node_modules, installed from the lockfile
###############################################################################
FROM node:${NODE_VERSION} AS deps

WORKDIR /opt/app

# Manifests first: this layer is re-used on every build where package.json and
# package-lock.json have not changed.
COPY package.json package-lock.json ./

# `npm ci` installs exactly what the lockfile pins -- reproducible builds.
# The cache mount keeps the npm cache out of the image layers.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --omit=dev --ignore-scripts \
 && npm cache clean --force


###############################################################################
# Stage 2 - runner: nginx + the Node runtime
###############################################################################
FROM nginx:${NGINX_VERSION} AS runner

ARG APP_VERSION=2.0.0
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="todo-list-app" \
      org.opencontainers.image.description="To-Do list app served by nginx, API on Node.js, storage in Amazon DynamoDB, website content on EFS" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.vendor="Aviz Academy" \
      org.opencontainers.image.licenses="MIT"

# nodejs  - runs the API. Alpine's package is Node 20/22 depending on the base;
#           the app needs >= 18 (global fetch, AWS SDK v3), so either is fine.
# su-exec - drops the API from root to the nginx user (uid 101).
# dumb-init - a real PID 1: reaps zombies and forwards SIGTERM to the group,
#           so `docker stop` and ECS task replacement shut both processes down.
RUN apk add --no-cache nodejs su-exec dumb-init

ENV NODE_ENV=production \
    PORT=3000 \
    AWS_REGION=ap-south-1 \
    DDB_TABLE=Tasks \
    WEB_ROOT=/usr/share/nginx/html \
    SITE_SRC=/opt/app/site \
    SEED_WEB_ROOT=ifempty

WORKDIR /opt/app

# node_modules first (changes rarely), application code second (changes often).
COPY --from=deps /opt/app/node_modules ./node_modules
COPY package.json server.js ./

# The website. NOT copied to /usr/share/nginx/html: that path is an EFS mount
# point at runtime and anything baked there would be shadowed by the volume.
COPY public/ /opt/app/site/

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
 && nginx -t -c /etc/nginx/nginx.conf

EXPOSE 80

# Shallow on purpose: it proves nginx is up and the container is alive without
# touching DynamoDB. A check that called /api/tasks would turn a missing IAM
# permission into an endless crash-loop instead of a readable 500 in the logs.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1

ENTRYPOINT ["dumb-init", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
