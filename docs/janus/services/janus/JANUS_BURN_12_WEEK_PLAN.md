# JANUS Neuromorphic Trading System: 12-Week Burn Implementation Plan

**Version:** 1.0  
**Date:** January 2025  
**Framework:** Rust + Burn ML Framework  
**Target:** Production-ready neuromorphic trading intelligence

---

## Executive Summary

This 12-week plan transforms the JANUS architectural specification into a production-grade Rust implementation using the Burn ML framework. The plan follows Burn best practices while implementing the complete neuromorphic brain architecture with CUDA acceleration for model training and selection.

**Key Objectives:**
- ✅ Implement all 9 brain regions (Visual Cortex → Cerebellum)
- ✅ CUDA-accelerated training pipeline with model versioning
- ✅ Automated model selection and replacement
- ✅ Production-ready inference (<40ms latency)
- ✅ Continuous retraining and improvement loop

---

## Current State Assessment

### Existing Crates (Ready)
- ✅ `vision` - DiffGAF + ViViT foundation (needs Burn migration)
- ✅ `ml` - LSTM/MLP models with Burn 0.19
- ✅ `training` - Training infrastructure (needs enhancement)
- ✅ `logic` - LTN foundation (needs Burn integration)
- ✅ `data-quality` - Data pipeline
- ✅ `common` - Shared utilities

### Missing Brain Regions (To Build)
- ❌ `thalamus` - Attention & multi-modal fusion
- ❌ `amygdala` - Risk management & fear response
- ❌ `hypothalamus` - Capital allocation & homeostasis
- ❌ `basal-ganglia` - Hierarchical RL decision making
- ❌ `cerebellum` - Optimal execution (VWAP)
- ❌ `hippocampus` - Memory consolidation & retrieval
- ❌ `prefrontal` - Symbolic reasoning integration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    JANUS Neuromorphic Brain                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT LAYER (Perception)                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Visual Cortex│  │   Sensors    │  │  Order Book  │              │
│  │  DiffGAF +   │  │  (Sentiment, │  │  (L2 Data)   │              │
│  │   ViViT      │  │   News, etc) │  │              │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                      │
│         └──────────────────┼──────────────────┘                      │
│                            ▼                                         │
│  FUSION LAYER                                                        │
│  ┌────────────────────────────────────────┐                         │
│  │         Thalamus (Attention)           │                         │
│  │  Multi-modal fusion & state embedding  │                         │
│  └────────────────┬───────────────────────┘                         │
│                   │                                                  │
│                   ▼                                                  │
│  DECISION LAYER                                                      │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  Basal Ganglia (Hierarchical RL)                     │           │
│  │  ┌─────────────┐         ┌──────────────┐            │           │
│  │  │  Manager    │────────▶│   Worker     │            │           │
│  │  │  (Strategy) │  Goals  │  (Tactics)   │            │           │
│  │  └─────────────┘         └──────┬───────┘            │           │
│  │         ▲                        │                    │           │
│  │         │                        ▼                    │           │
│  │  ┌──────┴──────────┐    ┌───────────────┐            │           │
│  │  │  Hippocampus    │    │ Actor-Critic  │            │           │
│  │  │  (Memory/ER)    │    │     (A2C)     │            │           │
│  │  └─────────────────┘    └───────┬───────┘            │           │
│  └──────────────────────────────────┼────────────────────┘           │
│                                     │                                │
│                                     ▼                                │
│  SAFETY LAYER                                                        │
│  ┌───────────────────┐    ┌──────────────────┐                      │
│  │  Prefrontal Cortex│    │    Amygdala      │                      │
│  │  (LTN Compliance) │◀───│  (Fear/Risk)     │                      │
│  └────────┬──────────┘    └──────────────────┘                      │
│           │ Veto/Approve                                             │
│           ▼                                                          │
│  EXECUTION LAYER                                                     │
│  ┌─────────────────────┐  ┌──────────────────┐                      │
│  │   Hypothalamus      │  │   Cerebellum     │                      │
│  │  (Position Sizing)  │─▶│  (VWAP Slicing)  │                      │
│  └─────────────────────┘  └────────┬─────────┘                      │
│                                     │                                │
│                                     ▼                                │
│                            ┌────────────────┐                        │
│                            │    Exchange    │                        │
│                            └────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Crate Structure (Target State)

```
src/janus/crates/
├── brain/                      # NEW - Brain region implementations
│   ├── visual-cortex/          # DiffGAF + ViViT (migrate from vision/)
│   ├── thalamus/               # Multi-modal fusion + attention
│   ├── basal-ganglia/          # Hierarchical RL (Manager/Worker)
│   ├── hippocampus/            # Experience replay + memory
│   ├── prefrontal/             # LTN compliance layer
│   ├── amygdala/               # Risk management + circuit breakers
│   ├── hypothalamus/           # Capital allocation (Kelly, etc.)
│   ├── cerebellum/             # Optimal execution (StaticVWAP)
│   └── common/                 # Shared brain utilities
│
├── training/                   # ENHANCED - Training infrastructure
│   ├── orchestrator/           # Multi-region training coordinator
│   ├── model-registry/         # Model versioning + selection
│   ├── metrics/                # Training metrics + TensorBoard
│   └── cuda/                   # CUDA kernel optimizations
│
├── inference/                  # NEW - Production inference
│   ├── runtime/                # ONNX Runtime integration
│   ├── quantization/           # FP16/INT8 quantization
│   └── batching/               # Dynamic batching
│
├── memory/                     # ENHANCED - Memory systems
│   ├── experience-replay/      # Prioritized replay buffer
│   ├── vector-store/           # Qdrant integration
│   └── consolidation/          # Hippocampal memory consolidation
│
└── integration/                # NEW - System integration
    ├── forward-service/        # Wake state (Rust)
    ├── backward-service/       # Sleep state (Rust + PyTorch bridge)
    └── bridge/                 # Shared memory + gRPC
```

---

## 12-Week Implementation Plan

### **Phase 1: Foundation & Infrastructure (Weeks 1-3)**

#### **Week 1: Project Restructuring & Training Infrastructure**

**Objectives:**
- Reorganize crates into neuromorphic brain structure
- Setup CUDA training environment in WSL
- Implement model registry and versioning system

**Deliverables:**

1. **Crate Reorganization**
   ```bash
   # Create new brain region crates
   cargo new --lib crates/brain/visual-cortex
   cargo new --lib crates/brain/thalamus
   cargo new --lib crates/brain/basal-ganglia
   cargo new --lib crates/brain/hippocampus
   cargo new --lib crates/brain/prefrontal
   cargo new --lib crates/brain/amygdala
   cargo new --lib crates/brain/hypothalamus
   cargo new --lib crates/brain/cerebellum
   cargo new --lib crates/brain/common
   
   # Create training infrastructure
   cargo new --lib crates/training/orchestrator
   cargo new --lib crates/training/model-registry
   cargo new --lib crates/training/metrics
   cargo new --lib crates/training/cuda
   ```

2. **CUDA Environment Setup**
   ```dockerfile
   # Dockerfile.training
   FROM nvidia/cuda:12.2.0-cudnn8-devel-ubuntu22.04
   
   RUN apt-get update && apt-get install -y \
       build-essential curl git \
       && rm -rf /var/lib/apt/lists/*
   
   # Install Rust
   RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
   ENV PATH="/root/.cargo/bin:${PATH}"
   
   # Install Burn with CUDA support
   WORKDIR /app
   COPY Cargo.toml .
   RUN cargo fetch
   ```

