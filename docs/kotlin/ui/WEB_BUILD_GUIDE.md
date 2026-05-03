# FKS Web Build Integration Guide

**Date:** 2024-12-30  
**Status:** ✅ Complete - Integrated into run.sh  
**Version:** 1.0.0

---

## Overview

The FKS Trading Platform web UI is built using **Kotlin Multiplatform (KMP)**, specifically targeting JavaScript/browser. The build process has been fully integrated into the Docker workflow via the `run.sh` script.

---

## Quick Start

### Method 1: Automatic Build (Recommended)

The web app is **automatically built** when you start the system:

```bash
./run.sh start
```

This will:
1. Build the KMP web application from source
2. Copy artifacts to `src/clients/web/dist/`
3. Build Docker images (including web service)
4. Start all services

### Method 2: Build Only Web App

To rebuild just the web application:

```bash
./run.sh build-web
```

Then restart the web service:

```bash
./run.sh restart web
```

### Method 3: Manual Build Script

Use the standalone build script for more control:

```bash
# Production build
./scripts/build-web.sh

# Development build with source maps
./scripts/build-web.sh --dev

# Clean and build
./scripts/build-web.sh --clean

# Watch mode (auto-rebuild on changes)
./scripts/build-web.sh --watch
```

---

## Integration Details

### Changes Made to run.sh

#### 1. Enhanced `build_kmp_web()` Function

**Location:** Lines 167-256

**Features:**
- Cleans previous builds
- Runs Gradle `:web:jsBrowserDistribution` task
- Copies artifacts from `build/distributions/` to `dist/`
- Verifies output (index.html, JS files)
- Provides detailed feedback

**Usage:**
```bash
build_kmp_web
```

#### 2. Integrated into `cmd_start()`

**Location:** Step 4.5 in cmd_start function

The web build now runs **before Docker image building** in development mode:

```bash
./run.sh start     # Automatically builds web app
./run.sh up        # Also builds web app
```

**Workflow:**
1. Generate .env file
2. Create SSL volumes
3. **→ Build KMP web app** ← NEW
4. Build Docker images
5. Start services

#### 3. Integrated into `cmd_build()`

**Location:** Lines 710-721

When building services, the web app is built first if:
- No specific services are specified, OR
- `web` is in the service list

```bash
./run.sh build        # Builds web + all services
./run.sh build web    # Builds only web app + web service
```

#### 4. Added `build-web` Command

**Location:** Lines 1190-1200

Standalone command to build just the web application:

```bash
./run.sh build-web
```

Returns exit code 0 on success, 1 on failure.

---

## File Structure

### Source Files

```
src/clients/web/
├── src/
│   ├── jsMain/
│   │   ├── kotlin/xyz/fkstrading/clients/web/
│   │   │   ├── Main.kt                    # Entry point
│   │   │   ├── SignalMatrixFull.kt        # Signal matrix UI
│   │   │   ├── SignalMatrixWebSocket.kt   # WebSocket integration
│   │   │   ├── WebSocketClient.kt         # WS client
│   │   │   ├── SetupScreen.kt             # Setup screen
│   │   │   └── HealthContent.kt           # Health check
│   │   └── resources/
│   │       └── index.html                 # HTML template
│   └── wasmJsMain/                        # Future WASM support
│       └── resources/
├── build/                                  # Gradle build output
│   └── distributions/                      # Compiled bundles
├── dist/                                   # Docker source (IMPORTANT)
│   ├── index.html                         # Served by nginx
│   ├── fks-web-kmp.js                     # Main JS bundle
│   └── *.js, *.css                        # Additional assets
├── build.gradle.kts                        # Gradle config
└── README.md                               # Documentation
```

### Build Output Flow

```
Kotlin Source (.kt)
    ↓
Gradle Build (:web:jsBrowserDistribution)
    ↓
web/build/distributions/
    ↓
Copy to web/dist/ (build_kmp_web function)
    ↓
Docker COPY web/dist/ → nginx image
    ↓
Served at http://localhost:3002
```

