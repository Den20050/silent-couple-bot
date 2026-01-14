┌─────────────────────────────────────────────────────────────────────────────┐
│ Telegram Users (Web/Mobile/Desktop)                                         │
│  ├─ User A (Mode: 'silent') → Isolated chat with bot                      │
│  └─ User B (Mode: 'chat') → Personal chat with partner + bot integration │
└─────────────────┬───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Cloudflare (WAF + DDoS Protection + CDN)                                    │
│  ├─ HTTPS termination                                                       │
│  └─ Rate limiting (100 req/s per IP)                                       │
└─────────────────┬───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ VPS (MTS Cloud/Selectel, Moscow) — 152-ФЗ Compliant                         │
│  OS: Ubuntu 22.04 LTS                                                       │
│  Specs: 2 vCPU, 4 GB RAM, 40 GB SSD                                         │
└─────────────────┬───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Docker Swarm / Docker Compose Stack                                         │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  N8N Main (primary instance)                                         │ │
│  │    - Webhook receiver                                                │ │
│  │    - Workflow orchestrator                                           │ │
│  │    - Queue producer                                                  │ │
│  │    - Healthcheck: /health (every 30s)                               │ │
│  │    - Restart: unless-stopped                                        │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  N8N Workers (3 replicas)                                            │ │
│  │    - Queue consumers                                                 │ │
│  │    - Horizontal scaling                                              │ │
│  │    - Graceful shutdown: 30s timeout                                  │ │
│  │    - Monitoring: queue depth, latency                               │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  Mini App Server (Node.js 18)                                        │ │
│  │    - Express.js + security headers                                   │ │
│  │    - Static file server (HTML/CSS/JS)                                │ │
│  │    - Telegram initData verification                                  │ │
│  │    - Healthcheck: /health                                            │ │
│  │    - Rate limit: 60 req/min per IP                                   │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL Primary                                                  │ │
│  │    - Postgres 15 Alpine                                              │ │
│  │    - Config: postgresql.conf (tuned)                                 │ │
│  │    - Streaming WAL to replicas                                       │ │
│  │    - Backup: daily pg_dump + WAL archiving to Minio                  │ │
│  │    - Healthcheck: pg_isready                                         │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL Replica 1 & 2                                            │ │
│  │    - Hot standby                                                     │ │
│  │    - Read-only queries from N8N                                     │ │
│  │    - Async replication                                               │ │
│  │    - Pool size: 10 connections per replica                           │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  Redis (Bull Queue)                                                  │ │
│  │    - Redis 7 Alpine                                                  │ │
│  │    - Persistence: AOF (appendonly.aof)                               │ │
│  │    - Eviction: noeviction                                            │ │
│  │    - Memory limit: 512mb                                             │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
│               │                                                            │
│  ┌────────────▼──────────────────────────────────────────────────────────┐ │
│  │  Minio S3                                                            │ │
│  │    - MinIO latest                                                    │ │
│  │    - 2 buckets: pics, backups                                        │ │
│  │    - Lifecycle: delete pics >90d, backups >30d                      │ │
│  │    - Encryption at rest                                              │ │
│  └────────────┬──────────────────────────────────────────────────────────┘ │
└───────────────┼───────────────────────────────────────────────────────────┐
                │                                                             │
                ▼                                                             │
┌─────────────────────────────────────────────────────────────────────────────┐
│ External Services                                                           │
│  ├─ Telegram Bot API (webhook + Mini App API)                             │
│  ├─ YooKassa (payments, refunds)                                         │
│  ├─ UptimeRobot (uptime monitoring)                                      │
│  └─ Grafana (metrics, alerts)                                            │
└─────────────────────────────────────────────────────────────────────────────┘