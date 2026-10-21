#!/bin/bash
# The OpenHands SDK, pinned to the commit the benchmark was run with.
set -euo pipefail

OPENHANDS_SDK_COMMIT="${OPENHANDS_SDK_COMMIT:-4cc0ebd29753c12f88e2561fc617e0bb0f7ec303}"   # v1.20.0

# Some of the SDK's dependencies build from source.
export CARGO_HOME=/opt/cargo RUSTUP_HOME=/opt/rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
export PATH="/opt/cargo/bin:${PATH}"

git clone https://github.com/OpenHands/software-agent-sdk.git /opt/software-agent-sdk
git -C /opt/software-agent-sdk checkout "${OPENHANDS_SDK_COMMIT}"
# The browser tool is never enabled, and its dependency tree is heavy.
sed -i '/browser-use/d' /opt/software-agent-sdk/openhands-tools/pyproject.toml

uv pip install 'litellm==1.89.0' fastapi \
    -e /opt/software-agent-sdk/openhands-sdk \
    -e /opt/software-agent-sdk/openhands-tools

uv pip show openhands-sdk | grep -i '^version'