---

## Gradle Configuration

### Build Tasks

**Main Task:**
```bash
cd src/clients
./gradlew :web:jsBrowserDistribution
```

**Available Tasks:**
- `:web:clean` - Clean build artifacts
- `:web:jsBrowserDistribution` - Build JS production bundle
- `:web:jsBrowserDevelopmentRun` - Run dev server
- `:web:wasmJsBrowserDistribution` - Build WASM (when enabled)

### Gradle Properties

**Location:** `src/clients/build.gradle.kts`

**Key Settings:**
- `kotlin.multiplatform` plugin enabled
- `js(IR)` target with browser configuration
- Output: `fks-web-kmp.js` (configurable)
- Distribution directory: `dist/`
- CSS support enabled
- Source maps: enabled in dev, disabled in prod

---

## Docker Integration

### Dockerfile

**Location:** `docker/web/Dockerfile`

```dockerfile
FROM nginx:alpine

# Copy built web assets
COPY src/clients/web/dist /usr/share/nginx/html/

# Copy nginx config
COPY config/nginx/web.conf /etc/nginx/conf.d/default.conf

EXPOSE 3001
```

**Important:** The Dockerfile expects `dist/` to exist with built files.

### Nginx Configuration

**Location:** `config/nginx/web.conf`

**Features:**
- Serves static files from `/usr/share/nginx/html`
- Proxies `/api/*` to Gateway (port 8001)
- Proxies `/ws/*` WebSocket connections
- Health check endpoint at `/health`
- Gzip compression enabled
- Security headers configured
- CORS enabled for API calls

**Port Mapping:**
- Container: 3001
- Host: 3002 (configured in docker-compose.yml)

---

## Build Process Details

### Step-by-Step Process

1. **Pre-build Checks**
   - Verify `src/clients/` directory exists
   - Check for `gradlew` (Gradle wrapper)
   - Make `gradlew` executable if needed

2. **Clean Previous Builds** (optional)
   ```bash
   ./gradlew :web:clean --no-daemon
   ```

3. **Run Gradle Build**
   ```bash
   ./gradlew :web:jsBrowserDistribution --no-daemon
   ```
   - Compiles Kotlin to JavaScript (IR backend)
   - Bundles with Webpack
   - Generates `web/build/distributions/`

4. **Copy Artifacts**
   ```bash
   cp -r web/build/distributions/* web/dist/
   ```

5. **Verify Output**
   - Check `index.html` exists
   - Check for `.js` files
   - Count and display files
   - Show total size

6. **Docker Integration**
   - Dockerfile copies `dist/` to nginx
   - Nginx serves files on port 3001
   - Accessible at `http://localhost:3002`

---

## Troubleshooting

### Issue: Web UI Shows "Building..." Placeholder

**Cause:** Web app not built before Docker image creation

**Solution:**
```bash
./run.sh build-web
./run.sh restart web
```

### Issue: "gradlew not found"

**Cause:** Gradle wrapper missing or incorrect path

**Solution:**
```bash
cd src/clients
chmod +x gradlew
./gradlew --version
```

### Issue: Build Succeeds but dist/ is Empty

**Cause:** Gradle output directory mismatch

**Solution:**
```bash
# Check Gradle output location
ls -la src/clients/web/build/distributions/

# Manually copy if needed
cp -r src/clients/web/build/distributions/* src/clients/web/dist/
```

### Issue: Out of Memory During Build

**Cause:** Insufficient Gradle heap size

**Solution:**
Edit `src/clients/gradle.properties`:
```properties
org.gradle.jvmargs=-Xmx4096m
```

### Issue: Web Service Won't Start

**Cause:** Missing dist/index.html

**Solution:**
Check if placeholder exists:
```bash
cat src/clients/web/dist/index.html
```

