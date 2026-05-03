# Project JANUS: Comprehensive Glossary

**Document Version**: 1.0  
**Date**: January 2025  
**Last Updated**: 2025-01-XX

---

## Table of Contents

1. [Acronyms & Abbreviations](#acronyms--abbreviations)
2. [Machine Learning Terms](#machine-learning-terms)
3. [Neuroscience Terms](#neuroscience-terms)
4. [Finance & Trading Terms](#finance--trading-terms)
5. [Mathematical Notation](#mathematical-notation)
6. [System Components](#system-components)

---

## Acronyms & Abbreviations

### A-G

**AI** - Artificial Intelligence  
General term for machine systems that exhibit intelligent behavior.

**API** - Application Programming Interface  
Interface for software components to communicate.

**CNN** - Convolutional Neural Network  
Deep learning architecture specialized for grid-like data (images).

**CPU** - Central Processing Unit  
Main processor for general computation.

**DL** - Deep Learning  
Machine learning using multi-layer neural networks.

**DQN** - Deep Q-Network  
Reinforcement learning algorithm combining Q-learning with deep neural networks. *Reference: Mnih et al. (2015)*

**FIFO** - First In, First Out  
Queue data structure where earliest items are processed first.

**GAF** - Gramian Angular Field  
Transformation method converting 1D time series to 2D images via polar coordinates. *Reference: Wang & Oates (2015)*

**GADF** - Gramian Angular Difference Field  
GAF variant using angular difference: $\mathbf{G}_{ij} = \sin(\phi_i - \phi_j)$. Highlights temporal flux.

**GASF** - Gramian Angular Summation Field  
GAF variant using angular summation: $\mathbf{G}_{ij} = \cos(\phi_i + \phi_j)$. Highlights static correlations.

**GPU** - Graphics Processing Unit  
Specialized processor for parallel computation, essential for deep learning training.

---

### H-M

**HFT** - High-Frequency Trading  
Algorithmic trading characterized by high speed, high turnover, and short holding periods.

**HNSW** - Hierarchical Navigable Small World  
Graph-based algorithm for approximate nearest neighbor search. Used in Qdrant.

**LLM** - Large Language Model  
Neural network trained on massive text corpora (e.g., GPT, BERT).

**LOB** - Limit Order Book  
Real-time record of all buy/sell orders at different price levels on an exchange.

**LTN** - Logic Tensor Network  
Neurosymbolic framework integrating first-order logic with neural networks using fuzzy logic. *Reference: Badreddine et al. (2022)*

**LSTM** - Long Short-Term Memory  
Recurrent neural network architecture designed to handle long-term dependencies.

**M3T** - Multi-Timescale Memory Transfer  
JANUS-specific term for hierarchical memory consolidation across episodic, working, and long-term stores.

**MiFID II** - Markets in Financial Instruments Directive II  
European Union regulation governing algorithmic trading transparency and risk controls.

**MLP** - Multilayer Perceptron  
Fully connected feedforward neural network with multiple hidden layers.

---

### N-S

**OpAL** - Opponent Actor Learning  
Biologically-inspired RL model with separate "Go" (Direct) and "No-Go" (Indirect) pathways. *Reference: Collins & Frank (2014)*

**ONNX** - Open Neural Network Exchange  
Standard format for representing neural network models, enabling cross-framework deployment.

**PCA** - Principal Component Analysis  
Linear dimensionality reduction technique finding orthogonal axes of maximum variance.

**PER** - Prioritized Experience Replay  
RL technique sampling experiences proportional to TD-error magnitude. *Reference: Schaul et al. (2015)*

**RL** - Reinforcement Learning  
Machine learning paradigm where agents learn by trial and error through rewards/penalties.

**ReLU** - Rectified Linear Unit  
Activation function: $f(x) = \max(0, x)$. Most common in modern deep learning.

**RPE** - Reward Prediction Error  
Difference between expected and received reward: $\delta_t = r_t + \gamma V(s_{t+1}) - V(s_t)$. Biological analog: dopamine signaling.

**RNN** - Recurrent Neural Network  
Neural network with cycles, allowing processing of sequential data.

**SMA** - Simple Moving Average  
Technical indicator: average of last $N$ prices. Used in momentum strategies.

**SPN** - Striatal Projection Neuron  
Neurons in the basal ganglia striatum. D1-type (direct pathway) vs D2-type (indirect pathway).

**SWR** - Sharp-Wave Ripple  
High-frequency oscillatory pattern in hippocampus during sleep, associated with memory replay. *Reference: Buzsáki (1989)*

---

### T-Z

**TD** - Temporal Difference  
Class of RL algorithms learning from bootstrapped estimates. Foundation of Q-learning.

**TD2Q** - Twin Delayed Q-Learning  
Variant of Q-learning with separate benefit (G) and cost (N) estimators. *Reference: Mikhael & Bogacz (2016)*

**t-SNE** - t-Distributed Stochastic Neighbor Embedding  
Nonlinear dimensionality reduction for visualization. Alternative to UMAP.

**UMAP** - Uniform Manifold Approximation and Projection  
Dimensionality reduction algorithm preserving both local and global structure. *Reference: McInnes et al. (2018)*

**ViT** - Vision Transformer  
Transformer architecture applied to image classification via patch embeddings. *Reference: Dosovitskiy et al. (2020)*

**ViViT** - Video Vision Transformer  
Extension of ViT to video data with spatiotemporal attention. *Reference: Arnab et al. (2021)*

**VWAP** - Volume-Weighted Average Price  
Execution benchmark: average price weighted by volume traded at each price level.

---

## Machine Learning Terms

### Ablation Study
Systematic removal of model components to measure individual contributions to performance. Essential for validating architectural choices.

### Activation Function
Nonlinear function applied to neuron outputs. Common types: ReLU, Sigmoid, Tanh, GELU.

### Attention Mechanism
Neural network component that learns to focus on relevant parts of input. Core to Transformer architecture.  
**Formula**: $\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$

### Backpropagation
Algorithm for computing gradients in neural networks via chain rule. Enables gradient descent optimization.

### Batch Normalization
Technique normalizing layer inputs to stabilize training. *Reference: Ioffe & Szegedy (2015)*

### Catastrophic Forgetting
Phenomenon where neural networks lose previously learned knowledge when trained on new tasks. Motivates continual learning approaches.

### Cross-Entropy Loss
Loss function for classification:  
$\mathcal{L} = -\sum_{i} y_i \log(\hat{y}_i)$  
Standard for training neural classifiers.

### Embedding
Dense vector representation of discrete entities (words, symbols). Maps high-dimensional sparse space to low-dimensional dense space.

### Epoch
One complete pass through the entire training dataset.

### Factorized Attention
Decomposition of full attention into spatial and temporal components to reduce computational complexity.  
**JANUS Usage**: ViViT processes frames spatially first, then temporally.

### Fine-Tuning
Transfer learning approach where pre-trained model is further trained on task-specific data.

### Gradient Descent
Optimization algorithm iteratively moving parameters in direction of steepest loss decrease:  
$\theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}$

### Grounding (in LTN)
Process of mapping symbolic logic terms (predicates, constants, variables) to neural network tensors.

### Hyperparameter
Configuration value set before training (e.g., learning rate, batch size). Distinguished from learned parameters (weights).

### Inference
Process of using trained model to make predictions on new data (forward pass without training).

### Layer Normalization
Normalization across features within a single sample. Preferred over batch norm in Transformers. *Reference: Ba et al. (2016)*

### Overfitting
Model learning training data too well, including noise, leading to poor generalization.

### Patch Embedding
Division of image into fixed-size patches, each linearly projected to a vector. Used in ViT/ViViT.

### Residual Connection
Shortcut connection adding input directly to layer output: $y = f(x) + x$. Enables training very deep networks. *Reference: He et al. (2016)*

### Softmax
Function converting logits to probability distribution:  
$\text{softmax}(z_i) = \frac{e^{z_i}}{\sum_j e^{z_j}}$

### Tensorization
Conversion of symbolic logic expressions into differentiable tensor operations (LTN concept).

### Token
Discrete unit of input to Transformer models. Can be word, subword, image patch, or video tubelet.

### Transfer Learning
Using knowledge from pre-trained model on related task to improve learning on target task.

### Tubelet
3D patch extracted from video (spatial dimensions + time). Extends 2D patch concept to video domain.

### Vanishing Gradient
Problem where gradients become extremely small in deep networks, preventing learning. Addressed by residual connections and better activations.

---

## Neuroscience Terms

### Amygdala
Brain region processing emotions, especially fear and threat detection. **JANUS Analog**: Anomaly detection and risk override system.

### Basal Ganglia
Subcortical brain structures involved in action selection and habit learning. Contains striatum, substantia nigra, globus pallidus.  
**JANUS Analog**: Decision engine with OpAL architecture.

### Cerebellum
Brain region coordinating motor control and fine-tuning movements. **JANUS Analog**: Optimal execution module (StaticVWAP).

### Circadian Rhythm
~24-hour biological cycle regulating sleep/wake states. **JANUS Analog**: Forward (wake) and Backward (sleep) service separation.

### Dopamine
Neurotransmitter signaling reward prediction errors. Critical for reinforcement learning in brain.  
**JANUS Analog**: RPE signal modulating synaptic plasticity in OpAL.

### Hippocampus
Brain region essential for episodic memory formation and spatial navigation. Contains CA3 region with recurrent connections.  
**JANUS Analog**: Fast-learning episodic buffer with prioritized replay.

### Homeostasis
Biological regulation maintaining stable internal conditions despite external changes.  
**JANUS Analog**: Hypothalamus module maintaining target capital allocation.

### Hypothalamus
Brain region regulating fundamental drives (hunger, thirst) and maintaining homeostasis.  
**JANUS Analog**: Capital allocation and position sizing (Kelly Criterion).

### Neocortex
Outer layer of mammalian brain responsible for higher-order cognition, pattern recognition, and memory storage.  
**JANUS Analog**: Vector database (Qdrant) storing consolidated schemas.

### Neuromorphic
Engineering approach mimicking biological neural architectures and principles rather than abstracting them away.

### Prefrontal Cortex (PFC)
Brain region responsible for executive functions: planning, logic, impulse control.  
**JANUS Analog**: Logic Tensor Network enforcing trading rules and compliance.

### Substantia Nigra pars compacta (SNc)
Dopamine-producing region in midbrain. Degenerates in Parkinson's disease.  
**JANUS Analog**: RPE computation module.

### Synapse
Junction between neurons where information is transmitted. Synaptic weights strengthen/weaken with learning.  
**JANUS Analog**: Neural network weights updated via gradient descent.

### Thalamus
Brain region acting as relay station and attention gatekeeper for sensory information.  
**JANUS Analog**: Multimodal fusion hub with gated cross-attention.

---

## Finance & Trading Terms

### Alpha (α)
Excess return of investment relative to benchmark. Holy grail of quantitative trading.

### Arbitrage
Simultaneous purchase and sale of asset to profit from price differences. Risk-free profit in efficient markets (rare).

### Ask/Offer
Price at which sellers are willing to sell. Counterpart to bid.

### Backtest
Simulation of trading strategy on historical data to estimate performance. **Critical Issue**: Lookahead bias.

### Basis Point (bp)
One hundredth of a percent (0.01%). Used to describe small interest rate or return changes.

### Bid
Price at which buyers are willing to buy. Difference between bid and ask is the spread.

### Circuit Breaker
Automatic trading halt triggered by extreme price movements. Regulatory safety mechanism.

### Drawdown
Peak-to-trough decline in portfolio value. Maximum drawdown is key risk metric.

### Fill
Execution of an order. Partial fill: only some of requested quantity executed.

### Latency
Time delay between event occurrence and system response. Critical in HFT (microsecond scale).

### Liquidity
Ease of buying/selling asset without moving price. High liquidity = tight spreads, deep order books.

### Long Position
Owning an asset with expectation of price increase. Opposite of short.

### Market Impact
Price movement caused by large order execution. Almgren-Chriss framework models this.

### Market Order
Order executed immediately at best available price. No price guarantee, but guaranteed fill.

### Mark-to-Market
Valuation of positions at current market prices. Daily profit/loss calculation.

### Order Book
See **LOB** (Limit Order Book).

### Position Sizing
Determination of capital allocated to each trade. Kelly Criterion provides optimal sizing under assumptions.

### Proprietary Trading (Prop Trading)
Trading firm's own capital rather than client money. Subject to specific regulations.

### Quantitative Trading (Quant)
Algorithmic trading based on mathematical models and statistical analysis.

### Sharpe Ratio
Risk-adjusted return metric:  
$\text{Sharpe} = \frac{\mathbb{E}[R - R_f]}{\sigma_R}$  
where $R$ is strategy return, $R_f$ is risk-free rate, $\sigma_R$ is volatility.

### Short Position
Selling borrowed asset with expectation of price decrease, then buying back cheaper.

### Slippage
Difference between expected trade price and actual execution price. Major cost in live trading.

### Sortino Ratio
Modified Sharpe ratio penalizing only downside volatility:  
$\text{Sortino} = \frac{\mathbb{E}[R - R_f]}{\sigma_{\text{downside}}}$

### Spread
Difference between bid and ask prices. Compensation for market makers providing liquidity.

### Wash Sale
Tax regulation prohibiting claiming loss on security sold and repurchased within 30 days.  
**JANUS**: Enforced via LTN constraint.

### Win Rate
Percentage of profitable trades. Can be misleading without considering average win/loss size.

---

## Mathematical Notation

### Scalars, Vectors, Matrices

| Symbol | Meaning | Example |
|--------|---------|---------|
| $x, y, z$ | Scalars (lowercase italic) | $x = 3.14$ |
| $\mathbf{x}, \mathbf{v}$ | Vectors (lowercase bold) | $\mathbf{x} \in \mathbb{R}^d$ |
| $\mathbf{X}, \mathbf{W}$ | Matrices (uppercase bold) | $\mathbf{W} \in \mathbb{R}^{m \times n}$ |
| $\mathcal{X}, \mathcal{D}$ | Sets (calligraphic) | $\mathcal{D} = \{(s_i, a_i, r_i)\}$ |

### Common Operations

| Notation | Meaning |
|----------|---------|
| $\mathbf{x}^T$ | Transpose of vector/matrix |
| $\mathbf{x} \odot \mathbf{y}$ | Element-wise (Hadamard) product |
| $\langle \mathbf{x}, \mathbf{y} \rangle$ | Inner product / dot product |
| $\|\mathbf{x}\|_2$ | Euclidean (L2) norm |
| $\nabla_\theta f$ | Gradient of $f$ with respect to $\theta$ |
| $\mathbb{E}_{x \sim p}[f(x)]$ | Expectation of $f(x)$ under distribution $p$ |
| $\arg\max_x f(x)$ | Value of $x$ maximizing $f$ |

### Logic Notation (LTN)

| Symbol | Meaning | Łukasiewicz Implementation |
|--------|---------|---------------------------|
| $\land$ | Logical AND | $u \land v = \max(0, u + v - 1)$ |
| $\lor$ | Logical OR | $u \lor v = \min(1, u + v)$ |
| $\neg$ | Logical NOT | $\neg u = 1 - u$ |
| $\Rightarrow$ | Implication | $u \Rightarrow v = \min(1, 1 - u + v)$ |
| $\forall x$ | Universal quantifier | $\min_{x \in D} P(x)$ or smooth aggregation |
| $\exists x$ | Existential quantifier | $\max_{x \in D} P(x)$ or smooth aggregation |

### Greek Letters (Common Usage)

| Symbol | Typical Meaning in JANUS |
|--------|-------------------------|
| $\alpha$ | Learning rate; trading signal strength |
| $\beta$ | Learnable bias in normalization |
| $\gamma$ | Discount factor in RL; learnable scale |
| $\delta$ | Reward prediction error (RPE) |
| $\epsilon$ | Exploration rate (ε-greedy); small constant |
| $\eta$ | Learning rate (alternative to α) |
| $\theta$ | Network parameters (weights) |
| $\lambda$ | Regularization coefficient |
| $\mu$ | Mean |
| $\sigma$ | Standard deviation |
| $\Sigma$ | Covariance matrix |
| $\phi$ | Polar angle in GAF transformation |
| $\tau$ | Temperature parameter; time constant |

---

## System Components

### Backward Service (Janus Consivius)
"Sleep state" service running memory consolidation, prioritized replay, and model refinement. Operates on Rayon (parallel threads).

### Qdrant
Open-source vector database using HNSW indexing. Stores neocortical schemas in JANUS.

### Episodic Buffer
Ring buffer (circular queue) storing recent experiences $(s, a, r, s')$ for immediate replay. Analog of hippocampal CA3 region.

### Forward Service (Janus Bifrons)
"Wake state" service executing real-time trading decisions. Operates on Tokio (async runtime) with <10ms latency target.

### Fusion Hub
See **Thalamus**. Gated cross-attention mechanism combining GAF, temporal, and sentiment modalities.

### Gating Mechanism
Neural network component controlling information flow. Used in LSTM, GRU, and JANUS recall-gated consolidation.

### Glass Box Architecture
System designed for interpretability and explainability. Contrasts with "black box" opaque models.

### Grounding Graph ($\mathcal{G}$)
Bipartite graph in LTN mapping symbolic constants/predicates to neural network tensors.

### Hot Reload
Runtime replacement of model weights without service restart. Enables continuous learning without downtime.

### Kelly Criterion
Optimal position sizing formula maximizing long-term growth:  
$f^* = \frac{p \cdot b - (1-p)}{b}$  
where $p$ = win probability, $b$ = win/loss ratio.

### Kill Switch
Emergency mechanism immediately halting all trading activity. Triggered by Amygdala on extreme anomalies.

### Learnable Normalization
GAF preprocessing with trainable affine parameters $\gamma, \beta$ instead of fixed min-max scaling.

### Lookahead Bias
Backtest error using information not available at decision time (e.g., future prices). Invalidates results.

### Multimodal Fusion
Integration of multiple input modalities (visual GAF, temporal price, textual sentiment) into unified representation.

### Polar Embedding
GAF transformation step mapping normalized values to polar angles: $\phi_t = \arccos(\tilde{x}_t)$.

### Recall-Gated Consolidation
Memory transfer mechanism requiring similarity threshold between new experience and existing schema before updating neocortex.

### Regime Shift
Fundamental change in market statistical properties (volatility, correlation structure). Major challenge for trading systems.

### Schema
Abstract pattern/template in long-term memory (neocortex). Represents generalized market state.

### Semantic Loss
Loss function enforcing logical constraints via LTN. Combines prediction loss and rule satisfaction.

### Spatiotemporal Manifold
High-dimensional representation encoding both spatial (price patterns) and temporal (sequence) structure.

### StaticVWAP
Optimal execution algorithm partitioning large order across time to minimize market impact. Based on Almgren-Chriss framework.

### T-norm
Triangular norm: generalization of logical AND to continuous truth values [0,1]. Łukasiewicz is one variant.

### Tubelet Embedding
3D patch extraction from GAF video: $(H_p \times W_p \times T_p)$ voxel projected to vector.

### Wake/Sleep Cycle
Biological rhythm alternating between active perception (wake) and memory consolidation (sleep). Core JANUS architectural principle.

---

## Usage Examples

### In Research Writing

**Incorrect**: "The model uses a CNN to process the data"  
**Correct**: "The Visual Cortex module employs a Video Vision Transformer (ViViT) with factorized spatiotemporal attention to process Gramian Angular Field (GAF) textures encoding market microstructure."

### Cross-Referencing

When introducing a term:
> The **Amygdala** module (Section 6) computes the Mahalanobis distance to detect distributional anomalies.

When using previously defined term:
> The Amygdala triggers the kill switch when $D_M > \theta_{\text{critical}}$.

---

## Acronym Quick Reference Card

| Acronym | Full Term | Section |
|---------|-----------|---------|
| GAF | Gramian Angular Field | Computer Vision |
| ViViT | Video Vision Transformer | Machine Learning |
| LTN | Logic Tensor Network | Neurosymbolic AI |
| OpAL | Opponent Actor Learning | Neuroscience |
| UMAP | Uniform Manifold Approximation | Statistics |
| PER | Prioritized Experience Replay | Reinforcement Learning |
| RPE | Reward Prediction Error | Neuroscience |
| VWAP | Volume-Weighted Average Price | Finance |
| LOB | Limit Order Book | Finance |
| SWR | Sharp-Wave Ripple | Neuroscience |

---

## Related Documents

- **Full Bibliography**: `BIBLIOGRAPHY.md`
- **Hyperparameter Specifications**: `HYPERPARAMETERS.md`
- **Architecture Specification**: `JANUS_ARCHITECTURAL_SPECIFICATION.md`
- **Implementation Status**: `JANUS_IMPLEMENTATION_STATUS.md`

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-XX | Initial glossary with 100+ terms |

---

**End of Glossary**

*For term requests or corrections, please submit an issue to the documentation repository.*