# ADR 0009-0034: Cloud Run Deployment

## Status

Accepted

## Context

The RetailTwin AI backend needs to run as a production-ready service on Google Cloud Platform. Cloud Run provides a serverless container platform that scales automatically and integrates with other GCP services.

## Problem

Development runs of FastAPI are not suitable for production:

- No automatic scaling
- No health checks
- No integration with GCP services
- No secret management
- No CI/CD pipeline

## Decision

We deploy the FastAPI backend to Cloud Run with:

1. Containerized deployment via Cloud Build
2. Environment-based configuration
3. Health check endpoints
4. GCP service integration
5. Secret Manager for credentials
6. CI/CD via Cloud Build triggers

## Architecture

```mermaid
flowchart TB
    subgraph GCP["Google Cloud Platform"]
        subgraph CloudRun["Cloud Run"]
            FR[🚀 FastAPI<br/>retailtwin-api]
        end

        subgraph Services["GCP Services"]
            FS[📦 Firestore<br/>Live Twin]
            BQ[📊 BigQuery<br/>Analytics]
            PS[📨 Pub/Sub<br/>Events]
            SM[🔐 Secret Manager<br/>Credentials]
            CL[📋 Cloud Logging<br/>Logs]
        end

        subgraph Build["CI/CD Pipeline"]
            GAR[📦 Artifact Registry]
            CB[🔨 Cloud Build]
            TR[⚡ Cloud Build Trigger]
        end
    end

    subgraph Clients["Clients"]
        WEB[🌐 Web App<br/>Firebase Hosting]
        EXT[🔌 External<br/>Services]
    end

    WEB -->|HTTPS| FR
    EXT -->|HTTPS| FR
    FR <-->|Read/Write| FS
    FR <-->|Query| BQ
    FR <-->|Publish/Subscribe| PS
    FR -->|Read Secrets| SM
    FR -->|Write Logs| CL

    CB -->|Build & Push| GAR
    GAR -->|Deploy| FR
    TR -->|Trigger| CB

    CB -.->|On push to main| TR
```

## CI/CD Pipeline Flow

```mermaid
flowchart LR
    subgraph Source["SOURCE"]
        GH[GitHub<br/>main branch]
    end

    subgraph Build["BUILD"]
        CB[Cloud Build<br/>Trigger]
        DOCKER[Docker Build<br/>+ Push]
        IMG[Artifact Registry<br/>us-central1]
    end

    subgraph Deploy["DEPLOY"]
        CR[Cloud Run<br/>Deploy]
        SA[Service Account<br/>retailtwin-api-sa]
    end

    subgraph Monitor["MONITOR"]
        LOGS[Cloud Logging<br/>Logs]
        METRICS[Cloud Monitoring<br/>Metrics]
    end

    GH -->|Push| CB
    CB -->|Build| DOCKER
    DOCKER -->|Push| IMG
    IMG -->|Deploy| CR
    CR -->|Use| SA
    CR -->|Write| LOGS
    CR -->|Emit| METRICS
```

## Cloud Run Service Configuration

```mermaid
flowchart TB
    subgraph Config["SERVICE CONFIG"]
        subgraph Resource["RESOURCES"]
            CPU[CPU: 2 vCPU]
            MEM[Memory: 1Gi]
            CONC[Concurrency: 80]
            TIMEOUT[Timeout: 300s]
        end

        subgraph Scaling["SCALING"]
            MIN[Min Instances: 0]
            MAX[Max Instances: 10]
        end

        subgraph Health["HEALTH CHECK"]
            LIVE[Liveness Probe<br/>/health every 30s]
            READY[Readiness Probe<br/>/health every 10s]
        end

        subgraph Security["SECURITY"]
            SA[Service Account:<br/>retailtwin-api-sa]
            INGRESS[Ingress:<br/>internal + cloud LB]
        end
    end
```

## Environment Variables

| Variable       | Source         | Description          |
| -------------- | -------------- | -------------------- |
| `ENVIRONMENT`  | Cloud Run      | `production`         |
| `GCP_PROJECT`  | Cloud Run      | Project ID           |
| `GCP_REGION`   | Cloud Run      | `us-central1`        |
| `LOG_LEVEL`    | Cloud Run      | `INFO`               |
| `CORS_ORIGINS` | Cloud Run      | Allowed origins      |
| `credentials`  | Secret Manager | Service account JSON |

## Service Account Roles

```mermaid
flowchart TB
    subgraph SA["Service Account: retailtwin-api-sa"]
        R1[✅ roles/run.invoker]
        R2[✅ roles/firestore.user]
        R3[✅ roles/bigquery.dataEditor]
        R4[✅ roles/pubsub.publisher]
        R5[✅ roles/pubsub.subscriber]
        R6[✅ roles/secretmanager.secretAccessor]
        R7[✅ roles/logging.logWriter]
    end
```

