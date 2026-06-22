# Kubernetes Deployment

Deploy OutplayLabs Arena on Kubernetes using the Helm chart for production deployments.

## Prerequisites

- Kubernetes cluster (1.24+)
- Helm 3
- Traefik Ingress Controller (with CRDs)
- Container registry for images
- PostgreSQL-compatible storage class

## Quick Start

```bash
# Add Helm repo (or use local chart)
# helm repo add arena https://...

# Configure values
cp helm/arena/values.yaml my-values.yaml
# Edit my-values.yaml

# Deploy
helm upgrade --install arena helm/arena \
  --namespace arena --create-namespace \
  -f my-values.yaml

# Wait for deployment
kubectl -n arena rollout status deployment/arena-backend

# Port-forward for local access
kubectl -n arena port-forward svc/arena-backend 8000:8000
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Traefik Ingress Controller    │
└──────────────────┬──────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    │                             │
┌───▼──────────┐          ┌──────▼───────┐
│   Backend    │          │  MCP Servers │
│  Deployment  │          │   (Jobs)     │
│  (1-10 pods) │          │              │
└──────┬───────┘          └──────────────┘
       │
┌──────▼───────┐
│  PostgreSQL  │
│  StatefulSet │
│  (10Gi PVC)  │
└──────────────┘
```

## Configuration

### values.yaml

```yaml
# Backend configuration
backend:
  image:
    repository: your-registry/arena-backend
    tag: latest
    pullPolicy: Always
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 2Gi

# Database configuration
database:
  storageClassName: standard
  storage: 10Gi
  createPV: false  # Set true for persistent PV

# MCP server configuration
mcpServer:
  image:
    repository: your-registry/arena-mcp
    tag: latest
  maxConcurrentJobs: 50
  jobTTL: 300
  publicBaseUrl: "https://api.agent-arena.local"

# OAuth configuration
oauth:
  github:
    clientId: ""
    clientSecret: ""
  google:
    clientId: ""
    clientSecret: ""
  jwtSecret: "your-jwt-secret"
  callbackBaseUrl: "https://agent-arena.local"

# Traefik configuration
traefik:
  host: "agent-arena.local"
  apiHost: "api.agent-arena.local"
  certResolver: "letsencrypt"  # Optional
```

### Secrets

Secrets are managed via Helm values or external secret manager:

```bash
# Generate JWT secret
openssl rand -hex 32

# Create secret manually
kubectl -n arena create secret generic arena-secrets \
  --from-literal=jwt-secret=your-jwt-secret \
  --from-literal=github-client-id=... \
  --from-literal=github-client-secret=...
```

## Building and Pushing Images

### Backend

```bash
cd backend/docker
docker build -t your-registry/arena-backend:latest .
docker push your-registry/arena-backend:latest
```

### MCP

```bash
cd backend/docker
docker build -f Dockerfile.mcp -t your-registry/arena-mcp:latest .
docker push your-registry/arena-mcp:latest
```

## Database

### Initial Setup

The Helm chart deploys PostgreSQL as a StatefulSet with a PersistentVolumeClaim.

### External Database

To use an external PostgreSQL:

```yaml
database:
  enabled: false

backend:
  env:
    - name: DATABASE_URL
      value: "postgresql+asyncpg://user:pass@external-db:5432/outplaylabs-arena"
```

### Migrations

Migrations run as a Kubernetes Job on deployment:

```bash
# Check migration status
kubectl -n arena get jobs
kubectl -n arena logs job/arena-migrations

# Run migrations manually
kubectl -n arena exec -it deployment/arena-backend -- \
  alembic -c /app/alembic.ini upgrade head
```

### Backup

```bash
# Backup database
kubectl -n arena exec -it statefulset/arena-db -- \
  pg_dump -U outplaylabs-arena outplaylabs-arena > backup.sql

# Restore database
cat backup.sql | kubectl -n arena exec -i statefulset/arena-db -- \
  psql -U outplaylabs-arena outplaylabs-arena
```

## Scaling

### Backend

The Helm chart includes HorizontalPodAutoscaler:

```yaml
backend:
  hpa:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilization: 70
    targetMemoryUtilization: 80
```

### Database

Database is a StatefulSet (single instance). For production:
- Use managed PostgreSQL (RDS, Cloud SQL, etc.)
- Configure read replicas
- Set up automated backups

## MCP Gateway

### RBAC

The backend needs permissions to create MCP resources:

```yaml
# helm/arena/templates/mcp-server/rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: arena-mcp-manager
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "delete", "get", "list"]
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["create", "delete", "get", "list"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["create", "delete", "get", "list"]
```

### Ingress

Each MCP pod gets its own Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-abc123
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: arena-strip-mcp-prefix@kubernetescrd
spec:
  rules:
    - host: api.agent-arena.local
      http:
        paths:
          - path: /mcp/mcp-abc123
            pathType: Prefix
            backend:
              service:
                name: mcp-abc123
                port:
                  number: 8000
```

## Monitoring

### Health Checks

```bash
# Check backend health
kubectl -n arena exec -it deployment/arena-backend -- \
  curl http://localhost:8000/api/health

# Check database
kubectl -n arena exec -it statefulset/arena-db -- \
  pg_isready -U arena
```

### Logs

```bash
# Backend logs
kubectl -n arena logs deployment/arena-backend -f

# Database logs
kubectl -n arena logs statefulset/arena-db -f

# MCP pod logs
kubectl -n arena logs pod/mcp-abc123
```

### Metrics

Expose metrics for Prometheus:

```yaml
backend:
  serviceMonitor:
    enabled: true
```

## Updating

```bash
# Update Helm chart
helm upgrade arena helm/arena \
  --namespace arena \
  -f my-values.yaml

# Rollback if needed
helm rollback arena 1

# Check rollout status
kubectl -n arena rollout status deployment/arena-backend
```

## Production Checklist

- [ ] Use external PostgreSQL (RDS, Cloud SQL)
- [ ] Configure TLS certificates
- [ ] Set up automated backups
- [ ] Configure resource limits
- [ ] Enable monitoring and alerting
- [ ] Set up CI/CD pipeline
- [ ] Configure OAuth providers
- [ ] Set strong JWT secret
- [ ] Review security settings
- [ ] Test disaster recovery
- [ ] Configure Cloudflare Pages for documentation

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl -n arena describe pod <pod-name>

# Check logs
kubectl -n arena logs <pod-name>

# Check PVC
kubectl -n arena get pvc
```

### Database Connection Issues

```bash
# Test connectivity
kubectl -n arena exec -it deployment/arena-backend -- \
  python -c "import asyncpg; asyncpg.connect('...')"

# Check database service
kubectl -n arena get svc arena-db
```

### MCP Pods Stuck

```bash
# List MCP pods
kubectl -n arena get pods -l app=mcp-server

# Delete stuck pods
kubectl -n arena delete pod mcp-abc123

# Check backend logs
kubectl -n arena logs deployment/arena-backend | grep mcp
```

## Next Steps

- [Docker Deployment](docker.md) — Local development
- [Configuration Reference](configuration.md) — All environment variables
- [MCP Setup](../mcp/setup.md) — MCP server configuration
