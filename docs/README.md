# FKS Platform Documentation

**Version**: 1.0.0
**Last Updated**: October 17, 2025  
**Active Documentation**: 18 essential files

---

## 🚀 Quick Start

**New to FKS?** Start here:

1. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand the system
3. **[setup/ENVIRONMENT_SETUP.md](setup/ENVIRONMENT_SETUP.md)** - Configure environment

---

## 📚 Documentation Index

### 📖 Core

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture  
- [INDEX.md](INDEX.md) - Legacy index

### 🔧 Setup (6 files)

Located in `setup/`

- ENVIRONMENT_SETUP.md - Environment configuration
- ENVIRONMENT_GUIDE.md - Detailed environment guide
- LOCAL_DEV_DOMAIN_SETUP.md - Local domain setup
- LOCAL_HOSTS_SETUP.md - Hosts configuration
- DOCKER_IMAGES.md - Docker images info
- CLOUDFLARE_SSL_SETUP_GUIDE.md - SSL configuration

### 🚀 Deployment (7 files)

Located in `deployment/`

- **DEPLOYMENT.md** - Main deployment guide
- **SECRETS.md** - All secrets (consolidated) ✨ NEW
- DEPLOYMENT_TROUBLESHOOTING.md - Troubleshooting
- GITHUB_ACTIONS.md - CI/CD setup
- LINODE_AUTOMATION_GUIDE.md - Linode deployment
- DOCKER_BUILD_OPTIMIZATION.md - Build optimization
- FORCE_BUILD_GUIDE.md - Force rebuild

### ✨ Features (7 files)

Located in `features/`

- TRADING_GUIDE.md - Trading features
- RAG_SETUP_GUIDE.md - RAG system
- LOCAL_LLM_SETUP.md - Local LLM with GPU
- FKS_INTELLIGENCE_QUICK_REF.md - Intelligence API
- AUTH_QUICKSTART.md - Authentication
- GAMIFICATION_IMPLEMENTATION.md - Gamification
- DATA_PROVIDERS.md - Data providers

### ⚙️ Operations (3 files)

Located in `operations/`

- NGINX_QUICKREF.md - Nginx commands
- TROUBLESHOOTING_GUIDE.md - Problem resolution
- GITHUB_SECRETS_QUICKREF.md - Secrets reference

### 💻 Development (2 files)

Located in `development/`

- DEVELOPMENT_GUIDE.md - Development workflow
- TESTING_GUIDE.md - Testing guide

### 📦 Archived (83 files)

Located in `archived/` - Historical documentation

---

## 🎯 Common Tasks

### Setup Locally

```bash
./start.sh start
```

See: [QUICKSTART.md](QUICKSTART.md)

### Deploy to Production

```bash
git push origin main  # Auto-deploys via GitHub Actions
```

See: [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md)

### Configure Secrets

See: [deployment/SECRETS.md](deployment/SECRETS.md)

### Enable RAG

```bash
./start.sh --gpu start  # Local LLM (free)
```

See: [features/RAG_SETUP_GUIDE.md](features/RAG_SETUP_GUIDE.md)

---

## 📊 Cleanup Summary

**Before**: 111 files (chaotic)  
**After**: 28 files (organized)  
**Reduction**: 73%

- Deleted 63 historical/fix reports
- Consolidated 14 secrets docs → 1
- Organized into 6 categories
- Archived 83 old files

---

## 🆘 Need Help?

- **Quick commands**: [../QUICKREF.md](../QUICKREF.md)
- **Troubleshooting**: [operations/TROUBLESHOOTING_GUIDE.md](operations/TROUBLESHOOTING_GUIDE.md)
- **View logs**: `./start.sh logs`

---

**Last Updated**: October 17, 2025 - Major documentation cleanup
