#!/bin/bash
set -e

PRIMARY_HOST="postgres-primary"
REPLICA_NAME=$(hostname)

# Ждём primary
until pg_isready -h $PRIMARY_HOST; do
  echo "Waiting for primary..."
  sleep 2
done

# Создаём standby.signal
touch $PGDATA/standby.signal

# Recovery config
cat > $PGDATA/postgresql-auto.conf <<EOF
primary_conninfo = 'host=$PRIMARY_HOST port=5432 user=replicator password=${DB_REPLICA_PASSWORD} application_name=$REPLICA_NAME'
recovery_target_timeline = 'latest'
standby_mode = 'on'
EOF

# Запускаем
exec postgres -c config_file=/etc/postgresql/postgresql.conf