# OpenClaw — Custom Build for RustCode

This directory contains the Docker build infrastructure for building a custom
OpenClaw image tailored to the RustCode stack.

## Quick Start

```bash
# Full build from source (clones upstream, builds base, layers config)
./docker/openclaw/build.sh

# Start the stack
docker compose up -d
```

## Architecture

```
docker/openclaw/
├── Dockerfile            # Our customisation layer (agents, env defaults)
├── Dockerfile.upstream   # Reference copy of upstream OpenClaw Dockerfile
├── build.sh              # Build orchestrator
├── .openclaw-version     # Pinned upstream version (tag, branch, or SHA)
├── .gitignore            # Excludes cloned source from git
├── README.md             # This file
└── src/                  # (git-ignored) Cloned upstream source tree
```

**Two-stage build:**

1. **Base image** (`openclaw-base:local`) — Built from upstream source using
   `Dockerfile.upstream`. This is the vanilla OpenClaw gateway + CLI.
2. **Custom image** (`openclaw:local`) — Layers RustCode agent config,
   workspace directories, and environment defaults on top of the base.

## Build Modes

| Command | What it does |
|---------|-------------|
| `build.sh` | Full build: clone source → build base → layer config |
| `build.sh --base-only` | Only build the upstream base image |
| `build.sh --layer-only` | Skip base, just rebuild the config layer |
| `build.sh --pull ghcr.io/openclaw/openclaw:latest` | Use a registry image as base |
| `build.sh --clean` | Remove cloned source directory |

## Updating OpenClaw

1. Edit `.openclaw-version` with the new tag/commit
2. Run `./docker/openclaw/build.sh`
3. Test: `docker compose up -d && docker compose logs -f openclaw-gateway`
4. Commit the version bump

## Environment Variables

The build script respects these env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_REPO_URL` | `https://github.com/openclaw/openclaw.git` | Upstream repo |
| `OPENCLAW_BASE_TAG` | `openclaw-base:local` | Base image tag |
| `OPENCLAW_TAG` | `openclaw:local` | Final image tag |
| `OPENCLAW_PLATFORM` | `linux/amd64` | Target platform |
| `OPENCLAW_EXTENSIONS` | _(empty)_ | Extensions to include |

## Customisation

- **Agent config**: Edit `openclaw/config/agents.yml` (project root)
- **Skills**: Add to `openclaw/skills/` and update Dockerfile COPY
- **Extensions**: Set `OPENCLAW_EXTENSIONS="ext1 ext2"` in build.sh call
- **System packages**: Use `OPENCLAW_DOCKER_APT_PACKAGES` build arg
