#!/bin/bash
# Codex ships a static musl binary, so it needs no runtime of its own.
set -euo pipefail

CODEX_VERSION="${CODEX_VERSION:-rust-v0.145.0}"

curl -fsSL "https://github.com/openai/codex/releases/download/${CODEX_VERSION}/codex-x86_64-unknown-linux-musl.tar.gz" \
    -o /tmp/codex.tar.gz
tar -xzf /tmp/codex.tar.gz -C /tmp
mv /tmp/codex-x86_64-unknown-linux-musl /usr/local/bin/codex
chmod +x /usr/local/bin/codex
rm /tmp/codex.tar.gz

codex --version
