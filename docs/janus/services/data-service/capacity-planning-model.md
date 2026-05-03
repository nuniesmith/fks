# Capacity Planning Model

**Version:** 1.0  
**Last Updated:** Week 9  
**Owner:** SRE Team

---

## Overview

This document provides a data-driven capacity planning model for the Data Service, including growth scenarios, scaling thresholds, and infrastructure requirements.

---

## Current Baseline (Week 8 Production)

### Traffic Metrics

| Metric | Current | Peak | Average |
|--------|---------|------|---------|
| Requests/sec | 10,240 | 15,800 | 8,500 |
| Trades ingested/sec | 10,240 | 15,800 | 8,500 |
| Daily volume | 885M trades | - | 734M trades |
| Monthly volume | 26.6B trades | - | 22B trades |

### Resource Utilization

| Resource | Requested | Used (Avg) | Used (P95) | Utilization |
|----------|-----------|------------|------------|-------------|
| CPU | 12 cores | 6.8 cores | 9.2 cores | 57% avg, 77% p95 |
| Memory | 24 GB | 14.4 GB | 18.8 GB | 60% avg, 78% p95 |
| Network | 10 Gbps | 2.1 Gbps | 4.8 Gbps | 21% avg, 48% p95 |
| Storage (QuestDB) | 8 TB | 1.2 TB | - | 15% |
| Storage (Redis) | 64 GB | 18 GB | 28 GB | 28% avg, 44% p95 |

### Performance Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Availability | 99.9% | 99.982% |
| P50 Latency | <100ms | 52ms |
| P95 Latency | <500ms | 287ms |
| P99 Latency | <1000ms | 507ms |
| Error Rate | <0.1% | 0.019% |
| Data Completeness | >99.5% | 99.83% |

---

## Growth Scenarios

### Scenario 1: 2x Growth (6 months)

**Assumptions:**
- 2x increase in trading volume across all exchanges
- New exchange integrations (2-3 additional)
- Increased symbol coverage (500 → 1000 symbols)

**Requirements:**

| Component | Current | Required | Scaling Factor |
|-----------|---------|----------|----------------|
| Data Service Pods | 3-10 (HPA) | 6-20 | 2x |
| CPU | 12 cores | 20 cores | 1.67x |
| Memory | 24 GB | 40 GB | 1.67x |
| QuestDB Storage | 8 TB | 20 TB | 2.5x |
| Redis Memory | 64 GB | 96 GB | 1.5x |
| Network Bandwidth | 10 Gbps | 20 Gbps | 2x |

**Traffic Projections:**
- Peak: 31,600 req/s
- Average: 17,000 req/s
- Daily volume: 1.77B trades
- Monthly volume: 53.2B trades

**Infrastructure Changes:**
```yaml
# Updated deployment
replicas:
  min: 6
  max: 20
  target_cpu: 70%

resources:
  requests:
    cpu: 2000m
    memory: 4Gi
  limits:
    cpu: 4000m
    memory: 8Gi

# QuestDB
storage: 20Ti
replicas: 3  # Switch to cluster mode

# Redis
node_type: cache.r6g.2xlarge
replicas: 3  # Cluster mode
```

**Cost Impact:**
- Current: $4,072/month
- Projected: $7,200/month (+77%)
- Cost per million trades: $0.14 → $0.13 (efficiency gain)

**Timeline to Implement:** 2-3 weeks  
**Confidence Level:** High (tested up to 2x in load testing)

---

### Scenario 2: 5x Growth (12 months)

**Assumptions:**
- 5x increase in trading volume
- 10+ exchange integrations
- Real-time streaming (addition to batch)
- Enhanced analytics workloads

**Requirements:**

| Component | Current | Required | Scaling Factor |
|-----------|---------|----------|----------------|
| Data Service Pods | 3-10 | 15-50 | 5x |
| CPU | 12 cores | 60 cores | 5x |
| Memory | 24 GB | 120 GB | 5x |
| QuestDB Storage | 8 TB | 60 TB | 7.5x |
| Redis Memory | 64 GB | 256 GB | 4x |
| Network Bandwidth | 10 Gbps | 50 Gbps | 5x |

**Traffic Projections:**
- Peak: 79,000 req/s
- Average: 42,500 req/s
- Daily volume: 4.43B trades
- Monthly volume: 133B trades

