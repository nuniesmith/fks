import React, { useState } from 'react';
import { Dashboard, Error404, Error500, ArchitectureDiagram, DocumentationViewer } from './index';
import './FKSApp.css';

const FKSApp = () => {
    const [currentView, setCurrentView] = useState('dashboard');
    const [error, setError] = useState(null);
    
    const handleNavigation = (view) => {
        setCurrentView(view);
        setError(null);
    };
    
    const renderCurrentView = () => {
        try {
            switch(currentView) {
                case 'dashboard':
                    return <Dashboard />;
                case 'architecture':
                    return <ArchitectureDiagram />;
                case 'documentation':
                    return <DocumentationViewer />;
                case 'error-404':
                    return <Error404 />;
                case 'error-500':
                    return <Error500 />;
                default:
                    return <Dashboard />;
            }
        } catch (err) {
            setError(err);
            return <Error500 />;
        }
    };
    
    if (error) {
        return <Error500 />;
    }
    
    return (
        <div className="fks_app">
            <nav className="fks_nav">
                <div className="nav-brand">
                    <span className="brand-icon">⚡</span>
                    <span className="brand-text">FKS Trading Systems</span>
                </div>
                <div className="nav-links">
                    <button 
                        className={`nav-link ${currentView === 'dashboard' ? 'active' : ''}`}
                        onClick={() => handleNavigation('dashboard')}
                    >
                        📊 Dashboard
                    </button>
                    <button 
                        className={`nav-link ${currentView === 'architecture' ? 'active' : ''}`}
                        onClick={() => handleNavigation('architecture')}
                    >
                        🏗️ Architecture
                    </button>
                    <button 
                        className={`nav-link ${currentView === 'documentation' ? 'active' : ''}`}
                        onClick={() => handleNavigation('documentation')}
                    >
                        📚 Documentation
                    </button>
                </div>
            </nav>
            
            <main className="fks_main">
                {renderCurrentView()}
            </main>
        </div>
    );
};

export default FKSApp;