3. **Model Registry System**
   ```rust
   // crates/training/model-registry/src/lib.rs
   use burn::prelude::*;
   use serde::{Deserialize, Serialize};
   use std::path::PathBuf;
   
   #[derive(Debug, Clone, Serialize, Deserialize)]
   pub struct ModelMetadata {
       pub model_id: String,
       pub brain_region: BrainRegion,
       pub version: u32,
       pub timestamp: i64,
       pub metrics: ModelMetrics,
       pub config: serde_json::Value,
   }
   
   #[derive(Debug, Clone, Serialize, Deserialize)]
   pub struct ModelMetrics {
       pub validation_loss: f64,
       pub sharpe_ratio: Option<f64>,
       pub win_rate: Option<f64>,
       pub max_drawdown: Option<f64>,
   }
   
   #[derive(Debug, Clone, Serialize, Deserialize)]
   pub enum BrainRegion {
       VisualCortex,
       Thalamus,
       BasalGanglia,
       Hippocampus,
       Prefrontal,
       Amygdala,
       Hypothalamus,
       Cerebellum,
   }
   
   pub struct ModelRegistry {
       base_path: PathBuf,
       active_models: HashMap<BrainRegion, ModelMetadata>,
   }
   
   impl ModelRegistry {
       pub fn new(base_path: PathBuf) -> Self {
           Self {
               base_path,
               active_models: HashMap::new(),
           }
       }
       
       pub fn register_model(
           &mut self,
           region: BrainRegion,
           metadata: ModelMetadata,
           weights_path: PathBuf,
       ) -> Result<(), Error> {
           // Save metadata
           let metadata_path = self.base_path
               .join(region.to_string())
               .join(format!("v{}.json", metadata.version));
           std::fs::write(&metadata_path, serde_json::to_string(&metadata)?)?;
           
           // Copy model weights
           let model_path = self.base_path
               .join(region.to_string())
               .join(format!("v{}.bin", metadata.version));
           std::fs::copy(weights_path, model_path)?;
           
           Ok(())
       }
       
       pub fn select_best_model(
           &mut self,
           region: BrainRegion,
           metric: ModelSelectionMetric,
       ) -> Result<ModelMetadata, Error> {
           // Load all versions
           let versions = self.list_versions(&region)?;
           
           // Select best based on metric
           let best = versions.into_iter()
               .max_by(|a, b| {
                   let score_a = metric.score(&a.metrics);
                   let score_b = metric.score(&b.metrics);
                   score_a.partial_cmp(&score_b).unwrap()
               })
               .ok_or(Error::NoModelsFound)?;
           
           // Update active model
           self.active_models.insert(region.clone(), best.clone());
           
           Ok(best)
       }
       
       pub fn get_active_model(&self, region: &BrainRegion) -> Option<&ModelMetadata> {
           self.active_models.get(region)
       }
   }
   
   pub enum ModelSelectionMetric {
       ValidationLoss,
       SharpeRatio,
       WinRate,
       Composite(Vec<(f64, ModelSelectionMetric)>), // Weighted combination
   }
   
   impl ModelSelectionMetric {
       pub fn score(&self, metrics: &ModelMetrics) -> f64 {
           match self {
               Self::ValidationLoss => -metrics.validation_loss, // Lower is better
               Self::SharpeRatio => metrics.sharpe_ratio.unwrap_or(0.0),
               Self::WinRate => metrics.win_rate.unwrap_or(0.0),
               Self::Composite(weights) => {
                   weights.iter()
                       .map(|(w, m)| w * m.score(metrics))
                       .sum()
               }
           }
       }
   }
   ```

**Testing:**
- ✅ Model registration and retrieval
- ✅ Version comparison and selection
- ✅ CUDA environment smoke test

**Documentation:**
- [ ] Crate structure rationale
- [ ] Model registry API docs
- [ ] CUDA setup guide

---

#### **Week 2: Visual Cortex - DiffGAF Migration to Burn**

**Objectives:**
- Migrate DiffGAF from legacy implementation to Burn 0.19
- Implement efficient CUDA kernels for GAF transformation
- Setup automated testing and benchmarking

**Deliverables:**

1. **DiffGAF Implementation (Burn)**
   ```rust
   // crates/brain/visual-cortex/src/diffgaf.rs
   use burn::{
       nn::Linear,
       prelude::*,
       tensor::{backend::Backend, Tensor},
   };
   
   #[derive(Module, Debug)]
   pub struct DiffGAF<B: Backend> {
       gamma: Param<Tensor<B, 1>>,  // Learnable scale
       beta: Param<Tensor<B, 1>>,   // Learnable shift
       method: GAFMethod,
   }
   
   #[derive(Debug, Clone)]
   pub enum GAFMethod {
       GASF,  // Gramian Angular Summation Field
       GADF,  // Gramian Angular Difference Field
   }
   
   impl<B: Backend> DiffGAF<B> {
       pub fn new(device: &B::Device, method: GAFMethod) -> Self {
           let gamma = Param::from_tensor(
               Tensor::ones([1], device)
           );
           let beta = Param::from_tensor(
               Tensor::zeros([1], device)
           );
           
           Self { gamma, beta, method }
       }
       
       pub fn forward(&self, x: Tensor<B, 2>) -> Tensor<B, 3> {
           // x: [batch, sequence_length]
           let [batch_size, seq_len] = x.dims();
           
           // Normalization
           let mean = x.clone().mean_dim(1);  // [batch, 1]
           let std = x.clone().var_dim(1).sqrt();  // [batch, 1]
           let eps = 1e-8;
           
           // Learnable normalization: γ * (x - μ) / σ + β
           let x_norm = self.gamma.val()
               .mul_scalar(
                   x.sub(mean).div(std.add_scalar(eps))
               )
               .add(self.beta.val());
           
           // Clamp to [-1 + ε, 1 - ε] for arccos stability
           let x_clamped = x_norm.clamp(-0.999999, 0.999999);
           
           // Polar encoding: φ = arccos(x)
           let phi = x_clamped.acos();  // [batch, seq_len]
           
           // Gramian matrix construction
           match self.method {
               GAFMethod::GASF => {
                   // cos(φᵢ + φⱼ) = cos(φᵢ)cos(φⱼ) - sin(φᵢ)sin(φⱼ)
                   let cos_phi = phi.clone().cos();  // [batch, seq_len]
                   let sin_phi = phi.sin();          // [batch, seq_len]
                   
                   // Outer products
                   let cos_outer = cos_phi.clone()
                       .unsqueeze_dim(2)  // [batch, seq_len, 1]
                       .matmul(
                           cos_phi.unsqueeze_dim(1)  // [batch, 1, seq_len]
                       );  // [batch, seq_len, seq_len]
                   
                   let sin_outer = sin_phi.clone()
                       .unsqueeze_dim(2)
                       .matmul(sin_phi.unsqueeze_dim(1));
                   
                   cos_outer.sub(sin_outer)
               }
               GAFMethod::GADF => {
                   // sin(φᵢ - φⱼ) = sin(φᵢ)cos(φⱼ) - cos(φᵢ)sin(φⱼ)
                   let cos_phi = phi.clone().cos();
                   let sin_phi = phi.sin();
                   
                   let sin_cos_outer = sin_phi.clone()
                       .unsqueeze_dim(2)
                       .matmul(cos_phi.unsqueeze_dim(1));
                   
                   let cos_sin_outer = cos_phi.clone()
                       .unsqueeze_dim(2)
                       .matmul(sin_phi.unsqueeze_dim(1));
                   
                   sin_cos_outer.sub(cos_sin_outer)
               }
           }
       }
   }
   
   #[derive(Config, Debug)]
   pub struct DiffGAFConfig {
       pub method: GAFMethod,
       #[config(default = true)]
       pub learnable: bool,
   }
   
   impl DiffGAFConfig {
       pub fn init<B: Backend>(&self, device: &B::Device) -> DiffGAF<B> {
           DiffGAF::new(device, self.method.clone())
       }
   }
   ```

2. **CUDA Kernel Optimization**
   ```rust
   // crates/training/cuda/src/gaf_kernels.rs
   #[cfg(feature = "cuda")]
   pub mod cuda_gaf {
       use burn_cuda::kernel::KernelSettings;
       
       // Custom CUDA kernel for fused GAF computation
       pub fn fused_gaf_kernel(
           x: &CudaTensor,
           gamma: f32,
           beta: f32,
           method: GAFMethod,
       ) -> CudaTensor {
           // Fuse normalization + polar encoding + Gramian computation
           // into single CUDA kernel to minimize memory transfers
           
           let kernel_code = r#"
           __global__ void fused_gaf(
               const float* x,
               float* output,
               float gamma,
               float beta,
               int batch_size,
               int seq_len,
               int method
           ) {
               int batch_idx = blockIdx.x;
               int i = threadIdx.x;
               int j = threadIdx.y;
               
               if (batch_idx >= batch_size || i >= seq_len || j >= seq_len) return;
               
               // Shared memory for normalization stats
               __shared__ float mean;
               __shared__ float std;
               
               // Compute mean and std (reduction)
               // ... (optimized reduction implementation)
               
               // Normalize
               float x_i = x[batch_idx * seq_len + i];
               float x_j = x[batch_idx * seq_len + j];
               
               float x_i_norm = gamma * (x_i - mean) / (std + 1e-8) + beta;
               float x_j_norm = gamma * (x_j - mean) / (std + 1e-8) + beta;
               
               // Clamp and compute angles
               x_i_norm = fmaxf(-0.999999f, fminf(0.999999f, x_i_norm));
               x_j_norm = fmaxf(-0.999999f, fminf(0.999999f, x_j_norm));
               
               float phi_i = acosf(x_i_norm);
               float phi_j = acosf(x_j_norm);
               
               // Gramian computation
               float result;
               if (method == 0) {  // GASF
                   result = cosf(phi_i) * cosf(phi_j) - sinf(phi_i) * sinf(phi_j);
               } else {  // GADF
                   result = sinf(phi_i) * cosf(phi_j) - cosf(phi_i) * sinf(phi_j);
               }
               
               output[batch_idx * seq_len * seq_len + i * seq_len + j] = result;
           }
           "#;
           
           // Compile and launch kernel
           // ... (kernel compilation and launch logic)
       }
   }
   ```

