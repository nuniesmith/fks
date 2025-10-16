// FKS Trading Systems Architecture Data
const architectureData = {
    layers: [
        {
            id: 'framework',
            title: 'Framework Layer',
            badge: 'Core Infrastructure',
            description: 'Base infrastructure and cross-cutting concerns for the entire system',
            infrastructureItems: [
                { icon: '🔧', name: 'Base Classes' },
                { icon: '⚙️', name: 'Config Management' },
                { icon: '📝', name: 'Logging (Loguru)' },
                { icon: '📊', name: 'Monitoring' },
                { icon: '💾', name: 'Persistence' },
                { icon: '🔄', name: 'Lifecycle Management' },
                { icon: '🚨', name: 'Exception Handling' },
                { icon: '✅', name: 'Validation' }
            ],
            services: [
                {
                    name: 'Architectural Patterns',
                    status: 'healthy',
                    details: [
                        '📌 Disruptor Pattern (High-performance queues)',
                        '🌌 Space-Based Architecture (Distributed processing)',
                        '🔍 Filter Pattern (Data preprocessing)',
                        '👁️ Observer Pattern (Event handling)',
                        '🏭 Factory Pattern (Component creation)'
                    ],
                    technologies: ['Python', 'AsyncIO', 'Design Patterns']
                },
                {
                    name: 'Cross-Cutting Concerns',
                    status: 'healthy',
                    details: [
                        '🔐 Security (Authentication/Authorization)',
                        '⚡ Performance Optimization',
                        '📈 Telemetry & Metrics',
                        '🔄 State Management',
                        '🎯 Dependency Injection'
                    ],
                    technologies: ['JWT', 'OAuth2', 'Prometheus']
                }
            ]
        },
        {
            id: 'domain',
            title: 'Domain Layer',
            badge: 'Business Logic',
            description: 'Core business domain models and rules',
            services: [
                {
                    name: '📊 Market Data',
                    status: 'healthy',
                    details: [
                        'Real-time price feeds',
                        'Historical data models',
                        'Market microstructure',
                        'Order book depth'
                    ],
                    technologies: ['WebSocket', 'FIX Protocol', 'Market Data APIs']
                },
                {
                    name: '📈 Trading',
                    status: 'healthy',
                    details: [
                        'Order management',
                        'Signal generation',
                        'Strategy execution',
                        'Trade lifecycle'
                    ],
                    technologies: ['Trading Algorithms', 'Strategy Patterns']
                },
                {
                    name: '💼 Portfolio',
                    status: 'healthy',
                    details: [
                        'Position tracking',
                        'P&L calculation',
                        'Asset allocation',
                        'Performance metrics'
                    ],
                    technologies: ['Portfolio Theory', 'Risk Metrics']
                },
                {
                    name: '⚠️ Risk',
                    status: 'warning',
                    details: [
                        'Risk limits',
                        'Exposure monitoring',
                        'VAR calculation',
                        'Compliance rules'
                    ],
                    technologies: ['Risk Models', 'Compliance Engine']
                },
                {
                    name: '📊 Analytics',
                    status: 'healthy',
                    details: [
                        'Performance analysis',
                        'Strategy backtesting',
                        'Market analysis',
                        'Trade analytics'
                    ],
                    technologies: ['Pandas', 'NumPy', 'Matplotlib']
                }
            ]
        },
        {
            id: 'services',
            title: 'Service Layer',
            badge: 'Microservices',
            description: 'Independent microservices handling specific system functions',
            services: [
                {
                    name: '📊 Data Service',
                    status: 'healthy',
                    port: 9001,
                    details: [
                        'Market data collection',
                        'ETL processing pipeline',
                        'ODS with CQL support',
                        'Event streaming (Kafka-like)',
                        'Data validation & enrichment'
                    ],
                    patterns: ['ETL Pattern', 'Filter Pattern'],
                    technologies: ['FastAPI', 'Redis', 'PostgreSQL'],
                    endpoints: ['/health', '/status', '/data/latest/{symbol}', '/data/query']
                },
                {
                    name: '🎯 App Service (Core Engine)',
                    status: 'healthy',
                    port: 9000,
                    details: [
                        'Trading engine (SBA)',
                        'Complex event processing',
                        'Strategy orchestration',
                        'Risk management',
                        'Order generation'
                    ],
                    patterns: ['Disruptor Pattern', 'Observer Pattern'],
                    technologies: ['Space-Based Architecture', 'CEP Engine'],
                    borderColor: '#f39c12'
                },
                {
                    name: '⚙️ Worker Service',
                    status: 'healthy',
                    port: 8001,
                    details: [
                        'Async task execution',
                        'Background processing',
                        'Scheduled jobs (Celery-like)',
                        'Distributed computing',
                        'Report generation'
                    ],
                    technologies: ['Task Queue', 'Redis', 'Celery'],
                    endpoints: ['/health', '/tasks', '/schedule']
                },
                {
                    name: '🔌 API Service',
                    status: 'healthy',
                    port: 8000,
                    details: [
                        'RESTful endpoints',
                        'WebSocket support',
                        'Authentication (JWT)',
                        'Rate limiting',
                        'Circuit breaker'
                    ],
                    technologies: ['FastAPI', 'WebSocket', 'JWT'],
                    endpoints: ['/api/v1/*', '/ws', '/auth/token']
                },
                {
                    name: '🧠 Training Service',
                    status: 'warning',
                    port: 8088,
                    details: [
                        'ML model training',
                        'Backtesting engine',
                        'Model registry',
                        'Hyperparameter tuning',
                        'GPU acceleration (CUDA)'
                    ],
                    technologies: ['PyTorch', 'CUDA', 'MLflow'],
                    gpu: true
                },
                {
                    name: '🤖 Transformer Service',
                    status: 'healthy',
                    port: 8089,
                    details: [
                        'NLP for news analysis',
                        'Sentiment extraction',
                        'Entity recognition',
                        'Market context enrichment',
                        'Real-time processing'
                    ],
                    technologies: ['Transformers', 'BERT', 'spaCy'],
                    gpu: true
                },
                {
                    name: '🌐 Web Service',
                    status: 'healthy',
                    port: 9999,
                    details: [
                        'Trading dashboard',
                        'Real-time monitoring',
                        'Interactive charts',
                        'System controls',
                        'Performance analytics'
                    ],
                    technologies: ['React', 'WebSocket', 'D3.js'],
                    frontend: true
                }
            ]
        },
        {
            id: 'infrastructure',
            title: 'Infrastructure Layer',
            badge: 'Platform & DevOps',
            description: 'Platform services and infrastructure components',
            services: [
                {
                    name: '🐳 Container Orchestration',
                    status: 'healthy',
                    details: [
                        'Docker containerization',
                        'Docker Compose orchestration',
                        'Service mesh (future: K8s)',
                        'Load balancing',
                        'Auto-scaling capabilities'
                    ],
                    technologies: ['Docker', 'Docker Compose', 'Kubernetes (planned)']
                },
                {
                    name: '💾 Data Persistence',
                    status: 'healthy',
                    details: [
                        'PostgreSQL (OLTP)',
                        'Redis (Cache + Queue)',
                        'TimescaleDB (Time-series)',
                        'S3-compatible storage',
                        'Backup & Recovery'
                    ],
                    technologies: ['PostgreSQL', 'Redis', 'TimescaleDB', 'MinIO']
                },
                {
                    name: '📡 External Integrations',
                    status: 'healthy',
                    details: [
                        'Exchange APIs (FIX protocol)',
                        'Market data providers',
                        'News feeds integration',
                        'Broker connections',
                        'Regulatory reporting'
                    ],
                    technologies: ['FIX', 'REST APIs', 'WebSocket']
                }
            ],
            infrastructureItems: [
                { icon: '🔒', name: 'Security Layer' },
                { icon: '📊', name: 'Monitoring Stack' },
                { icon: '📝', name: 'Logging Pipeline' },
                { icon: '🔄', name: 'CI/CD Pipeline' },
                { icon: '🌐', name: 'API Gateway' },
                { icon: '💾', name: 'Backup Systems' }
            ]
        },
        {
            id: 'dataflow',
            title: 'System Data Flow',
            badge: 'Event-Driven Architecture',
            description: 'How data flows through the system',
            flow: [
                { step: '📡 Market Data', description: 'External data sources' },
                { step: '🔄 ETL Pipeline', description: 'Extract, Transform, Load' },
                { step: '📊 Event Queue', description: 'Message queuing system' },
                { step: '⚡ CEP Engine', description: 'Complex Event Processing' },
                { step: '🎯 Strategy Execution', description: 'Trading logic execution' },
                { step: '📋 Order Generation', description: 'Create trading orders' },
                { step: '🏦 Exchange Routing', description: 'Route to exchanges' },
                { step: '✅ Execution', description: 'Order execution confirmation' }
            ]
        }
    ],
    
    serviceConnections: {
        'api': ['data', 'app', 'worker'],
        'app': ['data', 'worker', 'api'],
        'data': ['redis', 'postgres'],
        'worker': ['redis', 'data'],
        'web': ['api', 'app', 'data'],
        'training': ['data', 'postgres'],
        'transformer': ['data', 'redis']
    },
    
    technologies: {
        'Python': { category: 'language', color: '#3776ab' },
        'FastAPI': { category: 'framework', color: '#009688' },
        'React': { category: 'framework', color: '#61dafb' },
        'Docker': { category: 'platform', color: '#2496ed' },
        'PostgreSQL': { category: 'database', color: '#336791' },
        'Redis': { category: 'database', color: '#dc382d' },
        'PyTorch': { category: 'ml', color: '#ee4c2c' },
        'CUDA': { category: 'gpu', color: '#76b900' }
    },
    
    metrics: {
        'api': {
            requests_per_second: 10000,
            latency_ms: 5,
            uptime_percent: 99.99
        },
        'data': {
            events_per_second: 50000,
            queue_size: 1000,
            processing_time_ms: 2
        },
        'app': {
            orders_per_second: 1000,
            strategy_count: 25,
            active_positions: 150
        }
    }
};