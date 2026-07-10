#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="${MANIFEST:-${SCRIPT_DIR}/RESUMABLE_WHEEL_MANIFEST.tsv}"
WHEELHOUSE="${WHEELHOUSE:-/dev/shm/adsr_qwen_wheelhouse}"
WHEEL_WORKERS="${WHEEL_WORKERS:-4}"
mkdir -p "${WHEELHOUSE}"
cd "${WHEELHOUSE}"

export HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:3138}"
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:3138}"
export http_proxy="${http_proxy:-${HTTP_PROXY}}"
export https_proxy="${https_proxy:-${HTTPS_PROXY}}"

stage_one() {
  local package="$1" version="$2" filename="$3" bytes="$4" sha256="$5" url="$6"
  if [[ -f "${filename}" ]] && printf '%s  %s\n' "${sha256}" "${filename}" | sha256sum -c --status; then
    printf 'WHEEL_VALID package=%s version=%s bytes=%s filename=%s\n' \
      "${package}" "${version}" "${bytes}" "${filename}"
    return 0
  fi
  curl -fL -C - --retry 50 --retry-all-errors --retry-delay 2 \
    --speed-limit 1024 --speed-time 60 \
    -o "${filename}" "${url}"
  printf '%s  %s\n' "${sha256}" "${filename}" | sha256sum -c
  printf 'WHEEL_STAGED package=%s version=%s bytes=%s filename=%s\n' \
    "${package}" "${version}" "${bytes}" "${filename}"
}

running=0
while IFS=$'\t' read -r package version filename bytes sha256 url; do
  [[ "${package}" != "package" ]] || continue
  stage_one "${package}" "${version}" "${filename}" "${bytes}" "${sha256}" "${url}" &
  ((running += 1))
  if ((running >= WHEEL_WORKERS)); then
    wait -n
    ((running -= 1))
  fi
done <"${MANIFEST}"
wait