3. **Benchmarking Suite**
   ```rust
   // crates/brain/visual-cortex/benches/diffgaf_bench.rs
   use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
   use burn::backend::{NdArray, Wgpu, Cuda};
   use visual_cortex::DiffGAF;
   
   fn benchmark_diffgaf(c: &mut Criterion) {
       let mut group = c.benchmark_group("DiffGAF");
       
       for seq_len in [32, 64, 128, 256].iter() {
           group.bench_with_input(
               BenchmarkId::new("CPU", seq_len),
               seq_len,
               |b, &seq_len| {
                   let device = Default::default();
                   let model = DiffGAF::<NdArray>::new(&device, GAFMethod::GASF);
                   let input = Tensor::<NdArray, 2>::random(
                       [32, seq_len],
                       Distribution::Uniform(-1.0, 1.0),
                       &device,
                   );
                   
                   b.iter(|| {
                       let _ = black_box(model.forward(input.clone()));
                   });
               },
           );
           
           #[cfg(feature = "cuda")]
           group.bench_with_input(
               BenchmarkId::new("CUDA", seq_len),
               seq_len,
               |b, &seq_len| {
                   let device = CudaDevice::default();
                   let model = DiffGAF::<Cuda>::new(&device, GAFMethod::GASF);
                   let input = Tensor::<Cuda, 2>::random(
                       [32, seq_len],
                       Distribution::Uniform(-1.0, 1.0),
                       &device,
                   );
                   
                   b.iter(|| {
                       let _ = black_box(model.forward(input.clone()));
                   });
               },
           );
       }
       
       group.finish();
   }
   
   criterion_group!(benches, benchmark_diffgaf);
   criterion_main!(benches);
   ```

**Testing:**
- ✅ DiffGAF forward pass correctness
- ✅ Gradient flow through learnable parameters
- ✅ CUDA kernel vs. CPU equivalence
- ✅ Performance benchmarks (CPU vs. CUDA)

**Target Performance:**
- CPU (NdArray): ~5ms for 64×64 GAF
- CUDA: ~0.5ms for 64×64 GAF (10x speedup)

---

#### **Week 3: ViViT Implementation & Visual Cortex Integration**

**Objectives:**
- Implement Video Vision Transformer in Burn
- Integrate DiffGAF → ViViT pipeline
- Setup end-to-end training loop

**Deliverables:**

1. **ViViT Architecture**
   ```rust
   // crates/brain/visual-cortex/src/vivit.rs
   use burn::{
       nn::{
           attention::{MultiHeadAttention, MultiHeadAttentionConfig},
           Linear, LinearConfig, LayerNorm, LayerNormConfig,
           Dropout, DropoutConfig,
       },
       prelude::*,
   };
   
   #[derive(Module, Debug)]
   pub struct TubeletEmbedding<B: Backend> {
       projection: Linear<B>,
       pos_embedding: Param<Tensor<B, 3>>,
   }
   
   impl<B: Backend> TubeletEmbedding<B> {
       pub fn new(config: &TubeletEmbeddingConfig, device: &B::Device) -> Self {
           let projection = LinearConfig::new(
               config.tubelet_size * config.patch_size * config.patch_size * config.in_channels,
               config.embed_dim,
           ).init(device);
           
           let num_patches = (config.num_frames / config.tubelet_size)
               * (config.img_size / config.patch_size).pow(2);
           
           let pos_embedding = Param::from_tensor(
               Tensor::random(
                   [1, num_patches, config.embed_dim],
                   Distribution::Normal(0.0, 0.02),
                   device,
               )
           );
           
           Self { projection, pos_embedding }
       }
       
       pub fn forward(&self, video: Tensor<B, 5>) -> Tensor<B, 3> {
           // video: [batch, time, height, width, channels]
           let [batch_size, t, h, w, c] = video.dims();
           
           // Extract tubelets (3D patches)
           let patches = self.extract_tubelets(video);  // [batch, num_patches, tubelet_dim]
           
           // Linear projection
           let embeddings = self.projection.forward(patches);  // [batch, num_patches, embed_dim]
           
           // Add positional embeddings
           embeddings.add(self.pos_embedding.val())
       }
       
       fn extract_tubelets(&self, video: Tensor<B, 5>) -> Tensor<B, 3> {
           // Unfold operation to extract 3D patches
           // ... (implementation using Burn tensor operations)
       }
   }
   
   #[derive(Module, Debug)]
   pub struct ViViTBlock<B: Backend> {
       spatial_attn: MultiHeadAttention<B>,
       temporal_attn: Option<MultiHeadAttention<B>>,
       mlp: MLP<B>,
       norm1: LayerNorm<B>,
       norm2: LayerNorm<B>,
       norm3: Option<LayerNorm<B>>,
       dropout: Dropout,
   }
   
   impl<B: Backend> ViViTBlock<B> {
       pub fn forward(&self, x: Tensor<B, 3>, is_spatial: bool) -> Tensor<B, 3> {
           // Pre-norm architecture
           let normed = self.norm1.forward(x.clone());
           
           let attn_out = if is_spatial {
               self.spatial_attn.forward(normed.clone(), normed.clone(), normed)
           } else {
               self.temporal_attn.as_ref()
                   .unwrap()
                   .forward(normed.clone(), normed.clone(), normed)
           };
           
           // Residual connection
           let x = x.add(self.dropout.forward(attn_out));
           
           // MLP block
           let normed = self.norm2.forward(x.clone());
           let mlp_out = self.mlp.forward(normed);
           x.add(self.dropout.forward(mlp_out))
       }
   }
   
   #[derive(Module, Debug)]
   pub struct ViViT<B: Backend> {
       tubelet_embed: TubeletEmbedding<B>,
       spatial_blocks: Vec<ViViTBlock<B>>,
       temporal_blocks: Vec<ViViTBlock<B>>,
       norm: LayerNorm<B>,
       head: Linear<B>,
   }
   
   #[derive(Config, Debug)]
   pub struct ViViTConfig {
       #[config(default = 64)]
       pub img_size: usize,
       #[config(default = 8)]
       pub patch_size: usize,
       #[config(default = 16)]
       pub num_frames: usize,
       #[config(default = 2)]
       pub tubelet_size: usize,
       #[config(default = 3)]
       pub in_channels: usize,
       #[config(default = 512)]
       pub embed_dim: usize,
       #[config(default = 8)]
       pub depth: usize,
       #[config(default = 8)]
       pub num_heads: usize,
       #[config(default = 2048)]
       pub mlp_dim: usize,
       #[config(default = 0.1)]
       pub dropout: f64,
       #[config(default = 64)]
       pub output_dim: usize,
   }
   
   impl ViViTConfig {
       pub fn init<B: Backend>(&self, device: &B::Device) -> ViViT<B> {
           let tubelet_embed = TubeletEmbedding::new(self, device);
           
           let spatial_blocks = (0..self.depth / 2)
               .map(|_| ViViTBlock::new(self, device, true))
               .collect();
           
           let temporal_blocks = (0..self.depth / 2)
               .map(|_| ViViTBlock::new(self, device, false))
               .collect();
           
           let norm = LayerNormConfig::new(self.embed_dim).init(device);
           
           let head = LinearConfig::new(self.embed_dim, self.output_dim).init(device);
           
           ViViT {
               tubelet_embed,
               spatial_blocks,
               temporal_blocks,
               norm,
               head,
           }
       }
   }
   
   impl<B: Backend> ViViT<B> {
       pub fn forward(&self, video: Tensor<B, 5>) -> Tensor<B, 2> {
           // video: [batch, time, height, width, channels]
           
           // Tubelet embedding
           let mut x = self.tubelet_embed.forward(video);  // [batch, num_patches, embed_dim]
           
           // Spatial attention blocks
           for block in &self.spatial_blocks {
               x = block.forward(x, true);
           }
           
           // Temporal attention blocks
           for block in &self.temporal_blocks {
               x = block.forward(x, false);
           }
           
           // Global average pooling
           let x = x.mean_dim(1);  // [batch, embed_dim]
           
           // Classification head
           let x = self.norm.forward(x);
           self.head.forward(x)  // [batch, output_dim]
       }
   }
   ```

