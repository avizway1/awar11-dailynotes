#!/bin/sh
# ---------------------------------------------------------------------------
# Starts the two processes that make up the container:
#
#   1. seeds /usr/share/nginx/html (the EFS volume) from the copy of the site
#      baked into the image, so a brand-new file system is not empty
#   2. the Node API,  as uid 101 (nginx), on 127.0.0.1:3000
#   3. nginx itself,  in the foreground, on :80
#
# If either process dies the whole container exits, so ECS/Docker replaces it
# instead of leaving nginx serving 502s forever.
# ---------------------------------------------------------------------------
set -eu

WEB_ROOT="${WEB_ROOT:-/usr/share/nginx/html}"
SITE_SRC="${SITE_SRC:-/opt/app/site}"
SEED_WEB_ROOT="${SEED_WEB_ROOT:-ifempty}"
APP_USER="${APP_USER:-nginx}"

log() { echo "[entrypoint] $*"; }

# --- 1. web root ------------------------------------------------------------
# On ECS the EFS volume is mounted over WEB_ROOT, which hides whatever the image
# had there. Three modes:
#   ifempty (default) - copy the site in only when the volume is still empty,
#                       so content edited on EFS is never overwritten
#   always            - refresh the site on every start (redeploy the UI by
#                       restarting the task)
#   never             - hands-off; you manage the EFS contents yourself
seed_web_root() {
    mkdir -p "$WEB_ROOT"

    case "$SEED_WEB_ROOT" in
        never)
            log "SEED_WEB_ROOT=never - leaving $WEB_ROOT as it is"
            return
            ;;
        always)
            log "SEED_WEB_ROOT=always - refreshing $WEB_ROOT from $SITE_SRC"
            ;;
        *)
            if [ -n "$(ls -A "$WEB_ROOT" 2>/dev/null || true)" ]; then
                log "$WEB_ROOT already has content - not touching it"
                return
            fi
            log "$WEB_ROOT is empty - seeding it from $SITE_SRC"
            ;;
    esac

    cp -R "$SITE_SRC/." "$WEB_ROOT/"

    # An EFS access point squashes every write to its own POSIX user, so this
    # is usually a no-op there. It matters for a plain `docker run` volume.
    chown -R "$APP_USER:$APP_USER" "$WEB_ROOT" 2>/dev/null \
        || log "could not chown $WEB_ROOT - continuing (the access point owns it)"
}

seed_web_root

# --- 2. the API -------------------------------------------------------------
log "starting the API as $APP_USER: node /opt/app/server.js (port ${PORT:-3000})"
su-exec "$APP_USER" node /opt/app/server.js &
API_PID=$!

# --- 3. nginx ---------------------------------------------------------------
log "starting nginx: $*"
"$@" &
NGINX_PID=$!

shutdown() {
    log "signal received - stopping nginx and the API"
    kill "$NGINX_PID" "$API_PID" 2>/dev/null || true
    wait "$NGINX_PID" 2>/dev/null || true
    wait "$API_PID"   2>/dev/null || true
    exit 0
}
trap shutdown TERM INT

# dumb-init signals the whole process group, so the sleep below is interrupted
# immediately on `docker stop` and the trap runs without waiting out the poll.
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$NGINX_PID" 2>/dev/null; do
    sleep 5
done

if kill -0 "$API_PID" 2>/dev/null; then
    log "nginx exited - shutting the container down"
else
    log "the API exited - shutting the container down"
fi

kill "$NGINX_PID" "$API_PID" 2>/dev/null || true
exit 1
