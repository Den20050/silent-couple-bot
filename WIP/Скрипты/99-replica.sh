#!/bin/bash
set -e

# Создаём пользователя для репликации
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${DB_REPLICA_PASSWORD}';
    SELECT * FROM pg_create_physical_replication_slot('replica1');
    SELECT * FROM pg_create_physical_replication_slot('replica2');
EOSQL