2. **Visual Cortex Pipeline**
   ```rust
   // crates/brain/visual-cortex/src/pipeline.rs
   #[derive(Module, Debug)]
   pub struct VisualCortex<B: Backend> {
       diffgaf_gasf: DiffGAF<B>,
       diffgaf_gadf: DiffGAF<B>,
       vivit: ViViT<B>,
   }
   
   impl<B: Backend> VisualCortex<B> {
       pub fn forward(&self, price_history: Tensor<B, 2>) -> Tensor<B, 2> {
           // price_history: [batch, sequence_length]
           
           // Generate multi-channel GAF images
           let gasf = self.diffgaf_gasf.forward(price_history.clone());  // [B, S, S]
           let gadf = self.diffgaf_gadf.forward(price_history.clone());  // [B, S, S]
           
           // Stack as 3-channel image
           let gaf_image = Tensor::stack(vec![gasf, gadf], 3);  // [B, S, S, 2]
           
           // Create video by sliding window
           let video = self.create_video_sequence(gaf_image);  // [B, T, H, W, C]
           
           // ViViT inference
           self.vivit.forward(video)  // [B, embedding_dim]
       }
       
       fn create_video_sequence(&self, gaf_images: Tensor<B, 4>) -> Tensor<B, 5> {
           // Sliding window to create temporal sequence
           // ... (implementation)
       }
   }
   ```

3. **Training Loop**
   ```rust
   // crates/brain/visual-cortex/src/train.rs
   use burn::optim::{AdamConfig, GradientsParams, Optimizer};
   use burn::train::{
       LearnerBuilder, MetricEarlyStoppingStrategy, StoppingCondition,
   };
   
   pub fn train_visual_cortex<B: AutodiffBackend>(
       model: VisualCortex<B>,
       train_data: DataLoader,
       val_data: DataLoader,
       device: B::Device,
   ) -> VisualCortex<B> {
       let optimizer = AdamConfig::new()
           .with_weight_decay(Some(WeightDecayConfig::new(1e-4)))
           .init();
       
       let learner = LearnerBuilder::new("visual-cortex")
           .devices(vec![device.clone()])
           .num_epochs(100)
           .metric_train(LossMetric::new())
           .metric_valid(LossMetric::new())
           .metric_valid(SharpeRatioMetric::new())
           .early_stopping(MetricEarlyStoppingStrategy::new::<LossMetric>(
               Aggregate::Mean,
               Direction::Lowest,
               Split::Valid,
               StoppingCondition::NoImprovementSince { n_epochs: 10 },
           ))
           .build(model, optimizer, 1e-3);
       
       let model_trained = learner.fit(train_data, val_data);
       
       model_trained
   }
   ```

**Testing:**
- ✅ End-to-end forward pass (OHLCV → embedding)
- ✅ Gradient flow through entire pipeline
- ✅ Training convergence on synthetic data
- ✅ Inference latency < 5ms (CUDA)

---

### **Phase 2: Decision-Making Brain Regions (Weeks 4-6)**

#### **Week 4: Thalamus - Multi-Modal Fusion**

**Objectives:**
- Implement attention-based fusion of visual cortex + other sensors
- Build multi-modal state representation

**Deliverables:**

1. **Thalamus Module**
   ```rust
   // crates/brain/thalamus/src/lib.rs
   use burn::{
       nn::{
           attention::{MultiHeadAttention, MultiHeadAttentionConfig},
           Linear, LinearConfig,
       },
       prelude::*,
   };
   
   #[derive(Module, Debug)]
   pub struct Thalamus<B: Backend> {
       visual_projection: Linear<B>,
       orderbook_projection: Linear<B>,
       sentiment_projection: Linear<B>,
       cross_attention: MultiHeadAttention<B>,
       fusion_mlp: MLP<B>,
   }
   
   #[derive(Debug)]
   pub struct MarketState<B: Backend> {
       pub visual_embedding: Tensor<B, 2>,      // [batch, 64]
       pub orderbook_features: Tensor<B, 2>,     // [batch, 32]
       pub sentiment_features: Tensor<B, 2>,     // [batch, 16]
   }
   
   impl<B: Backend> Thalamus<B> {
       pub fn forward(&self, state: MarketState<B>) -> Tensor<B, 2> {
           // Project all modalities to common dimension
           let visual = self.visual_projection.forward(state.visual_embedding);
           let orderbook = self.orderbook_projection.forward(state.orderbook_features);
           let sentiment = self.sentiment_projection.forward(state.sentiment_features);
           
           // Stack as sequence
           let multi_modal = Tensor::stack(vec![visual, orderbook, sentiment], 1);
           // Shape: [batch, 3, hidden_dim]
           
           // Cross-modal attention
           let attended = self.cross_attention.forward(
               multi_modal.clone(),
               multi_modal.clone(),
               multi_modal,
           );  // [batch, 3, hidden_dim]
           
           // Global pooling + MLP
           let pooled = attended.mean_dim(1);  // [batch, hidden_dim]
           self.fusion_mlp.forward(pooled)     // [batch, state_dim]
       }
   }
   ```

**Testing:**
- ✅ Multi-modal fusion correctness
- ✅ Attention weight interpretability
- ✅ Latency < 2ms

---

#### **Week 5: Basal Ganglia - Hierarchical RL**

**Objectives:**
- Implement Manager-Worker hierarchical RL architecture
- Actor-Critic with PPO training

**Deliverables:**

1. **Manager Network (Strategic Policy)**
   ```rust
   // crates/brain/basal-ganglia/src/manager.rs
   #[derive(Module, Debug)]
   pub struct ManagerNetwork<B: Backend> {
       policy_net: MLP<B>,
       value_net: MLP<B>,
   }
   
   #[derive(Debug, Clone)]
   pub struct Goal {
       pub target_position: f64,    // Target position size
       pub horizon: usize,            // Time horizon (steps)
       pub risk_budget: f64,          // Risk allocation
   }
   
   impl<B: Backend> ManagerNetwork<B> {
       pub fn forward(
           &self,
           state: Tensor<B, 2>,
       ) -> (Goal, Tensor<B, 1>) {  // (goal, value)
           let policy_out = self.policy_net.forward(state.clone());
           let value = self.value_net.forward(state);
           
           // Decode goal from policy output
           let goal = self.decode_goal(policy_out);
           
           (goal, value.squeeze(1))
       }
       
       fn decode_goal(&self, policy: Tensor<B, 2>) -> Goal {
           // Extract goal parameters from policy network output
           // ... (implementation)
       }
   }
   ```

2. **Worker Network (Tactical Policy)**
   ```rust
   // crates/brain/basal-ganglia/src/worker.rs
   #[derive(Module, Debug)]
   pub struct WorkerNetwork<B: Backend> {
       actor: MLP<B>,
       critic: MLP<B>,
   }
   
   #[derive(Debug, Clone)]
   pub struct Action {
       pub trade_signal: TradeSignal,  // Buy/Sell/Hold
       pub urgency: f64,                 // Execution urgency
   }
   
   impl<B: Backend> WorkerNetwork<B> {
       pub fn forward(
           &self,
           state: Tensor<B, 2>,
           goal: &Goal,
       ) -> (Action, Tensor<B, 1>) {  // (action, value)
           // Concatenate state + goal
           let goal_tensor = self.goal_to_tensor(goal);
           let input = Tensor::cat(vec![state, goal_tensor], 1);
           
           // Actor-Critic forward pass
           let action_logits = self.actor.forward(input.clone());
           let value = self.critic.forward(input);
           
           let action = self.sample_action(action_logits);
           
           (action, value.squeeze(1))
       }
   }
   ```

3. **PPO Training**
   ```rust
   // crates/brain/basal-ganglia/src/train.rs
   pub struct PPOTrainer<B: AutodiffBackend> {
       manager: ManagerNetwork<B>,
       worker: WorkerNetwork<B>,
       optimizer: Adam<B>,
       clip_epsilon: f64,
       value_coef: f64,
       entropy_coef: f64,
   }
   
   impl<B: AutodiffBackend> PPOTrainer<B> {
       pub fn update(
           &mut self,
           trajectories: Vec<Trajectory>,
       ) -> TrainingMetrics {
           let mut total_loss = 0.0;
           
           for trajectory in trajectories {
               // Compute advantages using GAE
               let advantages = self.compute_gae(&trajectory);
               
               // Manager update
               let manager_loss = self.update_manager(&trajectory, &advantages);
               
               // Worker update
               let worker_loss = self.update_worker(&trajectory, &advantages);
               
               total_loss += manager_loss + worker_loss;
           }
           
           TrainingMetrics {
               loss: total_loss / trajectories.len() as f64,
           }
       }
       
       fn update_worker(
           &mut self,
           trajectory: &Trajectory,
           advantages: &[f64],
       ) -> f64 {
           let (old_log_probs, old_values) = trajectory.worker_outputs;
           let returns = trajectory.compute_returns();
           
           // Forward pass
           let (actions, values) = self.worker.forward(
               trajectory.states.clone(),
               &trajectory.goal,
           );
           
           // Compute new log probs
           let new_log_probs = self.compute_log_probs(&actions);
           
           // PPO clipped surrogate loss
           let ratio = (new_log_probs - old_log_probs).exp();
           let clipped_ratio = ratio.clamp(
               1.0 - self.clip_epsilon,
               1.0 + self.clip_epsilon,
           );
           
           let advantages_tensor = Tensor::from_floats(advantages);
           let policy_loss = -(ratio.min(clipped_ratio) * advantages_tensor).mean();
           
           // Value loss
           let value_loss = (values - returns).pow(2).mean();
           
           // Total loss
           let loss = policy_loss + self.value_coef * value_loss;
           
           // Backprop
           let grads = loss.backward();
           self.optimizer.step(1e-4, grads);
           
           loss.into_scalar()
       }
   }
   ```

