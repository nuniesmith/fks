# Kubernetes Resources

Kubernetes manifests and Helm charts for JANUS Vision.

## Structure

- `base/` - Common resources (RBAC, namespaces, network policies)
- `components/` - Reusable components (monitoring, security, data, vision)
- `overlays/` - Environment-specific configurations (kustomize)
- `helm/` - Helm charts

## Deployment

### Using Helm
```bash
cd helm/vision
helm install vision . --namespace vision-prod --create-namespace
```

### Using Kustomize
```bash
kubectl apply -k overlays/production/
```

## Environments

- **development** - Local/dev cluster
- **staging** - Staging environment
- **production** - Production cluster

