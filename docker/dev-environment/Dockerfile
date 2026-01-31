# Dev Environment Container
# SSH-accessible development container with Claude Code, opencode, and full tooling
# Runs on macvlan with its own LAN IP - no port mapping needed
#
# Build: docker compose build
# Run:   docker compose up -d
# SSH:   ssh james@192.168.20.60

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_MAJOR=22
ARG GO_VERSION=1.23.4
ARG DEV_USER=james
ARG DEV_UID=1000
ARG DEV_GID=1000

# =============================================================================
# System packages
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # SSH server
    openssh-server \
    # Core tools
    git curl wget jq htop vim nano tmux unzip zip \
    # Build essentials
    build-essential pkg-config libssl-dev \
    # Python
    python3 python3-pip python3-venv pipx \
    # Networking/debug
    iputils-ping net-tools dnsutils iproute2 ca-certificates \
    # Shell
    zsh \
    # Misc
    sudo locales gnupg lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Set locale
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# =============================================================================
# Docker CLI (no daemon - uses host socket)
# =============================================================================
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
       https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Node.js 22 (for Claude Code)
# =============================================================================
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Go 1.23
# =============================================================================
RUN curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-$(dpkg --print-architecture).tar.gz \
    | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# =============================================================================
# Create dev user
# =============================================================================
# Remove default ubuntu user/group (UID/GID 1000 on 24.04) then create ours
RUN userdel -r ubuntu 2>/dev/null || true \
    && groupadd -g ${DEV_GID} ${DEV_USER} 2>/dev/null || true \
    && useradd -m -u ${DEV_UID} -g ${DEV_GID} -s /bin/zsh ${DEV_USER} \
    && passwd -d ${DEV_USER} \
    && echo "${DEV_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DEV_USER} \
    && chmod 0440 /etc/sudoers.d/${DEV_USER}

# Add user to docker group (created at runtime by entrypoint)
RUN groupadd -r docker 2>/dev/null || true \
    && usermod -aG docker ${DEV_USER}

# =============================================================================
# Claude Code
# =============================================================================
RUN npm install -g @anthropic-ai/claude-code

# =============================================================================
# opencode
# =============================================================================
RUN npm install -g opencode-ai@latest

# =============================================================================
# Codex
# =============================================================================
RUN npm install -g @openai/codex

# =============================================================================
# Ansible
# =============================================================================
RUN pip3 install --break-system-packages ansible

# =============================================================================
# GitHub CLI
# =============================================================================
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
       https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# kubectl
# =============================================================================
RUN curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/$(dpkg --print-architecture)/kubectl" \
    -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl

# =============================================================================
# Terraform
# =============================================================================
RUN curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
       https://apt.releases.hashicorp.com $(. /etc/os-release && echo "$VERSION_CODENAME") main" \
       > /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends terraform \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# uv (Python package manager)
# =============================================================================
RUN curl -fsSL https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx

# =============================================================================
# Poetry
# =============================================================================
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# =============================================================================
# Homebrew
# =============================================================================
RUN NONINTERACTIVE=1 su - ${DEV_USER} -c \
    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
ENV PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:${PATH}"

# =============================================================================
# 1Password CLI
# =============================================================================
RUN curl -fsSL https://downloads.1password.com/linux/keys/1password.asc | \
    gpg --dearmor -o /usr/share/keyrings/1password-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] \
       https://downloads.1password.com/linux/debian/$(dpkg --print-architecture) stable main" \
       > /etc/apt/sources.list.d/1password.list \
    && mkdir -p /etc/debsig/policies/AC2D62742012EA22/ \
    && curl -fsSL https://downloads.1password.com/linux/debian/debsig/1password.pol \
       -o /etc/debsig/policies/AC2D62742012EA22/1password.pol \
    && mkdir -p /usr/share/debsig/keyrings/AC2D62742012EA22 \
    && curl -fsSL https://downloads.1password.com/linux/keys/1password.asc | \
       gpg --dearmor -o /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends 1password-cli \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# VS Code CLI (for Remote Tunnels)
# =============================================================================
RUN curl -fsSL "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64" \
    -o /tmp/vscode-cli.tar.gz \
    && tar -xzf /tmp/vscode-cli.tar.gz -C /usr/local/bin \
    && rm /tmp/vscode-cli.tar.gz

# =============================================================================
# Oh My Zsh + Pure prompt (installed to /opt so it survives bind mounts)
# =============================================================================
RUN git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git /opt/oh-my-zsh \
    && git clone --depth=1 https://github.com/sindresorhus/pure.git \
       /opt/oh-my-zsh/custom/themes/pure \
    && ln -s /opt/oh-my-zsh/custom/themes/pure/pure.zsh \
       /opt/oh-my-zsh/custom/themes/pure.zsh-theme \
    && ln -s /opt/oh-my-zsh/custom/themes/pure/async.zsh \
       /opt/oh-my-zsh/custom/async.zsh \
    && git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions \
       /opt/oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting \
       /opt/oh-my-zsh/custom/plugins/zsh-syntax-highlighting

# =============================================================================
# SSH setup
# =============================================================================
RUN mkdir -p /run/sshd \
    && mkdir -p /home/${DEV_USER}/.ssh \
    && chmod 700 /home/${DEV_USER}/.ssh \
    && chown -R ${DEV_USER}:${DEV_USER} /home/${DEV_USER}/.ssh

COPY config/sshd_config /etc/ssh/sshd_config
COPY config/zshrc /etc/skel/.zshrc

# =============================================================================
# Go path for user
# =============================================================================
ENV GOPATH="/home/${DEV_USER}/go"
ENV PATH="${GOPATH}/bin:/usr/local/go/bin:${PATH}"

# =============================================================================
# Entrypoint
# =============================================================================
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