**Testing:**
- ✅ Hierarchical policy learning on toy environment
- ✅ Goal-conditioned behavior emergence
- ✅ PPO convergence

---

#### **Week 6: Hippocampus - Memory & Experience Replay**

**Objectives:**
- Implement prioritized experience replay
- Memory consolidation system

**Deliverables:**

1. **Experience Replay Buffer**
   ```rust
   // crates/brain/hippocampus/src/replay.rs
   use std::collections::VecDeque;
   use rand::distributions::WeightedIndex;
   
   #[derive(Debug, Clone)]
   pub struct Experience {
       pub state: Vec<f32>,
       pub action: Action,
       pub reward: f64,
       pub next_state: Vec<f32>,
       pub done: bool,
       pub priority: f64,
   }
   
   pub struct PrioritizedReplayBuffer {
       buffer: VecDeque<Experience>,
       capacity: usize,
       alpha: f64,  // Priority exponent
       beta: f64,   // Importance sampling exponent
   }
   
   impl PrioritizedReplayBuffer {
       pub fn new(capacity: usize, alpha: f64, beta: f64) -> Self {
           Self {
               buffer: VecDeque::with_capacity(capacity),
               capacity,
               alpha,
               beta,
           }
       }
       
       pub fn push(&mut self, mut experience: Experience) {
           // Assign max priority to new experiences
           if self.buffer.is_empty() {
               experience.priority = 1.0;
           } else {
               let max_priority = self.buffer.iter()
                   .map(|e| e.priority)
                   .max_by(|a, b| a.partial_cmp(b).unwrap())
                   .unwrap();
               experience.priority = max_priority;
           }
           
           if self.buffer.len() >= self.capacity {
               self.buffer.pop_front();
           }
           
           self.buffer.push_back(experience);
       }
       
       pub fn sample(&self, batch_size: usize) -> (Vec<Experience>, Vec<f64>) {
           let priorities: Vec<f64> = self.buffer.iter()
               .map(|e| e.priority.powf(self.alpha))
               .collect();
           
           let dist = WeightedIndex::new(&priorities).unwrap();
           let mut rng = rand::thread_rng();
           
           let indices: Vec<usize> = (0..batch_size)
               .map(|_| dist.sample(&mut rng))
               .collect();
           
           let experiences = indices.iter()
               .map(|&i| self.buffer[i].clone())
               .collect();
           
           // Importance sampling weights
           let weights: Vec<f64> = indices.iter()
               .map(|&i| {
                   let prob = priorities[i] / priorities.iter().sum::<f64>();
                   (self.buffer.len() as f64 * prob).powf(-self.beta)
               })
               .collect();
           
           // Normalize weights
           let max_weight = weights.iter()
               .max_by(|a, b| a.partial_cmp(b).unwrap())
               .unwrap();
           let weights: Vec<f64> = weights.iter()
               .map(|w| w / max_weight)
               .collect();
           
           (experiences, weights)
       }
       
       pub fn update_priorities(&mut self, indices: Vec<usize>, td_errors: Vec<f64>) {
           for (idx, td_error) in indices.into_iter().zip(td_errors) {
               if idx < self.buffer.len() {
                   self.buffer[idx].priority = td_error.abs() + 1e-6;
               }
           }
       }
   }
   ```

2. **Memory Consolidation**
   ```rust
   // crates/brain/hippocampus/src/consolidation.rs
   pub struct MemoryConsolidation {
       short_term: PrioritizedReplayBuffer,
       long_term: Vec<Experience>,
       consolidation_threshold: f64,
   }
   
   impl MemoryConsolidation {
       pub fn consolidate(&mut self) {
           // Select high-priority experiences for long-term storage
           let important_experiences: Vec<Experience> = self.short_term.buffer
               .iter()
               .filter(|e| e.priority > self.consolidation_threshold)
               .cloned()
               .collect();
           
           // Add to long-term memory
           self.long_term.extend(important_experiences);
           
           // Optional: Compress long-term memory using clustering
           if self.long_term.len() > 10000 {
               self.compress_long_term_memory();
           }
       }
       
       fn compress_long_term_memory(&mut self) {
           // Use k-means clustering to summarize similar experiences
           // ... (implementation)
       }
   }
   ```

**Testing:**
- ✅ Replay buffer sampling distribution
- ✅ Priority updates correctness
- ✅ Memory consolidation effectiveness

---

### **Phase 3: Safety & Execution Layers (Weeks 7-9)**

#### **Week 7: Prefrontal Cortex - LTN Compliance**

**Objectives:**
- Migrate Logic Tensor Networks to Burn
- Implement differentiable compliance checking

**Deliverables:**

1. **Logic Tensor Networks**
   ```rust
   // crates/brain/prefrontal/src/ltn.rs
   use burn::prelude::*;
   
   #[derive(Debug, Clone)]
   pub enum TNorm {
       Lukasiewicz,  // min(a + b, 1)
       Product,      // a * b
       Godel,        // min(a, b)
   }
   
   #[derive(Module, Debug)]
   pub struct Predicate<B: Backend> {
       network: MLP<B>,
   }
   
   impl<B: Backend> Predicate<B> {
       pub fn forward(&self, x: Tensor<B, 2>) -> Tensor<B, 1> {
           // Output in [0, 1] (truth value)
           self.network.forward(x).sigmoid()
       }
   }
   
   pub struct LTN<B: Backend> {
       predicates: HashMap<String, Predicate<B>>,
       t_norm: TNorm,
   }
   
   impl<B: Backend> LTN<B> {
       pub fn evaluate_rule(
           &self,
           rule: &Rule,
           state: &Tensor<B, 2>,
       ) -> Tensor<B, 1> {
           match rule {
               Rule::Predicate(name) => {
                   self.predicates[name].forward(state.clone())
               }
               Rule::And(left, right) => {
                   let left_val = self.evaluate_rule(left, state);
                   let right_val = self.evaluate_rule(right, state);
                   self.t_norm(&left_val, &right_val)
               }
               Rule::Or(left, right) => {
                   let left_val = self.evaluate_rule(left, state);
                   let right_val = self.evaluate_rule(right, state);
                   self.s_norm(&left_val, &right_val)
               }
               Rule::Not(inner) => {
                   let val = self.evaluate_rule(inner, state);
                   Tensor::ones_like(&val).sub(val)
               }
               Rule::Implies(antecedent, consequent) => {
                   // a → b = ¬a ∨ b
                   let not_a = self.evaluate_rule(
                       &Rule::Not(Box::new(*antecedent.clone())),
                       state,
                   );
                   let b = self.evaluate_rule(consequent, state);
                   self.s_norm(&not_a, &b)
               }
           }
       }
       
       fn t_norm(&self, a: &Tensor<B, 1>, b: &Tensor<B, 1>) -> Tensor<B, 1> {
           match self.t_norm {
               TNorm::Lukasiewicz => {
                   (a.clone().add(b.clone()).sub_scalar(1.0))
                       .clamp(0.0, 1.0)
               }
               TNorm::Product => a.clone().mul(b.clone()),
               TNorm::Godel => a.clone().min_pair(b.clone()),
           }
       }
       
       fn s_norm(&self, a: &Tensor<B, 1>, b: &Tensor<B, 1>) -> Tensor<B, 1> {
           // Dual of t-norm
           match self.t_norm {
               TNorm::Lukasiewicz => {
                   (a.clone().add(b.clone()))
                       .clamp(0.0, 1.0)
               }
               TNorm::Product => {
                   a.clone().add(b.clone())
                       .sub(a.clone().mul(b.clone()))
               }
               TNorm::Godel => a.clone().max_pair(b.clone()),
           }
       }
   }
   ```