## Deployment Commands

### Initial Deployment

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GCP as Google Cloud
    participant CB as Cloud Build
    participant CR as Cloud Run

    Dev->>GCP: Enable required APIs
    Dev->>GCP: Create Artifact Registry repo
    Dev->>GCP: Create service account
    Dev->>GCP: Grant IAM roles

    Dev->>CB: Submit cloudbuild.yaml
    CB->>CB: Build Docker image
    CB->>GCP: Push to Artifact Registry
    CB->>CR: Deploy to Cloud Run

    CR-->>Dev: Service URL
```

### Commands

```bash
# Set project
gcloud config set project retailtwin-ai-511002

# Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Create repository
gcloud artifacts repositories create retailtwin-api \
  --repository-format=docker --location=us-central1

# Deploy
gcloud builds submit --config=cloudbuild.yaml
```

## Cost Estimation

```mermaid
flowchart LR
    subgraph Resources["Resource Usage"]
        CPU[CPU Time<br/>2 vCPU × 730h<br/>= 5,256 vCPU-s]
        MEM[Memory<br/>1Gi × 730h<br/>= 2,628 GiB-s]
        REQ[Requests<br/>~1M/month]
    end

    subgraph Free["Free Tier (Monthly)"]
        FT_CPU[180,000 vCPU-s]
        FT_MEM[90,000 GiB-s]
        FT_REQ[2M requests]
    end

    subgraph Cost["Actual Cost"]
        C_CPU[$0.00002400/vCPU-s]
        C_MEM[$0.00000250/GiB-s]
        C_REQ[$0.40/million]
    end

    Resources --> Cost
```

### Estimated Monthly Cost

| Resource  | Usage        | Free Tier | Cost       |
| --------- | ------------ | --------- | ---------- |
| CPU       | 5,256 vCPU-s | 180,000   | ~$0.13     |
| Memory    | 2,628 GiB-s  | 90,000    | ~$0.007    |
| Requests  | 1M           | 2M        | ~$0.40     |
| **Total** |              |           | **~$0.54** |

## Monitoring

```mermaid
flowchart TB
    subgraph Metrics["Cloud Monitoring"]
        M1["Error Rate<br/> 1% alert"]
        M2["Latency p99<br/> 2000ms alert"]
        M3["CPU Usage<br/> 80% alert"]
        M4["Memory Usage<br/> 90% alert"]
    end

    subgraph Alerts["Alerting"]
        CHANNEL[Notification Channel<br/>Email/Slack]
        POLICY[Alerting Policy]
    end

    subgraph Actions["Actions"]
        PAGE[On-call Paging]
        AUTO[Auto-scaling]
    end

    M1 --> POLICY
    M2 --> POLICY
    M3 --> POLICY
    M4 --> POLICY
    POLICY --> CHANNEL
    CHANNEL --> PAGE
    POLICY --> AUTO
```

## Troubleshooting

```mermaid
flowchart TB
    subgraph Issue["Common Issues"]
        I1[503 Service Unavailable]
        I2[Cold start timeout]
        I3[Permission denied]
        I4[Out of memory]
    end

    subgraph Cause["Causes"]
        C1[Health check failing]
        C2[Init taking too long]
        C3[Missing IAM role]
        C4[Memory limit too low]
    end

    subgraph Solution["Solutions"]
        S1[Check /health endpoint]
        S2[Increase startupTimeout]
        S3[Add required roles]
        S4[Increase memory]
    end

    I1 --> C1
    I2 --> C2
    I3 --> C3
    I4 --> C4

    C1 --> S1
    C2 --> S2
    C3 --> S3
    C4 --> S4
```

## Local Development

```mermaid
flowchart TB
    subgraph Local["Local Development"]
        API[FastAPI<br/>localhost:8000]
        FE[Firestore Emulator<br/>localhost:8080]
        PS[Pub/Sub Emulator<br/>localhost:8085]
    end

    API -->|Connect| FE
    API -->|Connect| PS
```

## Related Issues

- #9: [DAY-0] Deploy MVP API to Cloud Run
- #34: [D12] Productionize backend services on Cloud Run

## Implementation Files

```
infrastructure/gcp/
├── cloudbuild.yaml           # Cloud Build config
├── cloud_run_service.yaml    # Cloud Run spec
├── Dockerfile              # Container build
└── README.md               # Runbook
```

## Verification Checklist

- [ ] Service deploys successfully
- [ ] Health check passes
- [ ] Can reach Firestore
- [ ] Can reach BigQuery
- [ ] Can publish/subscribe to Pub/Sub
- [ ] Secrets accessible via Secret Manager
- [ ] Logs appear in Cloud Logging
- [ ] Metrics appear in Cloud Monitoring
- [ ] Rollback works
- [ ] CI/CD pipeline works
