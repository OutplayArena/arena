# Kubernetes & Helm

Deploy OutplayArena on Kubernetes using the included Helm chart. The chart deploys all components with production-grade configuration: HPA for the backend, StatefulSets for the database and Redis, and RBAC for MCP pod management.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.9+
- Traefik Ingress Controller with CRDs installed
- A container registry (or use Docker Hub images directly)
- A storage class supporting `ReadWriteOnce` volumes

## Quick Deploy

```bash
# Copy and customize values
cp helm/arena/values.yaml my-values.yaml
$EDITOR my-values.yaml

# Deploy
helm upgrade --install arena helm/arena/ \
  --namespace arena --create-namespace \
  -f my-values.yaml

# Wait for rollout
kubectl -n arena rollout status deployment/arena-backend
```

## What the Chart Deploys

| Resource | Type | Description |
|---|---|---|
| `arena-backend` | Deployment + HPA | FastAPI backend, scales 1–10 replicas |
| `arena-db` | StatefulSet + PVC | PostgreSQL 16 with 10 Gi persistent storage |
| `arena-redis` | StatefulSet + PVC | Redis 7 with 2 Gi persistent storage |
| `arena-mcp-server` | Deployment | Always-on MCP server (2 replicas by default) |
| `arena-migrations` | Job | Runs Alembic migrations on deploy |
| `arena-docs` | Deployment | MkDocs documentation site |
| Traefik IngressRoutes | CRD | Routing rules for backend and MCP |
| RBAC | Role + RoleBinding | Permissions for MCP pod/job management |
| Secrets | Secret | OAuth credentials, JWT secret, DB password |

## Key values.yaml Options

```yaml
# Image configuration
backend:
  image:
    repository: her3ert/outplayarena-backend
    tag: v0.1.0
    pullPolicy: Always
  replicas: 1
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
  hpa:
    enabled: true
    minReplicas: 1
    maxReplicas: 10
    targetCPUUtilization: 70
    targetMemoryUtilization: 80

mcpServer:
  image:
    repository: her3ert/outplayarena-mcp
    tag: v0.1.0
  replicas: 2
  port: 9999
  resources:
    requests:
      cpu: 100m
      memory: 64Mi
    limits:
      cpu: 500m
      memory: 256Mi

database:
  image: postgres:16-alpine
  storage: 10Gi
  storageClassName: standard   # set to your cluster's storage class

redis:
  image: redis:7-alpine
  storage: 2Gi
  storageClassName: standard

# Traefik host routing
traefik:
  host: arena.example.com
  certResolver: letsencrypt    # optional, if Traefik manages TLS

# OAuth and secrets
oauth:
  github:
    clientId: ""
    clientSecret: ""
  google:
    clientId: ""
    clientSecret: ""
  jwtSecret: ""                # openssl rand -hex 32
  callbackBaseUrl: "https://arena.example.com"
```

## Deployment Workflow

The chart uses a Kubernetes Job (`arena-migrations`) as an init step before the backend starts. The backend deployment waits for the migration Job to complete before becoming available. On updates:

1. `helm upgrade` triggers a new migration Job
2. Migrations run against the existing database
3. Backend deployment rolls out with the new image

Check migration status:

```bash
kubectl -n arena get jobs
kubectl -n arena logs job/arena-migrations
```

## Using an External Database

To use a managed PostgreSQL (RDS, Cloud SQL, etc.) instead of the in-cluster StatefulSet:

```yaml
database:
  enabled: false

backend:
  env:
    - name: DATABASE_URL
      value: "postgresql+asyncpg://user:pass@your-managed-db:5432/outplayarena"
```

## Secrets Management

The chart creates a Kubernetes Secret from `values.yaml`. For production, pass secrets via `--set` flags at deploy time (not stored in values files):

```bash
helm upgrade --install arena helm/arena/ \
  --namespace arena \
  -f my-values.yaml \
  --set oauth.jwtSecret="$(openssl rand -hex 32)" \
  --set oauth.github.clientId="$GITHUB_CLIENT_ID" \
  --set oauth.github.clientSecret="$GITHUB_CLIENT_SECRET"
```

Or use an external secrets manager (Vault, AWS Secrets Manager, External Secrets Operator) and patch the Secret separately.

## MCP on Kubernetes

The backend spawns MCP sessions as Kubernetes Jobs via the RBAC Role granted by the chart. Each game session creates a short-lived MCP Job that is cleaned up after `MCP_JOB_TTL` seconds.

The backend needs the following RBAC permissions (included in the chart):

```yaml
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

## Scaling

The backend HPA scales between `minReplicas` and `maxReplicas` based on CPU and memory usage. PostgreSQL is a single-instance StatefulSet — for high-traffic production deployments, use a managed PostgreSQL with read replicas.

## Monitoring

```bash
# Check backend health
kubectl -n arena exec -it deployment/arena-backend -- \
  curl http://localhost:8000/api/health

# Stream backend logs
kubectl -n arena logs deployment/arena-backend -f

# List MCP jobs
kubectl -n arena get jobs -l app=mcp-server

# Check resource usage
kubectl -n arena top pods
```

## Updates and Rollbacks

```bash
# Update image tag in values and upgrade
helm upgrade arena helm/arena/ -n arena -f my-values.yaml

# Check rollout
kubectl -n arena rollout status deployment/arena-backend

# Rollback to previous release if needed
helm rollback arena 1 -n arena
```

## Production Checklist

- [ ] Use external managed PostgreSQL (not the in-cluster StatefulSet)
- [ ] Configure TLS (via Traefik certResolver or external cert manager)
- [ ] Set up automated database backups
- [ ] Configure HPA with appropriate resource limits
- [ ] Use external secrets management (not values.yaml)
- [ ] Set `CORS_ALLOW_ORIGINS` to your specific domain
- [ ] Set strong `JWT_SECRET` (64+ hex chars)
- [ ] Review RBAC permissions — scope to the `arena` namespace
- [ ] Enable Kubernetes audit logging