2. **Compliance Rules**
   ```rust
   // crates/brain/prefrontal/src/rules.rs
   pub struct ComplianceChecker<B: Backend> {
       ltn: LTN<B>,
   }
   
   impl<B: Backend> ComplianceChecker<B> {
       pub fn check_ftmo_rules(
           &self,
           state: &MarketState<B>,
           proposed_action: &Action,
       ) -> ComplianceResult<B> {
           // FTMO rules:
           // 1. Max daily loss: 5%
           // 2. Max total loss: 10%
           // 3. No news trading 5 min before/after major events
           // 4. Position size limits
           
           let daily_loss_ok = self.ltn.evaluate_rule(
               &Rule::Predicate("daily_loss_below_5pct".to_string()),
               &state.to_tensor(),
           );
           
           let total_loss_ok = self.ltn.evaluate_rule(
               &Rule::Predicate("total_loss_below_10pct".to_string()),
               &state.to_tensor(),
           );
           
           let no_news_trading = self.ltn.evaluate_rule(
               &Rule::Not(Box::new(Rule::Predicate("near_news_event".to_string()))),
               &state.to_tensor(),
           );
           
           let position_size_ok = self.ltn.evaluate_rule(
               &Rule::Predicate("position_size_valid".to_string()),
               &state.to_tensor(),
           );
           
           // Combined rule: ALL conditions must be satisfied
           let compliance = self.ltn.t_norm(
               &daily_loss_ok,
               &self.ltn.t_norm(
                   &total_loss_ok,
                   &self.ltn.t_norm(&no_news_trading, &position_size_ok),
               ),
           );
           
           ComplianceResult {
               approved: compliance.clone().into_scalar() > 0.9,
               confidence: compliance,
               violations: vec![],  // TODO: Identify which rules failed
           }
       }
   }
   ```

**Testing:**
- ✅ LTN logic operations correctness
- ✅ Gradient flow through compliance loss
- ✅ Rule interpretation accuracy

---

#### **Week 8: Amygdala - Risk Management**

**Objectives:**
- Implement fear network and circuit breakers
- Real-time risk monitoring

**Deliverables:**

1. **Fear Network**
   ```rust
   // crates/brain/amygdala/src/fear.rs
   #[derive(Module, Debug)]
   pub struct FearNetwork<B: Backend> {
       threat_detector: MLP<B>,
       circuit_breaker: CircuitBreaker,
   }
   
   #[derive(Debug, Clone)]
   pub struct ThreatLevel {
       pub score: f64,          // [0, 1]
       pub category: ThreatCategory,
   }
   
   #[derive(Debug, Clone)]
   pub enum ThreatCategory {
       VolatilitySpike,
       DrawdownExcessive,
       LiquidityDry,
       FlashCrash,
       None,
   }
   
   impl<B: Backend> FearNetwork<B> {
       pub fn assess_threat(
           &mut self,
           state: &MarketState<B>,
       ) -> ThreatLevel {
           // Forward pass
           let threat_logits = self.threat_detector.forward(
               state.to_tensor()
           );
           
           let threat_score = threat_logits.sigmoid().into_scalar();
           
           // Categorize threat
           let category = if threat_score > 0.9 {
               self.detect_threat_category(state)
           } else {
               ThreatCategory::None
           };
           
           // Update circuit breaker
           if threat_score > self.circuit_breaker.threshold {
               self.circuit_breaker.trip();
           }
           
           ThreatLevel {
               score: threat_score,
               category,
           }
       }
       
       fn detect_threat_category(
           &self,
           state: &MarketState<B>,
       ) -> ThreatCategory {
           // Analyze state to determine threat type
           let volatility = state.compute_volatility();
           let drawdown = state.current_drawdown;
           let liquidity = state.orderbook_depth;
           
           if volatility > 3.0 {
               ThreatCategory::VolatilitySpike
           } else if drawdown > 0.08 {
               ThreatCategory::DrawdownExcessive
           } else if liquidity < 10000.0 {
               ThreatCategory::LiquidityDry
           } else {
               ThreatCategory::FlashCrash
           }
       }
   }
   ```

2. **Circuit Breaker**
   ```rust
   // crates/brain/amygdala/src/circuit_breaker.rs
   pub struct CircuitBreaker {
       threshold: f64,
       cooldown_period: Duration,
       state: CircuitState,
       last_trip_time: Option<Instant>,
   }
   
   #[derive(Debug, Clone, PartialEq)]
   pub enum CircuitState {
       Closed,   // Normal operation
       Open,     // Trading halted
       HalfOpen, // Testing if safe to resume
   }
   
   impl CircuitBreaker {
       pub fn trip(&mut self) {
           self.state = CircuitState::Open;
           self.last_trip_time = Some(Instant::now());
       }
       
       pub fn can_trade(&mut self) -> bool {
           match self.state {
               CircuitState::Closed => true,
               CircuitState::Open => {
                   // Check if cooldown period has elapsed
                   if let Some(trip_time) = self.last_trip_time {
                       if trip_time.elapsed() > self.cooldown_period {
                           self.state = CircuitState::HalfOpen;
                           true  // Allow test trade
                       } else {
                           false
                       }
                   } else {
                       false
                   }
               }
               CircuitState::HalfOpen => {
                   // Allow trading, will transition to Closed if successful
                   true
               }
           }
       }
       
       pub fn record_success(&mut self) {
           if self.state == CircuitState::HalfOpen {
               self.state = CircuitState::Closed;
           }
       }
   }
   ```

**Testing:**
- ✅ Threat detection on historical crashes
- ✅ Circuit breaker triggering logic
- ✅ False positive rate < 1%

---

#### **Week 9: Hypothalamus & Cerebellum - Capital Allocation & Execution**

**Objectives:**
- Implement position sizing (Kelly Criterion)
- Optimal execution (StaticVWAP)

**Deliverables:**

1. **Hypothalamus - Position Sizing**
   ```rust
   // crates/brain/hypothalamus/src/kelly.rs
   #[derive(Module, Debug)]
   pub struct KellyAllocator<B: Backend> {
       win_rate_estimator: MLP<B>,
       win_loss_ratio_estimator: MLP<B>,
       kelly_fraction: f64,  // Conservative multiplier (0.25 = quarter-Kelly)
   }
   
   impl<B: Backend> KellyAllocator<B> {
       pub fn compute_position_size(
           &self,
           state: &MarketState<B>,
           account_equity: f64,
       ) -> PositionSize {
           // Estimate win rate (p) and win/loss ratio (b)
           let p = self.win_rate_estimator.forward(state.to_tensor())
               .sigmoid()
               .into_scalar();
           
           let b = self.win_loss_ratio_estimator.forward(state.to_tensor())
               .relu()
               .into_scalar()
               .max(0.1);  // Ensure positive
           
           // Kelly formula: f* = (bp - q) / b
           // where q = 1 - p
           let q = 1.0 - p;
           let kelly_pct = ((b * p - q) / b).max(0.0).min(1.0);
           
           // Apply conservative fraction
           let position_pct = kelly_pct * self.kelly_fraction;
           
           PositionSize {
               fraction: position_pct,
               notional: account_equity * position_pct,
           }
       }
   }
   ```

2. **Cerebellum - Optimal Execution**
   ```rust
   // crates/brain/cerebellum/src/vwap.rs
   #[derive(Module, Debug)]
   pub struct StaticVWAP<B: Backend> {
       slice_network: MLP<B>,
       urgency_network: MLP<B>,
   }
   
   impl<B: Backend> StaticVWAP<B> {
       pub fn compute_slices(
           &self,
           total_quantity: f64,
           time_horizon: usize,
           state: &MarketState<B>,
       ) -> Vec<OrderSlice> {
           let urgency = self.urgency_network.forward(state.to_tensor())
               .sigmoid()
               .into_scalar();
           
           // Generate slice sizes using learned policy
           let mut slices = Vec::new();
           let mut remaining = total_quantity;
           
           for t in 0..time_horizon {
               let slice_pct = self.slice_network.forward(
                   Tensor::from_floats([t as f32 / time_horizon as f32, urgency as f32])
               ).sigmoid().into_scalar();
               
               let slice_qty = remaining * slice_pct;
               slices.push(OrderSlice {
                   quantity: slice_qty,
                   time_index: t,
                   limit_price: None,  // Market orders for now
               });
               
               remaining -= slice_qty;
           }
           
           slices
       }
   }
   ```

**Testing:**
- ✅ Kelly Criterion validation on historical data
- ✅ VWAP execution cost vs. benchmark
- ✅ Latency < 5ms combined

---

### **Phase 4: Integration & Production (Weeks 10-12)**

#### **Week 10: System Integration & Forward/Backward Services**

**Objectives:**
- Integrate all brain regions into cohesive system
- Implement Forward (Wake) and Backward (Sleep) services
- Setup shared memory communication

**Deliverables:**

