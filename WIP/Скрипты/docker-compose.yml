version: "3.9"

services:
  # ========================================
  # PostgreSQL Primary (Master)
  # ========================================
  postgres-primary:
    image: postgres:15-alpine
    container_name: n8n_db_primary
    restart: unless-stopped
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256"
      POSTGRES_HOST_AUTH_METHOD: trust
      DB_REPLICA_PASSWORD: ${DB_REPLICA_PASSWORD}
    volumes:
      - pg_primary_data:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d
      - ./scripts/postgresql.conf:/etc/postgresql/postgresql.conf
    ports:
      - "5432:5432"
    networks:
      - n8n-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U n8n -d n8n"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  # ========================================
  # PostgreSQL Replica 1
  # ========================================
  postgres-replica1:
    image: postgres:15-alpine
    container_name: n8n_db_replica1
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
      POSTGRES_HOST_AUTH_METHOD: trust
    volumes:
      - pg_replica1_data:/var/lib/postgresql/data
      - ./scripts/postgresql.conf:/etc/postgresql/postgresql.conf
      - ./scripts/replica-setup.sh:/usr/local/bin/replica-setup.sh
    networks:
      - n8n-net
    depends_on:
      postgres-primary:
        condition: service_healthy
    command: sh -c "sleep 10 && /usr/local/bin/replica-setup.sh"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U n8n"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  # ========================================
  # PostgreSQL Replica 2
  # ========================================
  postgres-replica2:
    image: postgres:15-alpine
    container_name: n8n_db_replica2
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
      POSTGRES_HOST_AUTH_METHOD: trust
    volumes:
      - pg_replica2_data:/var/lib/postgresql/data
      - ./scripts/postgresql.conf:/etc/postgresql/postgresql.conf
      - ./scripts/replica-setup.sh:/usr/local/bin/replica-setup.sh
    networks:
      - n8n-net
    depends_on:
      postgres-primary:
        condition: service_healthy
    command: sh -c "sleep 15 && /usr/local/bin/replica-setup.sh"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U n8n"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  # ========================================
  # Redis (Bull Queue)
  # ========================================
  redis:
    image: redis:7-alpine
    container_name: n8n_redis
    restart: unless-stopped
    command: redis-server --appendonly yes --save 60 1 --maxmemory 512mb --maxmemory-policy noeviction
    volumes:
      - redis_data:/data
    networks:
      - n8n-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  # ========================================
  # Minio S3
  # ========================================
  minio:
    image: minio/minio:latest
    container_name: n8n_s3
    restart: unless-stopped
    command: server /data --console-address ":9001" --address ":9000"
    environment:
      MINIO_ROOT_USER: ${MINIO_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET}
    volumes:
      - minio_data:/data
      - ./scripts/minio-policy.json:/etc/minio/policy.json
    ports:
      - "9001:9001"  # Console
      - "9000:9000"  # API
    networks:
      - n8n-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  # ========================================
  # N8N Main (Primary Instance)
  # ========================================
  n8n:
    image: n8n-custom:latest
    container_name: n8n_main
    restart: unless-stopped
    environment:
      # Database
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres-primary
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: n8n
      DB_POSTGRESDB_USER: n8n
      DB_POSTGRESDB_PASSWORD: ${DB_PASSWORD}
      DB_POSTGRESDB_READ_REPLICA_HOSTS: postgres-replica1,postgres-replica2
      DB_POSTGRESDB_POOL_SIZE: 20
      DB_POSTGRESDB_CONNECTION_TIMEOUT: 10000
      
      # N8N Core
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: ${ADMIN_USER}
      N8N_BASIC_AUTH_PASSWORD: ${ADMIN_PASS}
      WEBHOOK_URL: https://${DOMAIN}/
      N8N_LOG_LEVEL: info
      N8N_LOG_OUTPUT: console,file
      N8N_LOG_FILE_LOCATION: /home/node/.n8n/logs/n8n.log
      
      # Queue
      N8N_QUEUE_BULL_REDIS_HOST: redis
      N8N_QUEUE_BULL_REDIS_PORT: 6379
      N8N_QUEUE_BULL_REDIS_DB: 0
      
      # Graceful shutdown
      N8N_GRACEFUL_SHUTDOWN_TIMEOUT: 30
      
      # Retry logic
      N8N_DEFAULT_RETRY_ATTEMPTS: 3
      N8N_DEFAULT_RETRY_WAIT: 1000
      N8N_DEFAULT_TIMEOUT: 30000
      
      # Performance
      N8N_CONCURRENCY_LIMIT: 30
      N8N_NODES_INCLUDE: "n8n-nodes-base.start,n8n-nodes-base.telegram,n8n-nodes-base.postgres,n8n-nodes-base.cron"
      
      # Mini App integration
      MINI_APP_URL: https://${DOMAIN}/mini-app
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
      - ./workflows:/workflows
      - ./logs:/home/node/.n8n/logs
    networks:
      - n8n-net
    depends_on:
      postgres-primary:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  # ========================================
  # Mini App Server
  # ========================================
  mini-app:
    image: node:18-alpine
    container_name: n8n_mini_app
    restart: unless-stopped
    working_dir: /app
    command: sh -c "npm install --production && node server.js"
    environment:
      NODE_ENV: ${NODE_ENV:-production}
      TG_BOT_TOKEN: ${TG_BOT_TOKEN}
      MINI_APP_PORT: 3000
      RATE_LIMIT_WINDOW_MS: 60000
      RATE_LIMIT_MAX_REQUESTS: 60
    volumes:
      - ./mini-app:/app
      - /app/node_modules  # Volume for node_modules
    ports:
      - "127.0.0.1:3000:3000"
    networks:
      - n8n-net
    depends_on:
      n8n:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M

networks:
  n8n-net:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.20.0.0/16

volumes:
  pg_primary_data:
    driver: local
  pg_replica1_data:
    driver: local
  pg_replica2_data:
    driver: local
  n8n_data:
    driver: local
  redis_data:
    driver: local
  minio_data:
    driver: local