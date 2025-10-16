// FKS Trading Systems Architecture Interactive Application
class ArchitectureApp {
    constructor() {
        this.currentFilter = '';
        this.collapsedLayers = new Set();
        this.init();
    }

    init() {
        this.renderArchitecture();
        this.setupEventListeners();
        this.setupNavigation();
        this.startStatusUpdates();
    }

    renderArchitecture() {
        const container = document.getElementById('architectureLayers');
        container.innerHTML = '';

        architectureData.layers.forEach(layer => {
            const layerElement = this.createLayerElement(layer);
            container.appendChild(layerElement);
        });
    }

    createLayerElement(layer) {
        const isCollapsed = this.collapsedLayers.has(layer.id);
        const layerDiv = document.createElement('div');
        layerDiv.className = `layer ${isCollapsed ? 'collapsed' : ''}`;
        layerDiv.id = layer.id;

        // Create layer title
        const titleDiv = document.createElement('div');
        titleDiv.className = 'layer-title';
        titleDiv.onclick = () => this.toggleLayer(layer.id);
        titleDiv.innerHTML = `
            ${layer.title}
            <div>
                <span class="layer-badge">${layer.badge}</span>
                <span class="collapse-icon">▼</span>
            </div>
        `;
        layerDiv.appendChild(titleDiv);

        // Create layer content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'layer-content';

        // Add description if exists
        if (layer.description) {
            const descDiv = document.createElement('p');
            descDiv.style.color = '#ccc';
            descDiv.style.marginBottom = '1rem';
            descDiv.textContent = layer.description;
            contentDiv.appendChild(descDiv);
        }

        // Add infrastructure items if exists
        if (layer.infrastructureItems) {
            const infraGrid = document.createElement('div');
            infraGrid.className = 'infrastructure-grid';
            
            layer.infrastructureItems.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'infra-item';
                itemDiv.innerHTML = `${item.icon} ${item.name}`;
                itemDiv.onclick = () => this.showInfraDetails(item);
                infraGrid.appendChild(itemDiv);
            });
            
