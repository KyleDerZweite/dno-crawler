# Observability Stack Setup

Last Updated: 2026-01-17

This file is designed to be copied to your infrastructure repository.

Complete setup guide for a self hosted observability stack using OpenTelemetry Collector, Loki, Prometheus, and Grafana.

## Architecture Overview

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Application 1 │  │   Application 2 │  │   Application N │
│   (OTLP/HTTP)   │  │   (OTLP/HTTP)   │  │  (Docker logs)  │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │  OpenTelemetry Collector │
                 │  Port 4317 (gRPC)       │
                 │  Port 4318 (HTTP)       │
                 └────────────┬─────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌─────────┐    ┌──────────┐    ┌─────────┐
         │  Loki   │    │Prometheus│    │ (Tempo) │
         │  :3100  │    │  :9090   │    │ (later) │
         └────┬────┘    └────┬─────┘    └─────────┘
              │              │
              └──────┬───────┘
                     ▼
              ┌───────────┐
              │  Grafana  │
              │   :3000   │
              └───────────┘
```

## Quick Start

```bash
# Clone or copy these files to your infra repo
mkdir -p observability
cd observability

# Create configs (see below)
# Then start the stack
docker compose up -d
```

## Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # OpenTelemetry Collector
  # Receives logs and metrics from all applications
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: otel-collector
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./config/otel-collector.yaml:/etc/otelcol/config.yaml:ro
      - /var/lib/docker/containers:/var/log/containers:ro
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8889:8889"   # Prometheus metrics endpoint
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-production}
    restart: unless-stopped
    networks:
      - observability

  # Loki for Log aggregation
  loki:
    image: grafana/loki:latest
    container_name: loki
    command: -config.file=/etc/loki/config.yaml
    volumes:
      - ./config/loki.yaml:/etc/loki/config.yaml:ro
      - loki_data:/loki
    ports:
      - "3100:3100"
    restart: unless-stopped
    networks:
      - observability

  # Prometheus for Metrics aggregation
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped
    networks:
      - observability

  # Grafana for Dashboards and Visualization
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-changeme}
      - GF_USERS_DEFAULT_THEME=dark
      - GF_AUTH_ANONYMOUS_ENABLED=false
      - GF_SERVER_ROOT_URL=${GRAFANA_ROOT_URL:-http://localhost:3000}
    restart: unless-stopped
    networks:
      - observability
    depends_on:
      - loki
      - prometheus

networks:
  observability:
    driver: bridge

volumes:
  loki_data:
  prometheus_data:
  grafana_data:
```

## Configuration Files

### Directory Structure

```
observability/
├── docker-compose.yml
├── .env
└── config/
    ├── otel-collector.yaml
    ├── loki.yaml
    ├── prometheus.yml
    └── grafana/
        └── provisioning/
            └── datasources/
                └── datasources.yml
```

### OpenTelemetry Collector

```yaml
# config/otel-collector.yaml
receivers:
  # Receive OTLP from applications
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  
  # Collect Docker container logs (optional)
  filelog:
    include:
      - /var/log/containers/*.log
    include_file_path: true
    operators:
      # Parse Docker JSON log format
      - type: json_parser
        timestamp:
          parse_from: attributes.time
          layout: '%Y-%m-%dT%H:%M:%S.%LZ'
      # Extract container name
      - type: regex_parser
        regex: '/var/log/containers/(?P<container_name>[^_]+)_.*\.log'
        parse_from: attributes["log.file.path"]
      - type: move
        from: attributes.container_name
        to: resource["service.name"]

processors:
  # Batch for efficiency
  batch:
    timeout: 1s
    send_batch_size: 1024
  
  # Add environment label
  resource:
    attributes:
      - key: deployment.environment
        value: ${ENVIRONMENT}
        action: insert
  
  # Memory limiter (prevent OOM)
  memory_limiter:
    check_interval: 1s
    limit_mib: 400
    spike_limit_mib: 100

exporters:
  # Export logs to Loki
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
    labels:
      attributes:
        service.name: "service"
        level: "level"
      resource:
        deployment.environment: "environment"
  
  # Export metrics for Prometheus scraping
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: otel

service:
  pipelines:
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, batch, resource]
      exporters: [loki]
    
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

### Loki

```yaml
# config/loki.yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: warn

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 30d
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  max_streams_per_user: 10000
  max_global_streams_per_user: 10000

# Compactor for retention enforcement
compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem
```

### Prometheus

```yaml
# config/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Scrape OTel Collector metrics
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
  
  # Scrape Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  # Scrape Loki metrics
  - job_name: 'loki'
    static_configs:
      - targets: ['loki:3100']
  
  # Add your application metrics endpoints here
  # - job_name: 'dno-crawler'
  #   static_configs:
  #     - targets: ['dno-crawler-backend:8000']
  #   metrics_path: /metrics