**Infrastructure Changes:**
```yaml
# Multi-region deployment required
regions:
  - us-east-1 (primary)
  - eu-west-1 (secondary)
  - ap-southeast-1 (asia)

# Per-region resources
data-service:
  replicas:
    min: 15
    max: 50
  resources:
    requests:
      cpu: 2000m
      memory: 4Gi

# QuestDB - distributed cluster
questdb:
  storage: 60Ti
  replicas: 5
  sharding: enabled
  replication_factor: 2

# Redis - cluster mode
redis:
  node_type: cache.r6g.4xlarge
  replicas: 6
  cluster_mode: enabled
```

**Cost Impact:**
- Projected: $18,500/month (+354%)
- Cost per million trades: $0.14 → $0.12 (economy of scale)

**Timeline to Implement:** 3-6 months  
**Confidence Level:** Medium (requires architectural changes)

---

### Scenario 3: 10x Growth (24 months)

**Assumptions:**
- 10x increase in volume
- Global expansion
- Multiple product lines
- Advanced ML/analytics workloads

**Requirements:**

| Component | Current | Required | Scaling Factor |
|-----------|---------|----------|----------------|
| Data Service Pods | 3-10 | 30-100 | 10x |
| CPU | 12 cores | 150 cores | 12.5x |
| Memory | 24 GB | 300 GB | 12.5x |
| QuestDB Storage | 8 TB | 150 TB | 18.75x |
| Redis Memory | 64 GB | 512 GB | 8x |
| Network Bandwidth | 10 Gbps | 100 Gbps | 10x |

**Traffic Projections:**
- Peak: 158,000 req/s
- Average: 85,000 req/s
- Daily volume: 8.85B trades
- Monthly volume: 266B trades

**Architecture Evolution:**

```yaml
# Multi-region, multi-cluster architecture
regions:
  - us-east-1 (30%)
  - eu-west-1 (30%)
  - ap-southeast-1 (25%)
  - ap-northeast-1 (15%)

# Service mesh for cross-region
service_mesh: istio

# Data tiering
hot_data: 7 days (SSD)
warm_data: 30 days (gp3)
cold_data: 365 days (S3 Glacier)

# Streaming architecture
kafka_clusters: 3
stream_processing: Flink
batch_processing: Spark
```

**Cost Impact:**
- Projected: $42,000/month (+931%)
- Cost per million trades: $0.14 → $0.11 (further optimization)

**Timeline to Implement:** 12-24 months  
**Confidence Level:** Low (requires significant re-architecture)

---

## Scaling Thresholds

### Trigger Points for Scaling

#### Add Capacity When:

1. **CPU Utilization**
   - P95 > 75% for 15 minutes
   - Action: Increase HPA max or add nodes

2. **Memory Utilization**
   - P95 > 80% for 10 minutes
   - Action: Increase pod memory limits

3. **Request Rate**
   - Sustained > 12,000 req/s (80% of current capacity)
   - Action: Scale out data-service pods

4. **Latency Degradation**
   - P95 latency > 400ms for 5 minutes
   - Action: Investigate and scale if resource-constrained

5. **Storage Growth**
   - QuestDB > 70% capacity
   - Action: Expand storage or implement retention

6. **Error Rate**
   - > 0.05% for 10 minutes
   - Action: Investigate before scaling (may not be capacity issue)

#### Scale Down When:

1. **Sustained Low Utilization**
   - CPU < 40% for 1 hour
   - Memory < 50% for 1 hour
   - Action: Reduce min replicas or downsize nodes

2. **Off-Peak Hours** (if applicable)
   - Identify usage patterns
   - Action: Time-based HPA or scheduled scaling

---

## Bottleneck Analysis

### Current Bottlenecks (by load)

| Load Level | Primary Bottleneck | Secondary Bottleneck |
|------------|-------------------|---------------------|
| 1x (current) | None | QuestDB write latency (acceptable) |
| 2x | Network I/O | CPU on data-service |
| 3x | QuestDB ingestion | Redis connection pool |
| 5x+ | Single-region architecture | QuestDB single-node |

### Bottleneck Mitigation

**Network I/O (2x load):**
- Solution: Upgrade to enhanced networking (25 Gbps)
- Cost: +$50/month per node
- Timeline: 1 week

**QuestDB Ingestion (3x load):**
- Solution: QuestDB clustering (3 nodes)
- Cost: +$1,200/month
- Timeline: 2-3 weeks

**Single-Region (5x load):**
- Solution: Multi-region deployment
- Cost: +$8,000/month
- Timeline: 2-3 months

---

## Monitoring & Early Warning

### Leading Indicators

Monitor these metrics as early warnings:

1. **Growth Rate**
   ```promql
   # Week-over-week growth
   (
     rate(data_service_trades_ingested_total[7d]) -
     rate(data_service_trades_ingested_total[7d] offset 7d)
   ) / rate(data_service_trades_ingested_total[7d] offset 7d) * 100
   ```
   Alert: > 20% week-over-week

