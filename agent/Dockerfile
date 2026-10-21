# The PatchBench agent image -- one image per agent, all from this file.
#
#   docker build --build-arg AGENT=codex -t patchbench/agent-codex agent
#
# The agent program runs here, as the unprivileged user `agent`, but every
# command it runs goes to the task container: each shell in this image is
# `shell`, which hands the command to `forward`, the only program allowed to
# use the Docker socket. The agent therefore sees and changes only the task.
#
# Everything above `ARG AGENT` is shared, so Docker's cache reuses it across
# agents and only the agent's own install step differs between images.
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG DOCKER_CLI_VERSION=27.3.1
ARG AGENT_PYTHON=3.12

# For the install steps and the harness; the agent's commands never run here.
# bindfs is for `view`, which runs as root and so mounts without fusermount;
# fusermount loses its setuid bit, so the agent's user cannot mount anything.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq less ripgrep sudo xz-utils build-essential bindfs \
    && rm -rf /var/lib/apt/lists/* \
    && chmod u-s /usr/bin/fusermount

# The agent's user sees every file in the checkout as its own (see view) while
# root sees the real owners, and git refuses a checkout another user owns; and
# the harness commits a baseline, which needs an identity. Both are system-wide
# so they hold whatever HOME is set.
RUN git config --system --add safe.directory '*' \
    && git config --system user.name "patchbench" \
    && git config --system user.email "anonymous@email.com"

# Docker CLI only -- the daemon is the host's, reached over the mounted socket.
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
        -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp docker/docker \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz

# One virtualenv at a fixed path in every agent image; it is also the
# entrypoint, so the inference stage never needs to know which agent it starts.
ENV UV_INSTALL_DIR=/usr/local/bin \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    VIRTUAL_ENV=/opt/agent \
    PATCHBENCH_AGENT_PYTHON=/opt/agent/bin/python
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv venv --python "${AGENT_PYTHON}" /opt/agent \
    && uv pip install gitPython

# The agent's own user. Its home is /root, which is shared with the task
# container, so `~` names the same folder in a command and in a file tool.
RUN useradd --uid 10001 --home-dir /root --no-create-home --shell /bin/bash agent

# Command forwarding. The agent's user may run `forward` as root and nothing else.
# Also the harness's `view`, which shows that user the shared folders as root sees them.
COPY shell forward view /opt/patchbench/libexec/
RUN chmod 755 /opt/patchbench/libexec/shell /opt/patchbench/libexec/forward \
        /opt/patchbench/libexec/view \
    && mkdir -p /opt/patchbench/home \
    && echo 'agent ALL=(root) NOPASSWD: /opt/patchbench/libexec/forward' > /etc/sudoers.d/patchbench \
    && chmod 440 /etc/sudoers.d/patchbench

# ---- the only part that differs between agents ----
ARG AGENT
RUN test -n "${AGENT}" || { echo "build with --build-arg AGENT=<name>" >&2; exit 1; }
COPY install/${AGENT}.sh /tmp/install.sh
RUN bash /tmp/install.sh && rm /tmp/install.sh
LABEL org.patchbench.agent="${AGENT}"

# Root-side tools keep their settings out of the shared /root.
ENV HOME=/opt/patchbench/home

# Last, because every step above needs a real shell: each shell becomes `shell`.
RUN ["/opt/agent/bin/python", "-c", "import os, shutil\nfor path in ('/usr/bin/bash', '/usr/bin/rbash', '/usr/bin/dash', '/usr/bin/sh'):\n    shutil.copy('/opt/patchbench/libexec/shell', path + '.new')\n    os.chmod(path + '.new', 0o755)\n    os.replace(path + '.new', path)"]

WORKDIR /harnesses
ENTRYPOINT ["/opt/agent/bin/python"]
