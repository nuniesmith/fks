# Kotlin Multiplatform Web Build Guide

This document explains how to build and deploy the FKS Trading Platform web interface.

## Overview

The FKS web interface is built using **Kotlin Multiplatform (KMP)** with targets for:
- **JavaScript (JS)** - Standard browser compatibility
- **WebAssembly (Wasm)** - High-performance charting and real-time data visualization

## Quick Start

### Automatic Build (Recommended)

The web application is automatically built when you start services:

```bash
./run.sh up          # Builds web app, then starts all services
./run.sh start       # Same as above, with env setup
```

### Manual Build

To build only the web application without starting services:

```bash
./run.sh build-web
```

Or build everything including web:

```bash
./run.sh build
```

## Project Structure

```
src/clients/
├── build.gradle.kts          # Root build configuration
├── settings.gradle.kts       # Project settings
├── gradlew                   # Gradle wrapper (Unix)
├── gradlew.bat              # Gradle wrapper (Windows)
└── web/
    ├── build.gradle.kts      # Web module config
    ├── dist/                 # Build output (copied here for Docker)
    │   └── index.html        # Placeholder (replaced on build)
    ├── build/
    │   └── distributions/    # Gradle build output
    └── src/
        ├── jsMain/           # JavaScript-specific code
        └── wasmJsMain/       # WebAssembly-specific code
```

## Build Process

### What Happens During Build

1. **Gradle checks** - Verifies Gradle wrapper exists and is executable
2. **KMP compilation** - Compiles Kotlin to JavaScript and WebAssembly
3. **Webpack bundling** - Bundles assets, applies tree-shaking, and optimizes
4. **Output copying** - Copies `build/distributions/` → `dist/` for Docker
5. **Docker preparation** - Web service can now be built/restarted

### Build Outputs

| Target | Output File | Location |
|--------|-------------|----------|
| JS | `fks-web-kmp.js` | `web/build/distributions/` |
| Wasm | `fks-web-wasm.js` | `web/build/distributions/` |
| Assets | `*.html`, `*.css` | `web/build/distributions/` |

## Docker Integration

### Web Service

The `web` service in `docker-compose.yml`:
- **Image**: `nginx:alpine`
- **Port**: `3001` (internal), exposed on host
- **Volume**: Mounts `src/clients/web/dist` as read-only
- **Config**: Uses `config/nginx/web.conf` for serving

### Reverse Proxy

Nginx (main reverse proxy) routes traffic:
- **`/`** → `web:3001` (KMP web UI)
- **`/api/`** → `gateway:8000` (Backend API)
- **`/ws/`** → `gateway:8000` (WebSocket)
- **`/audit`** → `audit:8080` (Code analysis)

## Development Workflow

### Initial Setup

```bash
# First time setup
./run.sh start

# This will:
# 1. Generate .env with secrets
# 2. Build KMP web app
# 3. Build all Docker images
# 4. Start all services
```

### Rebuilding After Code Changes

```bash
# Option 1: Rebuild web and restart service
./run.sh build-web
docker-compose restart web

# Option 2: Use run.sh helper
./run.sh restart web

# Option 3: Full rebuild
./run.sh build web
./run.sh up web
```

### Watching for Changes (Development)

For active development, you can use Gradle's continuous build:

```bash
cd src/clients
./gradlew :web:jsBrowserDevelopmentRun --continuous
```

This starts a dev server on port 8080 with hot reload.

## Troubleshooting

### Build Failures

**Problem**: Gradle wrapper not found
```bash
Error: Gradle wrapper not found at src/clients/gradlew
```

**Solution**: Ensure you're in the project root and the wrapper exists:
```bash
ls -la src/clients/gradlew
# If missing, regenerate:
cd src/clients && gradle wrapper --gradle-version 8.5
```

---

**Problem**: Permission denied on gradlew
```bash
Error: Permission denied
```

**Solution**: Make gradlew executable (run.sh does this automatically):
```bash
chmod +x src/clients/gradlew
```

---

**Problem**: Node.js version mismatch
```bash
Error: Node.js version X is not supported
```