2. **Peak vs Average Ratio**
   ```promql
   max_over_time(rate(data_service_requests_total[1h])[7d]) /
   avg_over_time(rate(data_service_requests_total[1h])[7d])
   ```
   Alert: Ratio > 2.0 (indicates increasing spikiness)

3. **Resource Headroom**
   ```promql
   # CPU headroom
   100 - (
     avg(rate(container_cpu_usage_seconds_total[5m])) /
     avg(kube_pod_container_resource_limits_cpu_cores) * 100
   )
   ```
   Alert: < 25% headroom

### Capacity Alerts

```yaml
# Prometheus alert rules
- alert: CapacityWarning
  expr: |
    predict_linear(
      data_service_requests_total[7d], 86400 * 30
    ) > 15000
  for: 1h
  annotations:
    summary: "Projected to exceed capacity in 30 days"
    
- alert: StorageCapacityWarning
  expr: |
    (
      questdb_disk_used_bytes /
      questdb_disk_total_bytes
    ) > 0.70
  for: 15m
  annotations:
    summary: "QuestDB storage at 70% capacity"

- alert: HighResourceUtilization
  expr: |
    avg(rate(container_cpu_usage_seconds_total[15m])) /
    avg(kube_pod_container_resource_requests_cpu_cores) > 0.80
  for: 15m
  annotations:
    summary: "CPU utilization consistently high"
```

---

## Capacity Planning Workflow

### Monthly Review Process

**Week 1: Data Collection**
1. Export metrics for previous month
2. Analyze growth trends
3. Review incidents/outages
4. Calculate actual vs projected

**Week 2: Analysis**
1. Update capacity model with actuals
2. Refine growth projections
3. Identify bottlenecks
4. Cost analysis

**Week 3: Planning**
1. Update infrastructure roadmap
2. Budget forecasting
3. Vendor negotiations (if needed)
4. Document recommendations

**Week 4: Implementation**
1. Execute approved changes
2. Update runbooks
3. Team communication
4. Monitor impact

### Quarterly Deep Dive

1. **Architecture Review**
   - Validate scaling strategy
   - Identify technical debt
   - Evaluate new technologies

2. **Cost Optimization**
   - Reserved instance analysis
   - Rightsizing review
   - Storage optimization

3. **Disaster Recovery Testing**
   - Failover testing
   - Backup validation
   - Multi-region readiness

4. **Capacity Modeling**
   - Update growth scenarios
   - Stress testing
   - Bottleneck analysis

---

## Decision Matrix

### When to Scale Vertically vs Horizontally

| Scenario | Vertical (Bigger Nodes) | Horizontal (More Nodes) |
|----------|------------------------|------------------------|
| CPU bottleneck | ❌ Limited benefit | ✅ Preferred |
| Memory bottleneck | ✅ If per-pod memory | ✅ If aggregate |
| Storage bottleneck | ✅ For QuestDB | ❌ Requires clustering |
| Network bottleneck | ✅ Enhanced networking | ✅ Distribute load |
| Cost sensitivity | ❌ More expensive | ✅ More cost-effective |
| High availability | ❌ Single point failure | ✅ Better resilience |

**Recommendation:** Horizontal scaling for data-service, vertical for stateful components (QuestDB, Redis) up to a point, then cluster.

---

## Cost Projection Model

### Formula

```
Monthly Cost = 
  (Compute Cost) +
  (Storage Cost) +
  (Network Cost) +
  (Data Transfer Cost) +
  (Monitoring Cost)

Where:
  Compute = (vCPUs * $0.04/hr * 730) + (Memory GB * $0.005/hr * 730)
  Storage = (GB * $0.10/month for gp3)
  Network = (Load Balancers * $20/month) + (LCU hours * $0.008)
  Data Transfer = (GB egress * $0.09)
  Monitoring = Base $250/month + ($0.30 per million metrics)
```

### Growth vs Cost

| Scenario | Traffic Multiplier | Cost Multiplier | Efficiency |
|----------|-------------------|-----------------|------------|
| Current | 1x | 1x | Baseline |
| 2x Growth | 2x | 1.77x | +13% better |
| 5x Growth | 5x | 4.54x | +10% better |
| 10x Growth | 10x | 10.3x | -3% worse* |

*Note: 10x requires architecture changes; initial efficiency loss recovered through optimization

---

## Contingency Planning

### Emergency Scaling Procedures