If missing, create placeholder or build:
```bash
./run.sh build-web
```

---

## Development Workflow

### Daily Development

1. **Make code changes** in `src/clients/web/src/jsMain/kotlin/`

2. **Rebuild web app:**
   ```bash
   ./run.sh build-web
   ```

3. **Restart service:**
   ```bash
   ./run.sh restart web
   ```

4. **Check browser:** `http://localhost:3002`

### Watch Mode (Auto-rebuild)

```bash
./scripts/build-web.sh --watch
```

Then in another terminal:
```bash
# Every time watch rebuilds, restart service
./run.sh restart web
```

### Full Rebuild

```bash
./scripts/build-web.sh --clean
docker-compose build web
docker-compose up -d web
```

---

## Performance Considerations

### Build Time

- **First build:** 30-60 seconds (downloads dependencies)
- **Incremental build:** 10-20 seconds
- **No-op build:** 2-5 seconds

### Bundle Size

- **Development:** 5-10 MB (with source maps)
- **Production:** 500 KB - 2 MB (minified + gzipped)

### Optimization

**Already configured:**
- Dead code elimination (DCE)
- Minification in production
- Gzip compression in nginx
- Browser caching headers

---

## CI/CD Integration

### Build in CI Pipeline

```yaml
# Example GitHub Actions
steps:
  - name: Build Web App
    run: ./scripts/build-web.sh --prod

  - name: Build Docker Image
    run: docker-compose build web

  - name: Push to Registry
    run: docker-compose push web
```

### Production Deployment

```bash
# 1. Build optimized bundle
./scripts/build-web.sh --prod

# 2. Build Docker image
docker-compose build web

# 3. Tag for production
docker tag fks-web:latest fks-web:v1.0.0

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d web
```

---

## Testing

### Manual Testing

1. Build and deploy:
   ```bash
   ./run.sh build-web && ./run.sh restart web
   ```

2. Open browser: `http://localhost:3002`

3. Test features:
   - Signal matrix loads
   - WebSocket connects
   - API calls work
   - Health check responds

### Browser Console

Check for errors:
```
F12 → Console Tab
```

Check WebSocket:
```
F12 → Network Tab → WS filter
```

---

## Maintenance

### Update Dependencies

Edit `src/clients/build.gradle.kts`:
```kotlin
implementation("io.ktor:ktor-client-core:2.3.7")
```

Then rebuild:
```bash
./scripts/build-web.sh --clean
```

### Clean Build Cache

```bash
cd src/clients
./gradlew clean cleanBuildCache
rm -rf .gradle .kotlin build
```

---

## Next Steps

### Future Enhancements

- [ ] Enable WebAssembly (WASM) target for better performance
- [ ] Add automated tests (Karma, Jest)
- [ ] Implement code splitting for faster initial load
- [ ] Add PWA support (service worker, offline mode)
- [ ] Integrate TradingView charting library
- [ ] Add Storybook for component development

### Documentation Updates

- Add API documentation for web components
- Create component showcase
- Add troubleshooting guide for common issues
- Document WebSocket message protocol

---

## Summary

The KMP web build is now **fully integrated** into the FKS Docker workflow:

✅ **Automatic build** when starting system (`./run.sh start`)  
✅ **Standalone build** command (`./run.sh build-web`)  
✅ **Manual build script** (`./scripts/build-web.sh`)  
✅ **Docker integration** (Dockerfile + nginx config)  
✅ **Verification** (checks for index.html and JS files)  
✅ **Documentation** (README + this guide)

**Access the Web UI:**
```
http://localhost:3002
```

**Quick Commands:**
```bash
./run.sh start           # Build + start everything
./run.sh build-web       # Build only web app
./run.sh restart web     # Restart web service
./scripts/build-web.sh   # Standalone build script
```

---

**Status:** ✅ Ready for Production  
**Last Updated:** 2024-12-30  
**Maintainer:** nuniesmith