1. **Forward Service (Rust - Low Latency)**
   ```rust
   // crates/integration/forward-service/src/main.rs
   use tokio::runtime::Runtime;
   use shared_memory::ShmemConf;
   
   pub struct ForwardService<B: Backend> {
       visual_cortex: VisualCortex<B>,
       thalamus: Thalamus<B>,
       basal_ganglia: BasalGanglia<B>,
       prefrontal: PrefrontalCortex<B>,
       amygdala: Amygdala<B>,
       hypothalamus: Hypothalamus<B>,
       cerebellum: Cerebellum<B>,
       device: B::Device,
   }
   
   impl<B: Backend> ForwardService<B> {
       pub async fn inference_loop(&mut self) -> Result<(), Error> {
           loop {
               // 1. Receive market data
               let market_data = self.receive_market_data().await?;
               
               // 2. Visual processing
               let visual_embedding = self.visual_cortex.forward(market_data.prices);
               
               // 3. Multi-modal fusion
               let state = self.thalamus.forward(MarketState {
                   visual_embedding,
                   orderbook_features: market_data.orderbook,
                   sentiment_features: market_data.sentiment,
               });
               
               // 4. Risk assessment (Amygdala)
               let threat = self.amygdala.assess_threat(&state);
               if threat.score > 0.9 {
                   warn!("High threat detected: {:?}", threat.category);
                   continue;  // Skip trading
               }
               
               // 5. Decision making (Basal Ganglia)
               let (goal, action) = self.basal_ganglia.forward(&state);
               
               // 6. Compliance check (Prefrontal)
               let compliance = self.prefrontal.check_compliance(&state, &action);
               if !compliance.approved {
                   warn!("Compliance violation: {:?}", compliance.violations);
                   continue;
               }
               
               // 7. Position sizing (Hypothalamus)
               let position_size = self.hypothalamus.compute_position_size(
                   &state,
                   self.get_account_equity(),
               );
               
               // 8. Execution (Cerebellum)
               let slices = self.cerebellum.compute_slices(
                   position_size.notional,
                   action.horizon,
                   &state,
               );
               
               // 9. Execute orders
               for slice in slices {
                   self.execute_order(slice).await?;
               }
               
               // 10. Store experience for backward service
               self.store_experience(state, action, reward).await?;
               
               tokio::time::sleep(Duration::from_millis(100)).await;
           }
       }
   }
   ```

2. **Backward Service (Rust - Training)**
   ```rust
   // crates/integration/backward-service/src/main.rs
   pub struct BackwardService<B: AutodiffBackend> {
       training_orchestrator: TrainingOrchestrator<B>,
       model_registry: ModelRegistry,
       hippocampus: Hippocampus,
       device: B::Device,
   }
   
   impl<B: AutodiffBackend> BackwardService<B> {
       pub async fn training_loop(&mut self) -> Result<(), Error> {
           loop {
               // 1. Sleep period (every 4 hours)
               tokio::time::sleep(Duration::from_secs(4 * 3600)).await;
               
               info!("Starting training cycle...");
               
               // 2. Sample experiences from hippocampus
               let (experiences, weights) = self.hippocampus.replay_buffer.sample(1024);
               
               // 3. Train all brain regions
               let metrics = self.training_orchestrator.train_epoch(experiences).await?;
               
               // 4. Evaluate new models
               let validation_metrics = self.evaluate_models().await?;
               
               // 5. Model selection
               for region in BrainRegion::all() {
                   let best_model = self.model_registry.select_best_model(
                       region,
                       ModelSelectionMetric::Composite(vec![
                           (0.4, ModelSelectionMetric::SharpeRatio),
                           (0.3, ModelSelectionMetric::ValidationLoss),
                           (0.3, ModelSelectionMetric::WinRate),
                       ]),
                   )?;
                   
                   info!("Selected model for {:?}: v{}", region, best_model.version);
               }
               
               // 6. Deploy new models to forward service
               self.deploy_models().await?;
               
               // 7. Memory consolidation
               self.hippocampus.consolidate();
               
               info!("Training cycle complete. Metrics: {:?}", metrics);
           }
       }
   }
   ```

3. **Shared Memory Bridge**
   ```rust
   // crates/integration/bridge/src/shm.rs
   use shared_memory::{Shmem, ShmemConf};
   use arrow::ipc::{reader::StreamReader, writer::StreamWriter};
   
   pub struct SharedMemoryBridge {
       shm: Shmem,
   }
   
   impl SharedMemoryBridge {
       pub fn new(size_mb: usize) -> Result<Self, Error> {
           let shm = ShmemConf::new()
               .size(size_mb * 1024 * 1024)
               .create()?;
           
           Ok(Self { shm })
       }
       
       pub fn write_tensor<B: Backend>(
           &mut self,
           tensor: &Tensor<B, 2>,
       ) -> Result<(), Error> {
           // Convert to Arrow RecordBatch
           let data = tensor.to_data();
           // Write to shared memory
           // ... (Arrow IPC format)
       }
       
       pub fn read_tensor<B: Backend>(&self) -> Result<Tensor<B, 2>, Error> {
           // Read from shared memory
           // Convert Arrow → Tensor
           // ... (implementation)
       }
   }
   ```

**Testing:**
- ✅ End-to-end inference latency < 40ms
- ✅ Forward/Backward communication
- ✅ Model hot-swapping without downtime

---

#### **Week 11: CUDA Training Pipeline & Model Versioning**

**Objectives:**
- Optimize training with CUDA
- Implement automated model versioning and deployment
- Setup TensorBoard metrics

**Deliverables:**

1. **Training Orchestrator**
   ```rust
   // crates/training/orchestrator/src/lib.rs
   pub struct TrainingOrchestrator<B: AutodiffBackend> {
       regions: HashMap<BrainRegion, Box<dyn TrainableRegion<B>>>,
       optimizers: HashMap<BrainRegion, Adam<B>>,
       schedulers: HashMap<BrainRegion, CosineAnnealingLR>,
       metrics_writer: MetricsWriter,
   }
   
   impl<B: AutodiffBackend> TrainingOrchestrator<B> {
       pub async fn train_epoch(
           &mut self,
           experiences: Vec<Experience>,
       ) -> Result<TrainingMetrics, Error> {
           let mut metrics = TrainingMetrics::default();
           
           for (region, model) in &mut self.regions {
               info!("Training {:?}...", region);
               
               // Train region-specific model
               let region_metrics = model.train_batch(
                   &experiences,
                   self.optimizers.get_mut(region).unwrap(),
               )?;
               
               // Update learning rate
               self.schedulers.get_mut(region).unwrap().step();
               
               // Log metrics
               self.metrics_writer.log_scalar(
                   format!("{:?}/loss", region),
                   region_metrics.loss,
               );
               
               metrics.add_region_metrics(region.clone(), region_metrics);
               
               // Save checkpoint
               if region_metrics.loss < model.best_loss {
                   self.save_checkpoint(region, model)?;
               }
           }
           
           Ok(metrics)
       }
       
       fn save_checkpoint(
           &self,
           region: &BrainRegion,
           model: &dyn TrainableRegion<B>,
       ) -> Result<(), Error> {
           let version = self.get_next_version(region);
           let path = format!("checkpoints/{:?}/v{}.bin", region, version);
           
           // Save model weights
           model.save_weights(&path)?;
           
           // Register in model registry
           self.model_registry.register_model(
               region.clone(),
               ModelMetadata {
                   model_id: format!("{:?}_v{}", region, version),
                   brain_region: region.clone(),
                   version,
                   timestamp: chrono::Utc::now().timestamp(),
                   metrics: model.get_metrics(),
                   config: model.get_config(),
               },
               PathBuf::from(&path),
           )?;
           
           Ok(())
       }
   }
   ```

2. **CUDA Optimization**
   ```rust
   // crates/training/cuda/src/optimizer.rs
   #[cfg(feature = "cuda")]
   pub fn optimize_for_cuda<B: AutodiffBackend>(
       model: &mut impl Module<B>,
   ) {
       // Enable TF32 for matrix multiplications
       unsafe {
           burn_cuda::enable_tf32();
       }
       
       // Use cudnn for convolutions
       // Enable automatic mixed precision (AMP)
       // ... (CUDA-specific optimizations)
   }
   ```

3. **Metrics & TensorBoard**
   ```rust
   // crates/training/metrics/src/tensorboard.rs
   use tensorboard_rs::SummaryWriter;
   
   pub struct MetricsWriter {
       writer: SummaryWriter,
       step: usize,
   }
   
   impl MetricsWriter {
       pub fn log_scalar(&mut self, tag: &str, value: f64) {
           self.writer.add_scalar(tag, value as f32, self.step as i64);
           self.step += 1;
       }
       
       pub fn log_histogram(&mut self, tag: &str, values: &[f64]) {
           self.writer.add_histogram(tag, values, self.step as i64);
       }
       
       pub fn log_image(&mut self, tag: &str, image: &Tensor<B, 3>) {
           // Log GAF images, attention maps, etc.
           self.writer.add_image(tag, image, self.step as i64);
       }
   }
   ```

