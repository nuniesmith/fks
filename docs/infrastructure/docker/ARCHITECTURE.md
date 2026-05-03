# Docker Architecture Diagram

**FKS Docker Infrastructure - Visual Overview**

---

## 🏗️ Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FKS DOCKER ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         BASE DOCKERFILES (docker/)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │
│  │ Dockerfile.rust    │  │ Dockerfile.python  │  │ Dockerfile.authelia│   │
│  │ ────────────────── │  │ ────────────────── │  │ ────────────────── │   │
│  │ Base: rust:1.91    │  │ Base: python:3.13  │  │ Base: authelia     │   │
│  │ Runtime: debian    │  │ Tools: Poetry      │  │ Type: Auth Service │   │
│  │ Size: ~80 lines    │  │ Size: ~100 lines   │  │ Size: Custom       │   │
│  │ Use: CPU services  │  │ Use: CPU services  │  │ Use: Auth only     │   │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘   │
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │
│  │Dockerfile.rust.gpu │  │Dockerfile.python   │  │ Dockerfile.web     │   │
│  │ ────────────────── │  │         .gpu       │  │ ────────────────── │   │
│  │ Base: CUDA 12.4.1  │  │ ────────────────── │  │ Base: nginx:alpine │   │
│  │ Tools: CUDA dev    │  │ Base: CUDA 12.4.1  │  │ Type: Web UI       │   │
│  │ Size: ~95 lines    │  │ Tools: PyTorch GPU │  │ Size: Custom       │   │
│  │ Use: GPU ML/AI     │  │ Size: ~170 lines   │  │ Use: Web only      │   │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    SERVICE-SPECIFIC DOCKERFILES (src/)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ JANUS Services (src/janus/)                                          │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │                                                                      │  │
│  │  Dockerfile.rust              Dockerfile.python                     │  │
│  │  ───────────────              ──────────────────                    │  │
│  │  • Forward (Rust)              • Gateway (Python)                   │  │
│  │  • Backward (Rust)             • FastAPI orchestration              │  │
│  │  • Workspace build             • Root context                       │  │
│  │  • Shared crates               • Project-wide deps                  │  │
│  │  • gRPC proto                  • Poetry workspace                   │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │ Audit Service       │  │ Monitor Service     │  │ CNS Service      │   │
│  │ (src/audit/)        │  │ (src/monitor/)      │  │ (src/janus/...)  │   │
│  │ ─────────────────── │  │ ─────────────────── │  │ ──────────────── │   │
│  │ Dockerfile          │  │ Dockerfile          │  │ Dockerfile       │   │
│  │ • Standalone Rust   │  │ • Standalone Rust   │  │ • Python service │   │
│  │ • Server + CLI      │  │ • Infrastructure    │  │ • Health checks  │   │
│  │ • LLM integration   │  │ • Redis/Prometheus  │  │ • Monitoring     │   │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Build Flow Diagrams

### Rust Service Build (CPU)

```
┌─────────────┐
│   Source    │
│  src/my-    │
│  service/   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  docker/Dockerfile.rust                 │
├─────────────────────────────────────────┤
│  STAGE 1: Builder                       │
│  ┌────────────────────────────────┐    │
│  │ rust:1.91.1-slim               │    │
│  │ • Install build deps           │    │
│  │ • Copy Cargo.toml/lock         │    │
│  │ • Copy src/                    │    │
│  │ • cargo build --release        │    │
│  │ • strip binary                 │    │
│  └────────────────────────────────┘    │
│               │                         │
│               ▼                         │
│  STAGE 2: Runtime                       │
│  ┌────────────────────────────────┐    │
│  │ debian:bookworm-slim           │    │
│  │ • Install runtime deps         │    │
│  │ • Copy binary from builder     │    │
│  │ • Create non-root user         │    │
│  │ • Set health check             │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Image     │
│ fks-service │
│  ~100-200MB │
└─────────────┘
```

### Python Service Build (CPU)

```
┌─────────────┐
│   Source    │
│  Project    │
│    Root     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  docker/Dockerfile.python               │
├─────────────────────────────────────────┤
│  STAGE 1: Base                          │
│  ┌────────────────────────────────┐    │
│  │ python:3.13-slim               │    │
│  │ • Install system deps          │    │
│  │ • Install TA-Lib C library     │    │
│  └────────────────────────────────┘    │
│               │                         │
│               ▼                         │
│  STAGE 2: Builder                       │
│  ┌────────────────────────────────┐    │
│  │ Create venv                    │    │
│  │ • Copy pyproject.toml/lock     │    │
│  │ • poetry install               │    │
│  └────────────────────────────────┘    │
│               │                         │
│               ▼                         │
│  STAGE 3: Runtime                       │
│  ┌────────────────────────────────┐    │
│  │ Copy venv from builder         │    │
│  │ • Copy source code             │    │
│  │ • Create non-root user         │    │
│  │ • Set health check             │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Image     │
│ fks-service │
│  ~400-600MB │
└─────────────┘
```

