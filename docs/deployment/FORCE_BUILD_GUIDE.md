# 🚀 Force Build Guide - FKS Trading Systems

This guide explains all the ways to force Docker builds when the automatic change detection skips building services.

## 🎯 Quick Force Build Methods

### **Method 1: GitHub Actions UI (Recommended)**

1. **Go to GitHub Actions**:
   - Navigate to: `https://github.com/nuniesmith/fks/actions`
   - Click on **"🚀 FKS Trading Systems - Deployment Pipeline"**

2. **Run Workflow with Force Options**:
   - Click **"Run workflow"** button
   - Select these options:
     ```
     Deployment mode: builds-only          (just builds, no deploy)
     Build Options: force-rebuild-all      (builds everything)
     Environment: development              (or staging/production)
     Enable CPU builds: ✓ true            (api, worker, data, web, nginx, ninja-api)
     Enable GPU builds: ✓ true            (training, transformer - optional)
     ```

3. **Alternative Build Options**:
   - `force-rebuild-cpu` - Only CPU services (api, worker, data, web, nginx, ninja-api)
   - `force-rebuild-gpu` - Only GPU services (training, transformer)
   - `force-rebuild-all` - All services (CPU + GPU)
   - `clean-and-build` - Clean cache and rebuild

### **Method 2: Commit Message Triggers (New!)**

Simply include specific keywords in your commit message:

```bash
# Any of these patterns will trigger a force rebuild:
git commit -m "force rebuild all services"
git commit -m "rebuild force - fix deployment"
git commit -m "force build everything"
git commit -m "build force for production"

# Then push:
git push
```

**Supported Keywords**: `force rebuild`, `rebuild force`, `force build`, `build force`

### **Method 3: Empty Commit (Quick)**

```bash
# Create an empty commit with force keyword:
git commit --allow-empty -m "force: rebuild all Docker images"
git push
```

### **Method 4: Environment Variables Override**

If you have access to workflow settings, you can set:
```yaml
env:
  FORCE_REBUILD_ALL: true
```

## 📋 Service Categories

### **CPU Services** (Built on standard runners)
- `api` - Main API service (FastAPI/Python)
- `worker` - Background task processor
- `data` - Data management service
- `web` - React frontend application
- `nginx` - Web server and reverse proxy
- `ninja-api` - NinjaTrader integration API

### **GPU Services** (Require GPU runners)
- `training` - ML model training service
- `transformer` - AI transformer models

## 🔍 Debug Information

The enhanced workflow now shows debug output:

```
🔍 Debug - Input Values:
  github.event.inputs.enable_cpu_builds: 'true'
  github.event.inputs.build_options: 'force-rebuild-all'
  needs.detect-changes.outputs.force_rebuild: 'true'

🔍 Debug - Computed Values:
  ENABLE_CPU: 'true'
  FORCE_CPU: 'true'
  FORCE_GENERAL: 'true'
```

## ⚡ Performance Benefits

With the optimized build system:
- **Concurrent Building**: All services build in parallel
- **Batch Pushing**: Images pushed together to Docker Hub
- **60-70% Faster**: Compared to old sequential builds
- **Better Resource Usage**: Efficient CPU and memory utilization

## 🛠️ Troubleshooting

### **Issue: "No services to build"**
- **Cause**: Force flags not properly set
- **Solution**: Use Method 1 (GitHub UI) with explicit force options

### **Issue: "Services skipped despite force flag"**
- **Cause**: Change detection overriding force logic
- **Solution**: Check debug output, use `force-rebuild-all` option

### **Issue: "Build fails due to disk space"**
- **Cause**: Concurrent builds using more disk space
- **Solution**: Enhanced cleanup runs automatically, should resolve itself

### **Issue: "GPU builds not running"**
- **Cause**: GPU builds require explicit enablement
- **Solution**: Set `Enable GPU builds: true` in workflow UI

## 📊 Build Time Comparison

| Method | Time | Services | Notes |
|--------|------|----------|-------|
| Old Sequential CPU | 28-35 min | 6 services | One at a time |
| Old Sequential GPU | 12-16 min | 2 services | One at a time |
| **New Optimized** | **15-20 min** | **All 8 services** | **Concurrent** |

## 🔗 Quick Links

- [GitHub Actions](https://github.com/nuniesmith/fks/actions)
- [Docker Build Optimization Summary](./DOCKER_BUILD_OPTIMIZATION_SUMMARY.md)
- [Main Workflow File](../.github/workflows/00-complete.yml)

## 📝 Notes

- Force builds ignore change detection completely
- All force rebuild options also push to Docker Hub
- GPU services require appropriate runners (not always available)
- `builds-only` mode skips deployment, only builds and pushes images
- Debug output helps troubleshoot force build issues

---

**Last Updated**: July 26, 2025  
**Workflow Version**: Optimized Concurrent Builds v1.0
