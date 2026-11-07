#!/bin/sh
# Resolve the primary checkout even when invoked from a linked worktree.
set -eu
repo_dir=$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir)
repo_dir=$(dirname "$repo_dir")
cd "$repo_dir"
export COURSE_MAKER_REPO_ROOT="$repo_dir"
mkdir -p backend/.artifacts/animation
# Staging copies CanvasKit from this locked host toolkit into each project.
npm ci --prefix tools/animator --omit=dev
# Compose builds the worker from the toolkit used for the runtime fingerprint.
# A completed migration container may use an older image after new migrations land.
# Rebuild and run it on every startup before bringing up the API.
docker compose -p course-maker-syllabus-ui --env-file backend/.env \
  -f compose.yaml -f compose.dev.yaml build migrate
docker compose -p course-maker-syllabus-ui --env-file backend/.env \
  -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -p course-maker-syllabus-ui --env-file backend/.env \
  -f compose.yaml -f compose.dev.yaml up -d --build --wait api
docker compose -p course-maker-syllabus-ui --env-file backend/.env \
  -f compose.yaml -f compose.dev.yaml exec -T api python /app/check_animator_runtime.py
cd frontend
COURSE_MAKER_API_URL=http://127.0.0.1:50050 PORT=5173 \
  exec npm run dev -- --host 127.0.0.1 --strictPort
