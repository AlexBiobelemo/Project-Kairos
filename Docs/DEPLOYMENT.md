# Deployment Guide

This guide provides comprehensive instructions for deploying Project Kairos in production environments, from simple single-server deployments to enterprise-grade high-availability configurations.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Setup](#environment-setup)
3. [Deployment Methods](#deployment-methods)
4. [Configuration Management](#configuration-management)
5. [Security Hardening](#security-hardening)
6. [Monitoring Setup](#monitoring-setup)
7. [Backup & Recovery](#backup--recovery)
8. [Scaling & Performance](#scaling--performance)
9. [Maintenance & Updates](#maintenance--updates)
10. [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- Network: Stable internet connection
- OS: Linux (Ubuntu 20.04+ recommended), Windows Server 2019+, macOS 10.15+

**Recommended Requirements:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD with backup storage
- Network: High-speed connection with redundancy
- OS: Ubuntu 22.04 LTS or similar enterprise Linux

### Software Prerequisites

```bash
# Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Git (if not installed)
sudo apt-get update && sudo apt-get install -y git

# Optional: Python 3.11+ for local development
sudo apt-get install -y python3.11 python3.11-venv python3-pip
```

## Environment Setup

### 1. Clone and Prepare

```bash
# Clone repository
git clone https://github.com/AlexBiobelemo/Project-Kairos/
cd Project-Kairos

# Create required directories
mkdir -p data logs backups monitoring/grafana monitoring/prometheus

# Set proper permissions
sudo chown -R $USER:$USER data logs backups
chmod 755 data logs backups
```

### 2. Environment Configuration

Create production environment file:

```bash
# Create .env file
cat > .env << EOF
# Production Environment Configuration
KAIROS_ENV=production
KAIROS_DB_PATH=/app/data/kairos_production.db
KAIROS_LOG_LEVEL=INFO
KAIROS_LOG_FILE=/app/logs/kairos_production.log

# API Configuration
KAIROS_API_TIMEOUT=15
KAIROS_API_MAX_RETRIES=3
KAIROS_API_RATE_LIMIT=100

# Cache Settings
KAIROS_CACHE_WEATHER_TTL=300
KAIROS_CACHE_ALERTS_TTL=600
KAIROS_CACHE_DISASTERS_TTL=1800

# Security Settings
KAIROS_ENABLE_AUTH=false
KAIROS_ALLOWED_ORIGINS=*
KAIROS_SESSION_TIMEOUT=3600

# Monitoring
KAIROS_ALERT_WEBHOOK=https://hooks.slack.com/your-webhook-url

# Streamlit Configuration
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLE_CORS=false
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
EOF
```

## Deployment Methods

### Method 1: Basic Docker Deployment

For simple, single-server deployments:

```bash
# Build and deploy
docker-compose up -d kairos-app

# Verify deployment
docker-compose ps
docker-compose logs -f kairos-app

# Access application
curl http://localhost:8501/_stcore/health
```

### Method 2: Production with Monitoring

For production environments with full monitoring:

```bash
# Deploy with monitoring stack
docker-compose --profile monitoring up -d

# Verify all services
docker-compose --profile monitoring ps

# Access monitoring dashboards
# Grafana: http://localhost:3000 (admin/admin123)
# Prometheus: http://localhost:9090
```

### Method 3: High Availability with Proxy

For enterprise deployments with SSL and load balancing:

```bash
# Update domain in docker-compose.yml
sed -i 's/kairos.yourdomain.com/your-actual-domain.com/g' docker-compose.yml
sed -i 's/admin@yourdomain.com/your-email@domain.com/g' docker-compose.yml

# Deploy full stack
docker-compose --profile proxy --profile monitoring up -d

# Verify proxy is working
curl -I http://your-domain.com
```

### Method 4: Kubernetes Deployment

For container orchestration platforms:

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kairos-app
  labels:
    app: kairos
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kairos
  template:
    metadata:
      labels:
        app: kairos
    spec:
      containers:
      - name: kairos
        image: project-kairos:latest
        ports:
        - containerPort: 8501
        env:
        - name: KAIROS_ENV
          value: "production"
        volumeMounts:
        - name: kairos-data
          mountPath: /app/data
        - name: kairos-logs  
          mountPath: /app/logs
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 60
          periodSeconds: 30
      volumes:
      - name: kairos-data
        persistentVolumeClaim:
          claimName: kairos-data-pvc
      - name: kairos-logs
        persistentVolumeClaim:
          claimName: kairos-logs-pvc
```

## Configuration Management

### Production Configuration Template

```bash
# Create production config template
cat > kairos_config.json << EOF
{
  "database": {
    "path": "/app/data/kairos_production.db",
    "connection_timeout": 30,
    "max_connections": 20,
    "backup_interval_hours": 6,
    "enable_wal_mode": true
  },
  "cache": {
    "weather_ttl": 300,
    "alerts_ttl": 600,
    "disasters_ttl": 1800,
    "max_size_weather": 1000,
    "max_size_alerts": 200,
    "max_size_disasters": 400
  },
  "api": {
    "timeout_seconds": 15,
    "max_retries": 3,
    "retry_delay": 2,
    "rate_limit_calls": 100,
    "rate_limit_period": 3600
  },
  "security": {
    "enable_auth": false,
    "session_timeout": 3600,
    "max_login_attempts": 5,
    "enable_rate_limiting": true,
    "allowed_origins": ["*"]
  },
  "monitoring": {
    "log_level": "INFO",
    "log_file": "/app/logs/kairos_production.log",
    "max_log_size_mb": 100,
    "backup_count": 5,
    "enable_metrics": true,
    "health_check_interval": 60,
    "alert_webhook_url": "https://hooks.slack.com/your-webhook"
  }
}
EOF
```

### Environment-Specific Configurations

**Development:**
```bash
KAIROS_ENV=development
KAIROS_LOG_LEVEL=DEBUG
KAIROS_CACHE_WEATHER_TTL=60
```

**Staging:**
```bash
KAIROS_ENV=staging
KAIROS_LOG_LEVEL=INFO
KAIROS_ENABLE_AUTH=true
```

**Production:**
```bash
KAIROS_ENV=production
KAIROS_LOG_LEVEL=WARNING
KAIROS_ENABLE_AUTH=true
KAIROS_ALERT_WEBHOOK=<your-production-webhook>
```

## Security Hardening

### Container Security

```bash
# Run security scan
docker scan project-kairos:latest

# Check container for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    aquasec/trivy image project-kairos:latest
```

### Network Security

```bash
# Configure firewall (Ubuntu/Debian)
sudo ufw enable
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw allow 8501  # Kairos (if direct access needed)

# Deny all other incoming connections
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

### SSL/TLS Configuration

```yaml
# docker-compose.yml - Traefik with SSL
traefik:
  command:
    - --certificatesresolvers.letsencrypt.acme.email=your-email@domain.com
    - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
    - --certificatesresolvers.letsencrypt.acme.httpchallenge=true
    - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
```

### Authentication Setup (Optional)

For environments requiring authentication:

```python
# Add to environment variables
KAIROS_ENABLE_AUTH=true
KAIROS_AUTH_SECRET_KEY=<generate-strong-secret-key>
KAIROS_ALLOWED_USERS=admin,operator,viewer
```

## Monitoring Setup

### Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'kairos-app'
    static_configs:
      - targets: ['kairos-app:8501']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "alert_rules.yml"
```

### Grafana Dashboard

```json
# monitoring/grafana/dashboards/kairos.json
{
  "dashboard": {
    "title": "Project Kairos Dashboard",
    "panels": [
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"kairos-app\"}",
            "legendFormat": "Application Status"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "kairos_cache_hit_rate",
            "legendFormat": "Hit Rate"
          }
        ]
      }
    ]
  }
}
```

### Alert Rules

```yaml
# monitoring/alert_rules.yml
groups:
  - name: kairos_alerts
    rules:
      - alert: KairosDown
        expr: up{job="kairos-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Kairos application is down"

      - alert: HighMemoryUsage
        expr: (kairos_memory_usage / kairos_memory_total) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"

      - alert: LowCacheHitRate
        expr: kairos_cache_hit_rate < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate is below 50%"
```

## Backup & Recovery

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh - Automated backup script

set -e

BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_PATH="/app/data/kairos_production.db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo "Creating database backup..."
sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/kairos_db_$TIMESTAMP.db"
gzip "$BACKUP_DIR/kairos_db_$TIMESTAMP.db"

# Backup logs
echo "Backing up logs..."
tar -czf "$BACKUP_DIR/kairos_logs_$TIMESTAMP.tar.gz" /app/logs/

# Backup configuration
echo "Backing up configuration..."
cp /app/kairos_config.json "$BACKUP_DIR/kairos_config_$TIMESTAMP.json"

# Clean old backups (keep last 30 days)
find "$BACKUP_DIR" -name "kairos_*" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR"
```

### Cron Job for Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /app/backup.sh >> /app/logs/backup.log 2>&1

# Weekly full system backup
0 1 * * 0 /app/full_backup.sh >> /app/logs/backup.log 2>&1
```

### Recovery Procedures

```bash
# Database recovery
gunzip /app/backups/kairos_db_20231201_020000.db.gz
mv /app/data/kairos_production.db /app/data/kairos_production.db.backup
cp /app/backups/kairos_db_20231201_020000.db /app/data/kairos_production.db

# Restart application
docker-compose restart kairos-app
```

## Scaling & Performance

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'
services:
  kairos-app:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
```

### Load Balancer Configuration

```nginx
# nginx.conf - Load balancer example
upstream kairos_backend {
    server kairos-app-1:8501;
    server kairos-app-2:8501;
    server kairos-app-3:8501;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://kairos_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Performance Tuning

```bash
# System-level optimizations
echo 'vm.swappiness=10' >> /etc/sysctl.conf
echo 'net.core.somaxconn=65535' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog=65535' >> /etc/sysctl.conf
sysctl -p

# Docker optimizations
echo '{"storage-driver": "overlay2", "log-opts": {"max-size": "10m", "max-file": "3"}}' > /etc/docker/daemon.json
systemctl restart docker
```

## Maintenance & Updates

### Update Procedure

```bash
# 1. Backup current state
./backup.sh

# 2. Pull latest changes
git pull origin main

# 3. Build new image
docker-compose build kairos-app

# 4. Rolling update (zero downtime)
docker-compose up -d --no-deps kairos-app

# 5. Verify deployment
docker-compose logs -f kairos-app
curl http://localhost:8501/_stcore/health
```

### Health Monitoring

```bash
#!/bin/bash
# health_check.sh - Health monitoring script

HEALTH_URL="http://localhost:8501/_stcore/health"
LOG_FILE="/app/logs/health_check.log"

check_health() {
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [ "$status_code" -eq 200 ]; then
        echo "$timestamp - Health check passed" >> "$LOG_FILE"
        return 0
    else
        echo "$timestamp - Health check failed (HTTP $status_code)" >> "$LOG_FILE"
        # Send alert
        curl -X POST "$KAIROS_ALERT_WEBHOOK" \
             -H 'Content-type: application/json' \
             --data '{"text":"Kairos health check failed!"}'
        return 1
    fi
}

# Run health check
check_health
```

### Maintenance Mode

```bash
# Enable maintenance mode
docker-compose -f docker-compose.yml -f docker-compose.maintenance.yml up -d

# Perform maintenance tasks
./maintenance_tasks.sh

# Disable maintenance mode
docker-compose up -d kairos-app
```

## Troubleshooting

### Common Issues and Solutions

**1. Application Won't Start**
```bash
# Check logs
docker-compose logs kairos-app

# Check disk space
df -h

# Check permissions
ls -la data/ logs/

# Restart with clean state
docker-compose down
docker-compose up -d
```

**2. Database Connection Errors**
```bash
# Check database file
ls -la data/kairos_production.db

# Test database integrity
sqlite3 data/kairos_production.db "PRAGMA integrity_check;"

# Reset database if corrupted
mv data/kairos_production.db data/kairos_production.db.backup
docker-compose restart kairos-app
```

**3. High Memory Usage**
```bash
# Monitor memory usage
docker stats kairos-production

# Check cache sizes
docker-compose exec kairos-app python -c "
from cache import cache_manager
print(cache_manager.get_all_stats())
"

# Clear caches
docker-compose exec kairos-app python -c "
from cache import cache_manager
cache_manager.clear_all()
"
```

**4. API Timeouts**
```bash
# Check network connectivity
docker-compose exec kairos-app ping -c 3 api.open-meteo.com

# Check circuit breaker status
docker-compose exec kairos-app python -c "
from resilience import resilience_manager
print(resilience_manager.get_system_health())
"
```

### Performance Debugging

```bash
# CPU and memory profiling
docker stats --no-stream kairos-production

# Application profiling
docker-compose exec kairos-app python -m cProfile -o profile.out app_production.py

# Database query analysis
sqlite3 data/kairos_production.db "EXPLAIN QUERY PLAN SELECT * FROM weather ORDER BY timestamp DESC LIMIT 100;"
```

### Log Analysis

```bash
# View recent errors
docker-compose logs --tail=100 kairos-app | grep ERROR

# Monitor real-time logs
docker-compose logs -f kairos-app

# Extract performance metrics
grep "response_time" logs/kairos_production.log | tail -20
```

## Support Contacts

- **Emergency Issues**: Check GitHub Issues
- **Documentation**: README.md and inline code comments
- **Community**: GitHub Discussions
- **Security Issues**: Report privately via repository security tab

---

This deployment guide ensures your Project Kairos installation is production-ready, secure, monitored, and maintainable. Follow the appropriate section based on your deployment requirements and infrastructure constraints.
