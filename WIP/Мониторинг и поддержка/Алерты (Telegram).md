| Условие                  | Действие               |
| ------------------------ | ---------------------- |
| Queue depth > 1000       | Добавить workers       |
| p99 latency > 2s         | Оптимизировать запросы |
| PG replication lag > 30s | Проверить replica      |
| Circuit breaker open     | Ручное вмешательство   |
| Refund > 5 в день        | Проверить stability    |