**Solution**: Check `gradle.properties` for Node.js settings:
```properties
kotlin.js.nodejs.download=false  # Uses system Node.js
```

Ensure you have Node.js 18+ installed:
```bash
node --version  # Should be v18.0.0 or higher
```

### Docker Issues

**Problem**: Web service shows placeholder page

**Solution**: Build hasn't run or failed silently
```bash
./run.sh build-web
docker-compose restart web
```

---

**Problem**: 502 Bad Gateway on root path

**Possible causes**:
1. Web service not healthy: `docker-compose ps web`
2. Nginx config issue: `docker-compose logs nginx`
3. Build output missing: `ls -la src/clients/web/dist/`

**Solution**:
```bash
# Check web service
docker-compose ps web

# View web service logs
docker-compose logs web

# Rebuild if needed
./run.sh build-web
docker-compose restart web
```

---

**Problem**: CORS errors in browser console

**Solution**: The web.conf already includes CORS headers, but check:
```bash
# View current nginx config
docker-compose exec web cat /etc/nginx/conf.d/default.conf

# Should have Access-Control-Allow-Origin headers
```

## Configuration Files

### Nginx Web Config

Location: `config/nginx/web.conf`

Key settings:
- Serves static files from `/usr/share/nginx/html`
- Health check at `/health`
- API proxy to `gateway:8001`
- WebSocket support for `/ws/`
- CORS headers for API calls

### Gradle Build Config

Location: `src/clients/web/build.gradle.kts`

Key settings:
```kotlin
js(IR) {
    browser {
        webpackTask {
            mainOutputFileName = "fks-web-kmp.js"
        }
        distribution {
            outputDirectory.set(file("$projectDir/dist"))
        }
    }
}

wasmJs {
    browser {
        webpackTask {
            mainOutputFileName = "fks-web-wasm.js"
        }
    }
}
```

## Performance Optimization

### Production Builds

For production, ensure webpack is optimized:

```bash
cd src/clients
./gradlew :web:jsBrowserProductionWebpack
```

This enables:
- Dead code elimination
- Minification
- Source map generation
- Asset optimization

### Caching

Nginx serves files with cache headers:
```nginx
expires 1h;
add_header Cache-Control "public, immutable";
```

For long-term caching, implement versioned asset names.

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Build KMP Web
  run: |
    cd src/clients
    chmod +x gradlew
    ./gradlew :web:jsBrowserDistribution --no-daemon

- name: Build Docker Image
  run: docker-compose build web

- name: Push Image
  run: docker-compose push web
```

## Advanced Topics

### Multi-Target Development

The web module supports both JS and Wasm. To build specific targets:

```bash
cd src/clients

# JavaScript only
./gradlew :web:jsBrowserDistribution

# WebAssembly only
./gradlew :web:wasmJsBrowserDistribution

# Both (default)
./gradlew :web:build
```

### Custom Webpack Configuration

Edit `web/build.gradle.kts` to customize webpack:

```kotlin
browser {
    commonWebpackConfig {
        cssSupport {
            enabled.set(true)
        }
        // Add custom config here
    }
}
```

### Environment Variables

Pass environment variables to the build:

```bash
export NODE_OPTIONS="--max-old-space-size=4096"
./run.sh build-web
```

## Testing

### Unit Tests

```bash
cd src/clients
./gradlew :web:jsTest
```

### Integration Tests

```bash
# Start services
./run.sh up

# Run tests against live services
cd src/clients
./gradlew :web:jsTestBrowserHeadless
```

## Resources

- [Kotlin Multiplatform Docs](https://kotlinlang.org/docs/multiplatform.html)
- [Compose for Web](https://github.com/JetBrains/compose-multiplatform)
- [Gradle Build Tool](https://gradle.org/)
- [Webpack](https://webpack.js.org/)

## Support

If you encounter issues not covered here:

1. Check the build logs: `./run.sh build-web 2>&1 | tee build.log`
2. Verify Docker status: `./run.sh diagnose`
3. Review service health: `./run.sh health`
4. Check GitHub issues or create a new one

---

**Last Updated**: 2024
**Maintainer**: nuniesmith