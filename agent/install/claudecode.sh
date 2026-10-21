#!/bin/bash
# Node for the Claude Code CLI, and the Python SDK the harness drives it with.
set -euo pipefail

NODE_VERSION="${NODE_VERSION:-22.12.0}"   # Claude Code requires >= 22
CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION:-latest}"

curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    -o /tmp/node.tar.xz
tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1
rm /tmp/node.tar.xz

npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"
uv pip install 'claude-agent-sdk>=0.1.6'

# Recorded in the build log, since the CLI version is not pinned by default.
node --version
claude --version
uv pip show claude-agent-sdk | grep -i '^version'