**Immediate (< 15 minutes):**
```bash
# Increase HPA max replicas
kubectl patch hpa data-service -n production \
  -p '{"spec":{"maxReplicas":20}}'

# Force scale up
kubectl scale deployment data-service -n production --replicas=15
```

**Short-term (< 1 hour):**
```bash
# Add larger node pool
eksctl create nodegroup \
  --cluster=prod-cluster \
  --name=emergency-large \
  --node-type=c6i.4xlarge \
  --nodes=3 \
  --nodes-min=3 \
  --nodes-max=10
```

**Medium-term (< 24 hours):**
- Increase storage capacity
- Upgrade database instance sizes
- Add cross-region read replicas

### Budget Overrun Response

1. **Minor Overrun (<10%)**
   - Review and optimize
   - No immediate action

2. **Moderate Overrun (10-25%)**
   - Immediate cost analysis
   - Implement quick wins
   - Stakeholder notification

3. **Major Overrun (>25%)**
   - Emergency review
   - Pause non-critical scaling
   - Executive escalation

---

## Appendix: Calculation Examples

### Example 1: Calculating Required Pods

```python
# Given requirements
target_rps = 20000  # 2x current peak
pod_capacity_rps = 2000  # Per pod capacity
safety_margin = 0.25  # 25% headroom

# Calculate
required_pods = (target_rps / pod_capacity_rps) * (1 + safety_margin)
required_pods = (20000 / 2000) * 1.25
required_pods = 12.5 → 13 pods

# HPA configuration
min_replicas = ceil(required_pods * 0.5)  # 7
max_replicas = ceil(required_pods * 1.5)  # 20
```

### Example 2: Storage Growth Projection

```python
# Current state
daily_trades = 885_000_000
bytes_per_trade = 150  # Average
current_storage_gb = 1200

# Calculate daily growth
daily_growth_gb = (daily_trades * bytes_per_trade) / (1024**3)
daily_growth_gb = 123.5 GB/day

# Project future storage (7-day retention)
storage_7d = daily_growth_gb * 7
storage_7d = 865 GB

# With 2x traffic
storage_7d_2x = 865 * 2 = 1730 GB

# Add 30% buffer
required_storage = 1730 * 1.3 = 2249 GB → 2.5 TB
```

### Example 3: Network Bandwidth Calculation

```python
# Assumptions
avg_request_size_kb = 2
avg_response_size_kb = 5
requests_per_sec = 10000

# Calculate
inbound_mbps = (avg_request_size_kb * requests_per_sec * 8) / 1000
inbound_mbps = 160 Mbps

outbound_mbps = (avg_response_size_kb * requests_per_sec * 8) / 1000
outbound_mbps = 400 Mbps

total_mbps = 560 Mbps

# With 3x safety margin
required_bandwidth = 560 * 3 = 1680 Mbps → 2 Gbps
```

---

## Tools & Automation

### Capacity Planning Scripts

Located in: `deployment/production/scripts/`

1. **capacity-analysis.sh**
   - Analyzes current utilization
   - Projects future requirements
   - Generates recommendations

2. **cost-optimization.sh**
   - Cost analysis (covered separately)
   - Rightsizing recommendations

3. **load-simulator.sh**
   - Simulates future load
   - Tests scaling behavior
   - Validates capacity model

### Prometheus Queries

```promql
# Request rate trend (30-day)
predict_linear(
  data_service_requests_total[30d], 86400 * 30
)

# Storage growth rate
deriv(
  questdb_storage_bytes[7d]
) * 86400 * 30

# Cost per million trades
sum(cost_total) / 
(sum(increase(data_service_trades_total[30d])) / 1000000)
```

---

## Summary & Recommendations

### Key Takeaways

1. **Current State:** Well-provisioned with 25-40% headroom
2. **2x Growth:** Achievable with current architecture, 2-3 weeks lead time
3. **5x Growth:** Requires clustering and multi-region, 3-6 months lead time
4. **10x Growth:** Requires re-architecture, 12-24 months lead time

### Immediate Actions

1. ✅ Set up capacity monitoring alerts
2. ✅ Document emergency scaling procedures
3. ✅ Schedule monthly capacity reviews
4. ⏳ Plan for QuestDB clustering (reach 2x load)
5. ⏳ Evaluate multi-region strategy (before 3x load)

### Long-term Strategy

- Maintain 25-30% capacity headroom
- Plan infrastructure changes 3-6 months in advance
- Continuously optimize cost per transaction
- Regular load testing at 2x current peak
- Quarterly architecture reviews

---

**Document Maintenance:**
- Update monthly with actual metrics
- Review scenarios quarterly
- Validate projections against actuals
- Adjust thresholds based on production learnings