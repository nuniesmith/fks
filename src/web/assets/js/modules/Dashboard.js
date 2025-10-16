import React, { useState, useEffect } from 'react';
import './Dashboard.css';

const Dashboard = () => {
    const [services, setServices] = useState([]);
    const [query, setQuery] = useState('');
    const [visibleServices, setVisibleServices] = useState([]);
    const [tradingStatus, setTradingStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        loadServices();
        loadTradingStatus();
    }, []);
    
    const loadServices = async () => {
        try {
            const response = await fetch('/api/services');
            const data = await response.json();
            setServices(data);
            setVisibleServices(data);
        } catch (error) {
            console.error('Failed to load services', error);
            // Fallback services if API fails
            const fallbackServices = [
                {
                    id: 'fks_addon',
                    name: 'FKS Trading Addon',
                    icon: '⚡',
                    description: 'Custom FKS trading algorithms and strategies',
                    url: '/build',
                    category: 'Trading Tools'
                },
                {
                    id: 'ninja-trader',
                    name: 'NinjaTrader Platform',
                    icon: '📊',
                    description: 'Professional trading platform',
                    url: 'https://ninjatrader.com',
                    category: 'Trading Platforms'
                }
            ];
            setServices(fallbackServices);
            setVisibleServices(fallbackServices);
        } finally {
            setLoading(false);
        }
    };
    
    const loadTradingStatus = async () => {
        try {
            const response = await fetch('/api/trading-status');
            const data = await response.json();
            setTradingStatus(data);
        } catch (error) {
            console.error('Failed to load trading status', error);
        }
    };
    
    const onSearch = (e) => {
        const searchQuery = e.target.value.toLowerCase();
        setQuery(searchQuery);

        const filteredServices = services.filter(service =>
            service.name.toLowerCase().includes(searchQuery) ||
            service.description.toLowerCase().includes(searchQuery) ||
            service.category.toLowerCase().includes(searchQuery)
        );

        setVisibleServices(filteredServices);
    };
    
    const groupServicesByCategory = () => {
        const grouped = {};
        visibleServices.forEach(service => {
            const category = service.category || 'Other';
            if (!grouped[category]) {
                grouped[category] = [];
            }
            grouped[category].push(service);
        });
        return grouped;
    };
    
    const getStatusColor = (status) => {
        switch(status) {
            case 'active': return '#4CAF50';
            case 'development': return '#FF9800';
            case 'inactive': return '#F44336';
            default: return '#9E9E9E';
        }
    };

    if (loading) {
        return (
            <div className="dashboard-container">
                <div className="loading-spinner">Loading FKS Trading Systems...</div>
            </div>
        );
    }

    return (
        <div className="dashboard-container">
            <header className="dashboard-header">
                <h1>⚡ FKS Trading Systems</h1>
                <p className="dashboard-subtitle">Professional NinjaTrader Development Environment</p>
                
                {tradingStatus && (
                    <div className="trading-status">
                        <div className="status-item">
                            <span className="status-label">System Status:</span>
                            <span className="status-value operational">{tradingStatus.status}</span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">FKS Addon:</span>
                            <span className="status-value">{tradingStatus.fks_addon?.status}</span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">Markets:</span>
                            <span className="status-value">
                                Futures: {tradingStatus.markets?.futures} | 
                                Forex: {tradingStatus.markets?.forex}
                            </span>
                        </div>
                    </div>
                )}
                
                <div className="search-container">
                    <input
                        type="text"
                        value={query}
                        onChange={onSearch}
                        placeholder="🔍 Search trading tools and services..."
                        className="search-input"
                    />
                </div>
            </header>
            
            <main className="services-container">
                {Object.entries(groupServicesByCategory()).map(([category, categoryServices]) => (
                    <div key={category} className="category-section">
                        <h2 className="category-title">{category}</h2>
                        <div className="services-grid">
                            {categoryServices.map(service => (
                                <div key={service.id} className="service-card">
                                    <div className="service-header">
                                        <span className="service-icon">{service.icon}</span>
                                        {service.status && (
                                            <span 
                                                className="service-status"
                                                style={{ backgroundColor: getStatusColor(service.status) }}
                                            >
                                                {service.status}
                                            </span>
                                        )}
                                    </div>
                                    <h3 className="service-name">{service.name}</h3>
                                    <p className="service-description">{service.description}</p>
                                    <a 
                                        href={service.url} 
                                        target={service.url.startsWith('http') ? '_blank' : '_self'}
                                        rel="noopener noreferrer" 
                                        className="service-link"
                                    >
                                        {service.url.startsWith('/') ? 'Open' : 'Visit'} {service.name} ↗️
                                    </a>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
                
                {visibleServices.length === 0 && (
                    <div className="no-results">
                        <h3>🔍 No services found</h3>
                        <p>Try adjusting your search terms or browse all available trading tools.</p>
                    </div>
                )}
            </main>
        </div>
    );
};

export default Dashboard;