### Python GPU Service Build

```
┌─────────────┐
│   Source    │
│  Project    │
│    Root     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  docker/Dockerfile.python.gpu           │
├─────────────────────────────────────────┤
│  STAGE 1: CPU Builder                   │
│  ┌────────────────────────────────┐    │
│  │ python:3.13-slim               │    │
│  │ • Install TA-Lib               │    │
│  │ • Create venv                  │    │
│  │ • poetry install (base deps)   │    │
│  └────────────────────────────────┘    │
│               │                         │
│               ▼                         │
│  STAGE 2: ML Builder                    │
│  ┌────────────────────────────────┐    │
│  │ Install ML deps                │    │
│  │ • poetry install --with ml     │    │
│  │ • PyTorch with CUDA            │    │
│  └────────────────────────────────┘    │
│               │                         │
│               ▼                         │
│  STAGE 3: GPU Runtime                   │
│  ┌────────────────────────────────┐    │
│  │ nvidia/cuda:12.4.1-runtime     │    │
│  │ • Install Python 3.13          │    │
│  │ • Copy TA-Lib from builder     │    │
│  │ • Copy venv from ML builder    │    │
│  │ • Fix venv paths for GPU       │    │
│  │ • Copy source code             │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Image     │
│ fks-ml-svc  │
│   ~2-4 GB   │
└─────────────┘
```

---

## 📊 Service Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOCKER COMPOSE SERVICES                              │
└─────────────────────────────────────────────────────────────────────────────┘

                                 ┌─────────────┐
                                 │   Redis     │
                                 │ (Official)  │
                                 └──────┬──────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
            ┌───────▼────────┐  ┌──────▼──────┐   ┌───────▼────────┐
            │    Forward     │  │   Gateway   │   │    Monitor     │
            │ Dockerfile.rust│  │Dockerfile.  │   │  Dockerfile    │
            │   (Janus)      │  │  python     │   │  (src/monitor) │
            └───────┬────────┘  │  (Janus)    │   └────────────────┘
                    │           └──────┬──────┘
                    │                  │
                    └────────┬─────────┘
                             │
                     ┌───────▼────────┐
                     │    QuestDB     │
                     │  (Official)    │
                     └───────┬────────┘
                             │
                     ┌───────▼────────┐
                     │  Prometheus    │
                     │  (Official)    │
                     └───────┬────────┘
                             │
                     ┌───────▼────────┐
                     │    Grafana     │
                     │  (Official)    │
                     └────────────────┘

         ┌────────────────┐          ┌─────────────┐
         │     Audit      │          │   Authelia  │
         │  Dockerfile    │          │ Dockerfile. │
         │ (src/audit)    │          │  authelia   │
         └────────────────┘          └─────────────┘

                     ┌────────────────┐
                     │      Web       │
                     │  Dockerfile.   │
                     │      web       │
                     └────────────────┘
```

---

## 🎯 When to Use Which Dockerfile

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DECISION TREE                                        │
└─────────────────────────────────────────────────────────────────────────────┘

                        Creating New Service?
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              What Language?              Special Service?
                    │                         │
        ┌───────────┴───────────┐            │
        │                       │            ▼
      Rust                   Python    Create Custom
        │                       │       Dockerfile
        │                       │
        ▼                       ▼
    Need GPU?              Need GPU?
        │                       │
    ┌───┴───┐             ┌─────┴─────┐
    │       │             │           │
   No      Yes           No          Yes
    │       │             │           │
    ▼       ▼             ▼           ▼
┌────────┐ ┌──────┐  ┌────────┐  ┌─────────┐
│Rust    │ │Rust  │  │Python  │  │Python   │
│CPU     │ │GPU   │  │CPU     │  │GPU      │
└────────┘ └──────┘  └────────┘  └─────────┘
    │         │          │            │
    ▼         ▼          ▼            ▼
docker/   docker/    docker/      docker/
Dockerfile Dockerfile Dockerfile  Dockerfile
.rust     .rust.gpu  .python     .python.gpu


                    Workspace Build Needed?
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                   Yes                       No
                    │                         │
                    ▼                         ▼
           Create in src/SERVICE/      Use Base Dockerfile
           with custom Dockerfile      from docker/
           (see Janus example)
```

---

## 🔧 Layer Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-STAGE BUILD LAYERS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

