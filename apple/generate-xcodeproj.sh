#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT/apple"
command -v xcodegen >/dev/null 2>&1 || {
  echo "xcodegen is required: brew install xcodegen" >&2
  exit 1
}
xcodegen generate --spec project.yml
