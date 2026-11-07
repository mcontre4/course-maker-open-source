FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pil ca-certificates chromium-headless-shell ffmpeg fonts-liberation fonts-dejavu-core libegl1 libgles2 libx11-6 libwayland-egl1 libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/animator
COPY package.json package-lock.json ./
RUN npm ci
COPY validate-project.mjs compile-assets.py review-project.mjs verify-remotion.mjs render-video.mjs render-remotion.mjs render-canvas.mjs validate-canvas.mjs ./
ENV PATH="/opt/animator/node_modules/.bin:$PATH" \
    REMOTION_BROWSER_EXECUTABLE=/usr/bin/chromium-headless-shell \
    NODE_PATH=/opt/animator/node_modules \
    HOME=/tmp/home DO_NOT_TRACK=1 CI=1
WORKDIR /workspace
ENTRYPOINT ["/bin/sh", "-c", "mkdir -p /tmp/home; exec \"$@\"", "--"]