**Testing:**
- ✅ CUDA training speedup (10x+ vs CPU)
- ✅ Model versioning workflow
- ✅ Metrics visualization in TensorBoard

---

#### **Week 12: Testing, Documentation & Deployment**

**Objectives:**
- Comprehensive testing suite
- Production deployment
- Complete documentation

**Deliverables:**

1. **Integration Tests**
   ```rust
   // tests/integration/brain_regions.rs
   #[tokio::test]
   async fn test_end_to_end_inference() {
       let device = CudaDevice::default();
       let forward_service = ForwardService::new(device);
       
       // Simulate market data
       let market_data = generate_test_market_data();
       
       // Run inference
       let start = Instant::now();
       let decision = forward_service.infer(market_data).await.unwrap();
       let latency = start.elapsed();
       
       // Verify latency
       assert!(latency.as_millis() < 40, "Inference too slow: {:?}", latency);
       
       // Verify decision is valid
       assert!(decision.action.is_valid());
       assert!(decision.compliance_approved);
   }
   
   #[test]
   fn test_model_selection() {
       let mut registry = ModelRegistry::new(PathBuf::from("test_models"));
       
       // Register multiple versions
       for version in 1..=5 {
           registry.register_model(
               BrainRegion::VisualCortex,
               ModelMetadata {
                   version,
                   metrics: ModelMetrics {
                       sharpe_ratio: Some(1.0 + version as f64 * 0.1),
                       ..Default::default()
                   },
                   ..Default::default()
               },
               PathBuf::from(format!("v{}.bin", version)),
           ).unwrap();
       }
       
       // Select best model
       let best = registry.select_best_model(
           BrainRegion::VisualCortex,
           ModelSelectionMetric::SharpeRatio,
       ).unwrap();
       
       assert_eq!(best.version, 5);
   }
   ```

2. **Docker Compose Setup**
   ```yaml
   # docker-compose.janus.yml
   version: '3.8'
   
   services:
     forward-service:
       build:
         context: .
         dockerfile: Dockerfile.forward
       runtime: nvidia
       environment:
         - CUDA_VISIBLE_DEVICES=0
         - RUST_LOG=info
       volumes:
         - ./models:/app/models
         - /dev/shm:/dev/shm
       ports:
         - "8080:8080"
       networks:
         - janus-net
   
     backward-service:
       build:
         context: .
         dockerfile: Dockerfile.backward
       runtime: nvidia
       environment:
         - CUDA_VISIBLE_DEVICES=0
         - RUST_LOG=info
       volumes:
         - ./models:/app/models
         - ./checkpoints:/app/checkpoints
         - /dev/shm:/dev/shm
       networks:
         - janus-net
   
     tensorboard:
       image: tensorflow/tensorflow:latest
       command: tensorboard --logdir=/logs --bind_all
       ports:
         - "6006:6006"
       volumes:
         - ./logs:/logs
       networks:
         - janus-net
   
   networks:
     janus-net:
       driver: bridge
   ```

3. **Documentation**
   - API documentation (cargo doc)
   - Architecture diagrams
   - Training playbook
   - Deployment guide
   - Troubleshooting guide

**Testing:**
- ✅ All integration tests passing
- ✅ Load testing (1000+ inferences/sec)
- ✅ Chaos engineering (service failures)
- ✅ Production smoke tests

---

## Summary & Timeline

### Weekly Milestones

| Week | Focus | Key Deliverables | Brain Regions |
|------|-------|------------------|---------------|
| 1 | Foundation | Model registry, CUDA setup, crate structure | - |
| 2 | Vision | DiffGAF migration to Burn | Visual Cortex |
| 3 | Vision | ViViT implementation | Visual Cortex |
| 4 | Fusion | Multi-modal attention | Thalamus |
| 5 | Decision | Hierarchical RL (PPO) | Basal Ganglia |
| 6 | Memory | Experience replay, consolidation | Hippocampus |
| 7 | Safety | LTN compliance layer | Prefrontal Cortex |
| 8 | Risk | Fear network, circuit breakers | Amygdala |
| 9 | Execution | Position sizing, VWAP slicing | Hypothalamus, Cerebellum |
| 10 | Integration | Forward/Backward services | All regions |
| 11 | Training | CUDA optimization, versioning | All regions |
| 12 | Production | Testing, deployment, docs | All regions |

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Inference Latency | < 40ms | Full brain forward pass |
| Training Time | 10-300s | Per epoch, CUDA |
| Model Selection | Automated | Based on Sharpe/Win Rate |
| Sharpe Ratio | > 2.0 | On validation set |
| Win Rate | > 55% | Minimum acceptable |
| Max Drawdown | < 10% | Circuit breaker threshold |

### Model Management

```
models/
├── visual-cortex/
│   ├── v1.bin
│   ├── v1.json (metadata)
│   ├── v2.bin
│   ├── v2.json
│   └── active -> v2.bin
├── thalamus/
│   └── ...
├── basal-ganglia/
│   └── ...
└── ...
```

**Model Lifecycle:**
1. Train new version in Backward service
2. Evaluate on validation set
3. Compare metrics with current version
4. If better, register in model registry
5. Hot-swap in Forward service (zero downtime)
6. Monitor performance for 24h
7. Rollback if metrics degrade

### Continuous Improvement Loop

```
┌─────────────────────────────────────────────┐
│         FORWARD SERVICE (Wake)              │
│  - Inference (<40ms)                        │
│  - Execute trades                           │
│  - Store experiences                        │
└──────────────┬──────────────────────────────┘
               │
               │ Experiences
               ▼
┌─────────────────────────────────────────────┐
│         HIPPOCAMPUS (Memory)                │
│  - Prioritized replay buffer                │
│  - Memory consolidation                     │
└──────────────┬──────────────────────────────┘
               │
               │ Sample batch
               ▼
┌─────────────────────────────────────────────┐
│         BACKWARD SERVICE (Sleep)            │
│  - Train all brain regions                  │
│  - Evaluate new models                      │
│  - Model selection                          │
│  - Deploy if better                         │
└──────────────┬──────────────────────────────┘
               │
               │ New models
               ▼
┌─────────────────────────────────────────────┐
│         MODEL REGISTRY                      │
│  - Version management                       │
│  - A/B testing                              │
│  - Rollback capability                      │
└──────────────┬──────────────────────────────┘
               │
               │ Deploy best
               ▼
         (Back to Forward Service)
```

---

## Appendix: Burn Best Practices

### 1. Backend Selection

```rust
// Development (CPU)
type Backend = burn::backend::NdArray;

// Training (CUDA)
#[cfg(feature = "cuda")]
type Backend = burn::backend::Autodiff<burn::backend::Cuda>;

// Inference (ONNX)
type InferenceBackend = burn_onnx::Backend;
```

### 2. Model Serialization

```rust
// Save model
model.save_file("model.bin", &CompactRecorder::new())?;

// Load model
let model = VisualCortex::load_file("model.bin", &CompactRecorder::new(), &device)?;
```

### 3. ONNX Export

```rust
// Export to ONNX for production inference
model.export_onnx("model.onnx")?;

// Load in ONNX Runtime (C++ or Rust)
let session = ort::Session::builder()?.with_model_from_file("model.onnx")?;
```

### 4. Gradient Checkpointing

```rust
// For memory-efficient training of large models
#[derive(Module, Debug)]
struct LargeModel<B: Backend> {
    #[checkpoint]  // Recompute activations during backward pass
    encoder: LargeEncoder<B>,
    decoder: Decoder<B>,
}
```

### 5. Mixed Precision Training

```rust
// Enable AMP for faster training
let config = TrainingConfig::new()
    .with_mixed_precision(true)
    .with_grad_scaler(GradScaler::new());
```

---

## Conclusion

This 12-week plan provides a complete roadmap for implementing the JANUS neuromorphic trading system using Rust and the Burn ML framework. Key success factors:

1. **Modular Architecture** - Each brain region is an independent crate
2. **CUDA Acceleration** - 10x+ training speedup
3. **Automated Model Management** - Continuous improvement without manual intervention
4. **Production Ready** - <40ms inference latency with hot-swapping
5. **Comprehensive Testing** - Integration, load, and chaos testing

**Next Steps:**
1. Start with Week 1 (foundation and model registry)
2. Follow the plan sequentially, testing at each milestone
3. Adjust timeline based on team size and resources
4. Maintain documentation as you build
5. Set up monitoring and alerting from Day 1

**Success Metrics (by Week 12):**
- ✅ All 9 brain regions implemented
- ✅ End-to-end inference < 40ms
- ✅ CUDA training pipeline operational
- ✅ Automated model selection working
- ✅ Production deployment successful
- ✅ Sharpe ratio > 2.0 on validation set

Good luck building JANUS! 🚀