# ============================================================================
# Ollama image — official base + curl/wget for healthchecks
# ============================================================================
#
# On bare-metal Linux with nvidia-container-toolkit, GPU passthrough is
# handled entirely by the Docker runtime (deploy.resources.reservations
# in docker-compose.yml). No WSL2 hacks, symlinks, or entrypoint wrappers
# are needed.
#
# Build:
#   docker build -f docker/Dockerfile.ollama -t rc-ollama .
#
# Or via compose — see docker-compose.yml rc-ollama.build stanza.
# ============================================================================
FROM ollama/ollama:latest

# Install curl + wget so healthchecks and init scripts work.
# The base image is Ubuntu 24.04 (Noble) and ships apt-get.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# No custom entrypoint — the official ollama entrypoint handles everything.
# GPU visibility is configured via environment variables and the NVIDIA
# container runtime (nvidia-container-toolkit) on the host.
#
# Required host setup (one-time):
#   sudo apt install -y nvidia-container-toolkit
#   sudo nvidia-ctk runtime configure --runtime=docker
#   sudo systemctl restart docker