            contentDiv.appendChild(infraGrid);
        }

        // Add services grid
        if (layer.services) {
            const servicesGrid = document.createElement('div');
            servicesGrid.className = 'services-grid';
            
            layer.services.forEach(service => {
                const serviceCard = this.createServiceCard(service);
                servicesGrid.appendChild(serviceCard);
            });
            
            contentDiv.appendChild(servicesGrid);
        }

        // Add data flow if exists
        if (layer.flow) {
            const flowContainer = this.createDataFlow(layer.flow);
            contentDiv.appendChild(flowContainer);
        }

        layerDiv.appendChild(contentDiv);

        // Add flow arrow (except for last layer)
        if (layer.id !== 'dataflow') {
            const arrow = document.createElement('div');
            arrow.className = 'flow-arrow';
            arrow.innerHTML = '⬇';
            container.appendChild(layerDiv);
            container.appendChild(arrow);
        } else {
            container.appendChild(layerDiv);
        }

        return layerDiv;
    }

    createServiceCard(service) {
        const card = document.createElement('div');
        card.className = 'service-card';
        
        if (service.borderColor) {
            card.style.borderColor = service.borderColor;
        }

        // Add status indicator
        const statusClass = `status-${service.status}`;
        
        let cardHTML = `
            <div class="service-name">
                <span class="status-indicator ${statusClass}"></span>
                ${service.name}
                ${service.port ? `<span style="font-size: 0.8em; color: #999;"> :${service.port}</span>` : ''}
            </div>
            <div class="service-details">
        `;

        // Add details as list
        if (service.details && service.details.length > 0) {
            cardHTML += '<ul style="list-style: none; padding: 0;">';
            service.details.forEach(detail => {
                cardHTML += `<li>• ${detail}</li>`;
            });
            cardHTML += '</ul>';
        }

        // Add patterns
        if (service.patterns) {
            service.patterns.forEach(pattern => {
                cardHTML += `<span class="pattern-tag">${pattern}</span> `;
            });
        }

        // Add tech stack
        if (service.technologies) {
            cardHTML += '<div class="tech-stack">';
            service.technologies.forEach(tech => {
                cardHTML += `<span class="tech-badge">${tech}</span>`;
            });
            cardHTML += '</div>';
        }

        cardHTML += '</div>';
        card.innerHTML = cardHTML;

        // Add click handler
        card.onclick = () => this.showServiceDetails(service);

        return card;
    }

    createDataFlow(flow) {
        const container = document.createElement('div');
        container.style.textAlign = 'center';
        container.style.padding = '30px';

        const flowDiv = document.createElement('div');
        flowDiv.style.display = 'flex';
        flowDiv.style.justifyContent = 'center';
        flowDiv.style.alignItems = 'center';
        flowDiv.style.flexWrap = 'wrap';
        flowDiv.style.gap = '20px';

        flow.forEach((step, index) => {
            const stepDiv = document.createElement('span');
            stepDiv.style.display = 'inline-block';
            stepDiv.style.padding = '15px 25px';
            stepDiv.style.background = '#3a3a3a';
            stepDiv.style.borderRadius = '8px';
            stepDiv.style.cursor = 'pointer';
            stepDiv.className = 'tooltip';
            
            stepDiv.innerHTML = `
                ${step.step}
                <span class="tooltiptext">${step.description}</span>
            `;

            flowDiv.appendChild(stepDiv);

            if (index < flow.length - 1) {
                const arrow = document.createElement('span');
                arrow.style.color = '#4a90e2';
                arrow.style.fontSize = '1.5em';
                arrow.innerHTML = '→';
                flowDiv.appendChild(arrow);
            }
        });

        container.appendChild(flowDiv);
        return container;
    }

    toggleLayer(layerId) {
        const layer = document.getElementById(layerId);
        if (this.collapsedLayers.has(layerId)) {
            this.collapsedLayers.delete(layerId);
            layer.classList.remove('collapsed');
        } else {
            this.collapsedLayers.add(layerId);
            layer.classList.add('collapsed');
        }
    }

    showServiceDetails(service) {
        const modal = document.getElementById('serviceModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');

        modalTitle.innerHTML = `${service.name} <span class="status-indicator status-${service.status}"></span>`;
        
        let bodyHTML = '<div style="color: #ccc;">';
        
        // Port information
        if (service.port) {
            bodyHTML += `<p><strong>Port:</strong> ${service.port}</p>`;
        }

        // Status
        bodyHTML += `<p><strong>Status:</strong> ${service.status}</p>`;

        // GPU support
        if (service.gpu) {
            bodyHTML += `<p><strong>GPU Enabled:</strong> Yes (CUDA)</p>`;
        }

        // Frontend indicator
        if (service.frontend) {
            bodyHTML += `<p><strong>Type:</strong> Frontend Service</p>`;
        }

        // Endpoints
        if (service.endpoints) {
            bodyHTML += '<h3>Endpoints:</h3><ul>';
            service.endpoints.forEach(endpoint => {
                bodyHTML += `<li><code>${endpoint}</code></li>`;
            });
            bodyHTML += '</ul>';
        }

        // Patterns
        if (service.patterns) {
            bodyHTML += '<h3>Architectural Patterns:</h3>';
            service.patterns.forEach(pattern => {
                bodyHTML += `<span class="pattern-tag">${pattern}</span> `;
            });
        }

        // Technologies
        if (service.technologies) {
            bodyHTML += '<h3 style="margin-top: 1rem;">Technologies:</h3><div class="tech-stack">';
            service.technologies.forEach(tech => {
                bodyHTML += `<span class="tech-badge">${tech}</span>`;
            });
            bodyHTML += '</div>';
        }

        // Service connections
        const serviceName = this.extractServiceName(service.name);
        const connections = this.getServiceConnections(serviceName);
        if (connections.length > 0) {
            bodyHTML += '<h3 style="margin-top: 1rem;">Connected Services:</h3><ul>';
            connections.forEach(conn => {
                bodyHTML += `<li>${conn}</li>`;
            });
            bodyHTML += '</ul>';
        }

        // Metrics (if available)
        const metrics = architectureData.metrics[serviceName];
        if (metrics) {
            bodyHTML += '<h3 style="margin-top: 1rem;">Metrics:</h3><ul>';
            Object.entries(metrics).forEach(([key, value]) => {
                const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                bodyHTML += `<li><strong>${formattedKey}:</strong> ${value}</li>`;
            });
            bodyHTML += '</ul>';
        }

        bodyHTML += '</div>';
        modalBody.innerHTML = bodyHTML;
        modal.style.display = 'flex';
    }

    showInfraDetails(item) {
        const modal = document.getElementById('serviceModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');

        modalTitle.textContent = `${item.icon} ${item.name}`;
        
        let details = {
            'Base Classes': 'Foundation classes that all services inherit from, providing common functionality like logging, configuration, and lifecycle management.',
            'Config Management': 'Centralized configuration system using YAML files, environment variables, and dynamic config updates.',
            'Logging (Loguru)': 'Structured logging using Loguru library with JSON output, correlation IDs, and centralized log aggregation.',
            'Monitoring': 'Prometheus metrics, health checks, and custom dashboards for system observability.',
            'Persistence': 'Database abstraction layer supporting PostgreSQL, Redis, and future data stores.',
            'Lifecycle Management': 'Service initialization, graceful shutdown, and state management.',
            'Exception Handling': 'Global exception handlers, retry logic, and error recovery mechanisms.',
            'Validation': 'Input validation, schema validation, and data integrity checks.',
            'Security Layer': 'TLS/SSL, API authentication, authorization, and encryption at rest.',
            'Monitoring Stack': 'Prometheus, Grafana, and custom metrics for real-time monitoring.',
            'Logging Pipeline': 'ELK stack or similar for log aggregation and analysis.',
            'CI/CD Pipeline': 'GitHub Actions for automated testing, building, and deployment.',
            'API Gateway': 'Centralized API routing, rate limiting, and authentication.',
            'Backup Systems': 'Automated backup strategies for databases and critical data.'
        };

        modalBody.innerHTML = `
            <div style="color: #ccc;">
                <p>${details[item.name] || 'Infrastructure component for the FKS Trading Systems.'}</p>
            </div>
        `;
        
        modal.style.display = 'flex';
    }

    extractServiceName(displayName) {
        const nameMap = {
            '📊 Data Service': 'data',
            '🎯 App Service (Core Engine)': 'app',
            '⚙️ Worker Service': 'worker',
            '🔌 API Service': 'api',
            '🧠 Training Service': 'training',
            '🤖 Transformer Service': 'transformer',
            '🌐 Web Service': 'web'
        };
        return nameMap[displayName] || displayName.toLowerCase();
    }

    getServiceConnections(serviceName) {
        return architectureData.serviceConnections[serviceName] || [];
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('input', (e) => {
            this.filterServices(e.target.value);
        });

        // Modal close
        const modalClose = document.getElementById('modalClose');
        const modal = document.getElementById('serviceModal');
        
        modalClose.onclick = () => {
            modal.style.display = 'none';
        };

        window.onclick = (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        };

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                modal.style.display = 'none';
            }
            if (e.key === '/' && e.ctrlKey) {
                e.preventDefault();
                searchInput.focus();
            }
        });
    }

    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = item.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                
                if (targetElement) {
                    // Remove collapsed state if navigating to it
                    this.collapsedLayers.delete(targetId);
                    targetElement.classList.remove('collapsed');
                    
                    // Smooth scroll
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    
                    // Update active nav
                    navItems.forEach(nav => nav.classList.remove('active'));
                    item.classList.add('active');
                }
            });
        });
    }

    filterServices(searchTerm) {
        const term = searchTerm.toLowerCase();
        const allCards = document.querySelectorAll('.service-card');
        const allInfraItems = document.querySelectorAll('.infra-item');
        
        // Reset all highlights
        allCards.forEach(card => card.classList.remove('highlighted'));
        allInfraItems.forEach(item => item.classList.remove('highlighted'));

        if (!term) {
            return;
        }

        // Search and highlight matching items
        allCards.forEach(card => {
            const text = card.textContent.toLowerCase();
            if (text.includes(term)) {
                card.classList.add('highlighted');
                // Ensure parent layer is expanded
                const layer = card.closest('.layer');
                if (layer) {
                    const layerId = layer.id;
                    this.collapsedLayers.delete(layerId);
                    layer.classList.remove('collapsed');
                }
            }
        });

        allInfraItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (text.includes(term)) {
                item.classList.add('highlighted');
            }
        });
    }

    startStatusUpdates() {
        // Simulate status updates
        setInterval(() => {
            const services = ['healthy', 'warning', 'error'];
            const indicators = document.querySelectorAll('.status-indicator');
            
            indicators.forEach(indicator => {
                // Randomly update status (10% chance)
                if (Math.random() < 0.1) {
                    const currentClasses = Array.from(indicator.classList);
                    const statusClass = currentClasses.find(c => c.startsWith('status-'));
                    if (statusClass) {
                        indicator.classList.remove(statusClass);
                        const newStatus = services[Math.floor(Math.random() * services.length)];
                        indicator.classList.add(`status-${newStatus}`);
                    }
                }
            });
        }, 5000);
    }

    // Public API for console debugging
    showMetrics() {
        console.table(architectureData.metrics);
    }

    showConnections() {
        console.log('Service Connections:', architectureData.serviceConnections);
    }

    exportArchitecture() {
        const dataStr = JSON.stringify(architectureData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'fks_architecture.json';
        link.click();
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.fksApp = new ArchitectureApp();
    console.log('FKS Architecture App initialized. Try fksApp.showMetrics() or fksApp.exportArchitecture()');
});