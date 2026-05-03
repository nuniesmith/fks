# gRPC + NCCL Quick Reference

## Table of Contents
- [Quick Start](#quick-start)
- [gRPC Server](#grpc-server)
- [gRPC Client](#grpc-client)
- [NCCL Backend](#nccl-backend)
- [Environment Variables](#environment-variables)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Build with Features

```bash
# CPU-only (gRPC only)
cargo build --release

# With CUDA and NCCL
cargo build --release --features cuda,nccl

# All features
cargo build --release --all-features
```

### Run Parameter Server

```bash
cargo run --example grpc_nccl_training -- --mode server
```

### Run Worker

```bash
cargo run --release --features nccl \
    --example grpc_nccl_training -- \
    --mode worker \
    --rank 0 \
    --world-size 2 \
    --local-gpus 4 \
    --master-addr localhost:50051
```

---

## gRPC Server

### Basic Server

```rust
use janus_neuromorphic::distributed::DistributedTrainingServer;

#[tokio::main]
async fn main() -> Result<()> {
    let server = DistributedTrainingServer::new("0.0.0.0:50051");
    server.serve().await?;
    Ok(())
}
```

### Server Methods

| Method | Description |
|--------|-------------|
| `new(addr)` | Create server at address |
| `serve()` | Start serving requests |
| `num_nodes()` | Get number of registered nodes |
| `get_world_size()` | Get cluster world size |

---

## gRPC Client

### Connect

```rust
use janus_neuromorphic::distributed::DistributedTrainingClient;

let mut client = DistributedTrainingClient::connect(
    "http://localhost:50051"
).await?;
```

### Custom Configuration

```rust
use janus_neuromorphic::distributed::GrpcClientConfig;
use std::time::Duration;

let config = GrpcClientConfig {
    server_addr: "http://master:50051".to_string(),
    connect_timeout: Duration::from_secs(30),
    request_timeout: Duration::from_secs(60),
    max_retries: 5,
    retry_delay: Duration::from_millis(100),
    ..Default::default()
};

let mut client = DistributedTrainingClient::with_config(config).await?;
```

### Push Gradients

```rust
let response = client.push_gradients(
    "layer1.weight",      // key
    gradients,            // Vec<f32>
    0,                    // version
    0,                    // rank
).await?;

println!("New version: {}", response.version);
```

### Pull Parameters

```rust
let response = client.pull_parameters("layer1.weight", rank).await?;
let params = response.data;  // Vec<f32>
```

### Barrier Synchronization

```rust
// Wait for all nodes
client.barrier(barrier_id, rank).await?;
```

### Heartbeat

```rust
let resources = create_resource_usage();
client.heartbeat(rank, status, Some(resources)).await?;
```

### Register Node

```rust
let caps = create_node_capabilities(
    true,                      // has_cuda
    true,                      // has_nccl
    4,                         // num_gpus
    "NVIDIA A100".to_string(), // gpu_type
);

let response = client.register_node(
    rank,
    hostname,
    ip_address,
    vec![0, 1, 2, 3],  // gpu_ids
    caps,
).await?;
```

### All-Reduce (via gRPC)

```rust
let response = client.all_reduce(
    "gradients",
    data,
    0,  // ReduceOp::SUM
    rank,
).await?;
```

### Client Methods Summary

| Method | Purpose |
|--------|---------|
| `connect(addr)` | Connect to server |
| `push_gradients(key, data, ver, rank)` | Push gradients |
| `pull_parameters(key, rank)` | Pull parameters |
| `barrier(id, rank)` | Synchronization barrier |
| `heartbeat(rank, status, res)` | Send heartbeat |
| `all_reduce(key, data, op, rank)` | All-reduce operation |
| `broadcast(key, data, root, rank)` | Broadcast from root |
| `gather(key, data, root, rank)` | Gather to root |
| `register_node(...)` | Register with cluster |
| `get_cluster_status(rank)` | Get cluster info |

---

## NCCL Backend

### Initialize

```rust
use janus_neuromorphic::distributed::{
    NcclBackend, NcclConfig, NcclReduceOp,
};

let config = NcclConfig {
    rank: 0,
    world_size: 4,
    device_id: 0,
    nccl_id: None,
    enable_profiling: false,
    network_interface: Some("eth0".to_string()),
    use_rdma: false,
};

let backend = NcclBackend::new(config).await?;
```

### All-Reduce

```rust
// Sum gradients
let result = backend.all_reduce(data, NcclReduceOp::Sum).await?;

// Average gradients
let result = backend.all_reduce(data, NcclReduceOp::Avg).await?;
```

### Broadcast

```rust
// Broadcast from rank 0
let result = backend.broadcast(data, 0).await?;
```

### Reduce

```rust
// Reduce to rank 0
let result = backend.reduce(data, 0, NcclReduceOp::Sum).await?;
```

### All-Gather

```rust
let gathered = backend.all_gather(local_data).await?;
// Returns Vec<Vec<f32>>, one per rank
```

### Reduce-Scatter

```rust
// Data size must be divisible by world_size
let result = backend.reduce_scatter(data, NcclReduceOp::Sum).await?;
```

### Device Sync

```rust
backend.synchronize().await?;
```

### Reduce Operations

| Operation | Description |
|-----------|-------------|
| `NcclReduceOp::Sum` | Sum all values |
| `NcclReduceOp::Prod` | Product of all values |
| `NcclReduceOp::Max` | Maximum value |
| `NcclReduceOp::Min` | Minimum value |
| `NcclReduceOp::Avg` | Average (sum/world_size) |

### Multi-GPU Setup

```rust
use janus_neuromorphic::distributed::NcclCommGroup;

let mut configs = Vec::new();
for i in 0..4 {
    configs.push(NcclConfig {
        rank: i,
        world_size: 4,
        device_id: i,
        ..Default::default()
    });
}

let comm_group = NcclCommGroup::new(configs).await?;

// Use specific GPU
if let Some(backend) = comm_group.get(0) {
    let result = backend.all_reduce(data, NcclReduceOp::Sum).await?;
}
```

---

## Environment Variables

### NCCL Network

```bash
# Ethernet
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1

# InfiniBand
export NCCL_SOCKET_IFNAME=ib0
export NCCL_IB_DISABLE=0
export NCCL_NET_GDR_LEVEL=5

# RoCE
export NCCL_IB_GID_INDEX=3
export NCCL_IB_TC=106
```

### NCCL Debugging

```bash
export NCCL_DEBUG=INFO
export NCCL_DEBUG_SUBSYS=ALL
export NCCL_DEBUG_FILE=/tmp/nccl_debug.log
```

### NCCL Performance

```bash
export NCCL_BUFFSIZE=16777216     # 16MB buffer
export NCCL_NTHREADS=512           # Thread count
export NCCL_P2P_LEVEL=5            # Enable P2P
export NCCL_P2P_DISABLE=0          # Don't disable P2P
```

### NCCL Topology

```bash
export NCCL_TOPO_FILE=/path/to/topology.xml
export NCCL_TOPO_DISABLE=1  # Disable auto-detection
```

---

## Common Patterns

### Hybrid NCCL + gRPC Sync

```rust
// Step 1: Sync locally with NCCL
let local_synced = nccl_backend.all_reduce(
    gradients, 
    NcclReduceOp::Avg
).await?;

// Step 2: Sync across nodes with gRPC
grpc_client.push_gradients("grads", local_synced, 0, rank).await?;
let global_synced = grpc_client.pull_parameters("grads", rank).await?;
```

### Barrier Pattern

```rust
// All nodes wait here
client.barrier(step_number, rank).await?;

// Continue only when all nodes arrive
process_next_step();
```

### Heartbeat Loop

```rust
use tokio::time::{interval, Duration};

let mut interval = interval(Duration::from_secs(10));
loop {
    interval.tick().await;
    
    let resources = create_resource_usage();
    if let Err(e) = client.heartbeat(rank, 3, Some(resources)).await {
        warn!("Heartbeat failed: {}", e);
    }
}
```

### Error Handling with Retry

```rust
let mut retries = 0;
let max_retries = 3;

loop {
    match client.push_gradients(key, data.clone(), ver, rank).await {
        Ok(response) => break response,
        Err(e) if retries < max_retries => {
            retries += 1;
            warn!("Retry {}/{}: {}", retries, max_retries, e);
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        Err(e) => return Err(e),
    }
}
```

### Parameter Server Pattern

```rust
// Workers push gradients
for worker_id in 0..world_size {
    client.push_gradients(key, grads, ver, worker_id).await?;
}

// Server automatically averages when all pushed

// Workers pull updated parameters
let params = client.pull_parameters(key, rank).await?;
```

---

## Troubleshooting

### gRPC Connection Failed

```bash
# Check server is running
netstat -tuln | grep 50051

# Check firewall
sudo ufw allow 50051

# Test connectivity
telnet master-node 50051
```

### NCCL Errors

**"Call to connect failed"**
```bash
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0  # Correct interface
```

**"Topology detection failed"**
```bash
export NCCL_TOPO_DISABLE=1
```

**"Out of memory"**
```bash
export NCCL_BUFFSIZE=2097152  # Reduce buffer
# Or reduce batch size
```

### Performance Issues

**High sync time**
- Check network bandwidth: `iperf3 -c other-node`
- Enable RDMA if available
- Increase NCCL buffer size
- Use gradient compression

**Low GPU utilization**
- Check data loading is not bottleneck
- Increase batch size if memory allows
- Use prefetching
- Profile with `nvidia-smi dmon`

---

## Performance Tips

### Network Optimization

1. **Use InfiniBand if available**
   ```bash
   export NCCL_IB_DISABLE=0
   export NCCL_NET_GDR_LEVEL=5
   ```

2. **Tune buffer size**
   ```bash
   export NCCL_BUFFSIZE=16777216  # Start with 16MB
   ```

3. **Enable GPU Direct RDMA**
   ```bash
   export NCCL_NET_GDR_LEVEL=5
   ```

### Client Configuration

```rust
let config = GrpcClientConfig {
    connect_timeout: Duration::from_secs(30),
    request_timeout: Duration::from_secs(120),  // Increase for large models
    keepalive: true,
    keepalive_interval: Duration::from_secs(10),
    max_retries: 5,
    retry_delay: Duration::from_millis(100),
    ..Default::default()
};
```

### Gradient Accumulation

```rust
// Reduce sync frequency
if step % accumulation_steps == 0 {
    sync_gradients();
}
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM nvidia/cuda:12.2.0-cudnn8-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    libnccl2 libnccl-dev \
    protobuf-compiler libprotobuf-dev

WORKDIR /app
COPY . .

RUN cargo build --release --features cuda,nccl

EXPOSE 50051

CMD ["./target/release/grpc_nccl_training", "--mode", "server"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  param-server:
    image: fks-neuromorphic:latest
    ports:
      - "50051:50051"
    command: ["--mode", "server"]

  worker:
    image: fks-neuromorphic:latest
    runtime: nvidia
    environment:
      - RANK=0
      - WORLD_SIZE=2
      - MASTER_ADDR=param-server:50051
    command: ["--mode", "worker", "--local-gpus", "4"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 4
              capabilities: [gpu]
```

---

## Kubernetes Deployment

```yaml
apiVersion: v1
kind: Service
metadata:
  name: param-server
spec:
  selector:
    app: param-server
  ports:
  - port: 50051

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: training-workers
spec:
  serviceName: training
  replicas: 4
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
      - name: worker
        image: fks-neuromorphic:latest
        env:
        - name: MASTER_ADDR
          value: "param-server:50051"
        - name: WORLD_SIZE
          value: "4"
        - name: RANK
          valueFrom:
            fieldRef:
              fieldPath: metadata.labels.statefulset.kubernetes.io/pod-index
        resources:
          limits:
            nvidia.com/gpu: 4
```

---

## Slurm Script

```bash
#!/bin/bash
#SBATCH --job-name=fks-training
#SBATCH --nodes=4
#SBATCH --gpus-per-node=4
#SBATCH --ntasks-per-node=1

# Start parameter server
srun --nodes=1 --ntasks=1 --exclusive \
    cargo run --release --bin grpc_nccl_training -- --mode server &

sleep 5

# Start workers
srun cargo run --release --features nccl \
    --example grpc_nccl_training -- \
    --mode worker \
    --world-size $SLURM_NNODES \
    --local-gpus 4
```

---

## Reference Links

- [Full Documentation](./PHASE_7_GRPC_NCCL.md)
- [Implementation Summary](./GRPC_NCCL_SUMMARY.md)
- [NCCL Documentation](https://docs.nvidia.com/deeplearning/nccl/)
- [gRPC Documentation](https://grpc.io/docs/)
- [Tonic (Rust gRPC)](https://github.com/hyperium/tonic)

---

## Version Info

- **gRPC**: tonic 0.14.2
- **NCCL**: cudarc 0.11 (optional)
- **Protocol Buffers**: prost 0.13
- **Features**: `cuda`, `nccl`
