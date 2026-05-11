#!/bin/sh
set -eu

image="${1:-${MINIPBX_DOCKER_IMAGE:-}}"
version="$(cat VERSION)"
platforms="${MINIPBX_DOCKER_PLATFORMS:-linux/amd64,linux/arm64}"

if [ -z "$image" ]; then
  echo "Usage: docker/publish.sh <dockerhub-namespace>/minipbx" >&2
  echo "Example: docker/publish.sh mydockerhubuser/minipbx" >&2
  exit 2
fi

case "$image" in
  *:*)
    echo "Pass the image name without tag. The script publishes :$version and :latest." >&2
    exit 2
    ;;
esac

docker buildx build \
  --platform "$platforms" \
  --file docker/Dockerfile \
  --tag "$image:$version" \
  --tag "$image:latest" \
  --push \
  .