```

### Grafana Data Sources

```yaml
# config/grafana/provisioning/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    jsonData:
      maxLines: 1000
    
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    jsonData:
      timeInterval: "15s"
```

## Environment Variables

```bash
# .env
ENVIRONMENT=production
GRAFANA_USER=admin
GRAFANA_PASSWORD=your-secure-password
GRAFANA_ROOT_URL=https://grafana.yourdomain.com
```

## Sending Logs from Applications

### Python (structlog + OTLP)

```python
# Option 1 stdout JSON (recommended as collector reads Docker logs)
import json
import sys

def emit_event(event: dict):
    print(json.dumps(event), file=sys.stdout, flush=True)

# Option 2 Direct OTLP HTTP
import httpx

async def send_to_otel(event: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://otel-collector:4318/v1/logs",
            json={
                "resourceLogs": [{
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "my-app"}}
                        ]
                    },
                    "scopeLogs": [{
                        "logRecords": [{
                            "timeUnixNano": str(int(time.time() * 1e9)),
                            "body": {"stringValue": json.dumps(event)},
                            "attributes": [
                                {"key": "level", "value": {"stringValue": event.get("level", "info")}}
                            ]
                        }]
                    }]
                }]
            },
            headers={"Content-Type": "application/json"}
        )
```

### Docker Logging Driver

Configure containers to send logs directly.

```yaml
# In your application docker-compose.yml
services:
  my-app:
    image: my-app:latest
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # OTel collector reads from /var/lib/docker/containers
```

## Useful Loki Queries (LogQL)

```logql
# All logs from a service
{service="dno-crawler"}

# Errors only
{service="dno-crawler"} |= "error" | json | level = "error"

# Slow requests (greater than 2 seconds)
{service="dno-crawler"} | json | duration_ms > 2000

# Specific user requests
{service="dno-crawler"} | json | user_id = "user_456"

# Error rate (last 5 minutes)
sum(rate({level="error"}[5m])) by (service)

# Top 10 slowest endpoints
topk(10, avg by (http_path) (
  {service="dno-crawler"} | json | unwrap duration_ms
))
```

## Grafana Dashboard Ideas

### Request Overview Panel

| Metric | Description |
|--------|-------------|
| Request rate by status code | Track 2xx, 4xx, 5xx distributions |
| P50/P95/P99 latency histogram | Latency percentiles over time |
| Error rate trend | Error percentage trend line |

### Service Health Panel

| Metric | Description |
|--------|-------------|
| Active services | Currently reporting services |
| Log ingestion rate | Logs per second |
| Error count by service | Error distribution across services |

### User Activity Panel

| Metric | Description |
|--------|-------------|
| Requests by user tier | Distribution across subscription tiers |
| Top users by request count | Most active users |
| User error rate | Errors per user |

## Resource Requirements

| Component | Min RAM | Recommended | Storage |
|-----------|---------|-------------|---------|
| OTel Collector | 128MB | 256MB | minimal |
| Loki | 512MB | 1GB | 50GB+ |
| Prometheus | 256MB | 512MB | 20GB |
| Grafana | 256MB | 512MB | 1GB |
| **Total** | **~1.2GB** | **~2.5GB** | **~70GB** |

Suitable for VPS with 4GB RAM and 100GB+ storage.

## Maintenance

### Backup Grafana

```bash
# Export dashboards
docker exec grafana grafana-cli admin export-dashboards /tmp/dashboards
docker cp grafana:/tmp/dashboards ./backups/

# Or backup the volume
docker run --rm -v grafana_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/grafana-backup.tar.gz /data
```

### Check Loki Retention

```bash
# View Loki storage usage
docker exec loki du -sh /loki/chunks

# Force compaction (if needed)
curl -X POST http://localhost:3100/compactor/ring/forget
```

### Update Stack

```bash
docker compose pull
docker compose up -d
```

## Troubleshooting

### Logs not appearing in Loki

1. Check OTel Collector logs with `docker logs otel-collector`
2. Verify Loki is healthy with `curl http://localhost:3100/ready`
3. Check labels are being set correctly

### High memory usage

1. Reduce Loki `max_streams_per_user` setting
2. Lower OTel Collector batch size
3. Increase sampling rate (drop more logs)

### Grafana cannot connect to data sources

1. Verify network connectivity with `docker exec grafana ping loki`
2. Check data source URLs use container names, not localhost