STAGE 1: Builder
┌─────────────────────────────────────────┐
│ Layer 1: Base Image (FROM)              │ ← Cached (rarely changes)
├─────────────────────────────────────────┤
│ Layer 2: System Dependencies            │ ← Cached (rarely changes)
├─────────────────────────────────────────┤
│ Layer 3: Dependency Files (COPY)        │ ← Cached (changes occasionally)
│          Cargo.toml / pyproject.toml    │
├─────────────────────────────────────────┤
│ Layer 4: Build Dependencies             │ ← Cached (if deps unchanged)
│          cargo build / poetry install   │
├─────────────────────────────────────────┤
│ Layer 5: Source Code (COPY src/)        │ ← Invalidated (changes often)
├─────────────────────────────────────────┤
│ Layer 6: Build Binary / Install App     │ ← Rebuilt (if source changed)
└─────────────────────────────────────────┘
                    │
                    ▼
STAGE 2: Runtime
┌─────────────────────────────────────────┐
│ Layer 1: Runtime Base Image             │ ← Cached (rarely changes)
├─────────────────────────────────────────┤
│ Layer 2: Runtime Dependencies           │ ← Cached (rarely changes)
├─────────────────────────────────────────┤
│ Layer 3: Copy Artifacts from Builder    │ ← Invalidated (if built changed)
├─────────────────────────────────────────┤
│ Layer 4: User & Permissions             │ ← Cached (rarely changes)
└─────────────────────────────────────────┘

🎯 Key Optimization: Copy dependency files BEFORE source code
   → Dependencies change less frequently than source
   → Better cache hit rate
   → Faster builds
```

---

## 📏 Image Size Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          IMAGE SIZES                                         │
└─────────────────────────────────────────────────────────────────────────────┘

Service Type                Base Image              Final Size
─────────────────────────────────────────────────────────────────────────────

Rust (CPU)
  Forward                   debian:bookworm-slim    ~150 MB
  Audit                     debian:bookworm-slim    ~120 MB
  Monitor                   debian:bookworm-slim    ~100 MB

Python (CPU)
  Gateway                   python:3.13-slim        ~500 MB

Python (GPU)
  ML Service                nvidia/cuda:12.4.1      ~3.5 GB
  (includes PyTorch)

Special
  Authelia                  authelia/authelia       ~200 MB
  Web                       nginx:alpine            ~50 MB

Infrastructure
  Redis                     redis:7-alpine          ~30 MB
  QuestDB                   questdb/questdb         ~200 MB
  Prometheus                prom/prometheus         ~200 MB
  Grafana                   grafana/grafana         ~300 MB
```

---

## 🔐 Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SECURITY LAYERS                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Layer 1: Base Image Selection           │
│ • Use official images                   │
│ • Prefer -slim variants                 │
│ • Pin specific versions                 │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Layer 2: Minimal Dependencies           │
│ • Install only required packages        │
│ • Clean up after install                │
│ • No dev tools in production            │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Layer 3: Non-Root Users                 │
│ • All services run as non-root          │
│ • UID 1000 (appuser/monitor/audit)      │
│ • Limited file permissions              │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Layer 4: Multi-Stage Builds             │
│ • Build tools NOT in final image        │
│ • Only runtime dependencies             │
│ • Smaller attack surface                │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Layer 5: Health Checks                  │
│ • All services have health checks       │
│ • Automatic restart on failure          │
│ • Monitoring integration                │
└─────────────────────────────────────────┘
```

---

## 🚀 Deployment Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BUILD → TEST → DEPLOY FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

Developer          CI/CD              Registry           Production
─────────           ─────              ─────────          ───────────

┌─────────┐
│ git push│
└────┬────┘
     │
     ▼
┌──────────────┐
│ GitHub       │
│ Actions      │
└──────┬───────┘
       │
       ├─► Build using appropriate Dockerfile
       │   • Rust: docker/Dockerfile.rust
       │   • Python: docker/Dockerfile.python
       │
       ├─► Run Tests
       │   • Unit tests
       │   • Integration tests
       │   • Security scan
       │
       ├─► Tag Image
       │   • nuniesmith/fks:service
       │   • nuniesmith/fks:service-v1.2.3
       │
       ▼
┌──────────────┐
│ DockerHub    │
│ Push         │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Production   │
│ Pull & Run   │
└──────────────┘
       │
       ├─► docker compose pull
       ├─► docker compose up -d
       └─► Health check monitoring
```

---

## 📚 Documentation Structure

```
docker/
├── README.md              # Complete architecture guide (500+ lines)
│   ├── Base Dockerfiles usage
│   ├── Service-specific builds
│   ├── GPU configuration
│   └── Troubleshooting
│
├── MIGRATION.md           # Migration from old structure (460+ lines)
│   ├── Before/After comparison
│   ├── Build command changes
│   ├── Verification steps
│   └── Checklist
│
├── QUICKSTART.md          # Quick reference (440+ lines)
│   ├── Common commands
│   ├── Cheat sheet
│   ├── Examples
│   └── Troubleshooting
│
└── ARCHITECTURE.md        # This file - Visual diagrams
    ├── Architecture overview
    ├── Build flows
    ├── Decision trees
    └── Security layers
```

---

**Last Updated:** 2024  
**Version:** 2.0  
**Maintainer:** FKS Platform Team