import React from 'react';
import './ErrorPage.css';

const Error500 = () => {
    return (
        <div className="container">
            <div className="error-illustration">⚠️</div>
            <div className="error-code">500</div>
            <h1>Server Error</h1>
            <p className="subtitle">Houston, we have a problem!</p>
            <p className="description">
                Our digital bees are experiencing some technical difficulties. This isn't your fault -
                our servers are having a temporary hiccup while processing your request.
            </p>
            <div className="status-indicator">
                <span className="status-dot"></span>
                <span>System Status: Under Investigation</span>
            </div>
            <div className="error-details">
                <h3>🔍 Technical Information</h3>
                <div className="error-info">
                    <div className="error-item">
                        <div className="error-label">Error Code</div>
                        <div className="error-value">HTTP 500</div>
                    </div>
                    <div className="error-item">
                        <div className="error-label">Timestamp</div>
                        <div className="error-value">{new Date().toLocaleString()}</div>
                    </div>
                    <div className="error-item">
                        <div className="error-label">Server</div>
                        <div className="error-value">7gram.xyz</div>
                    </div>
                </div>
            </div>
            <div className="suggestions">
                <h3>🔧 What you can do:</h3>
                <ul>
                    <li>Wait a few minutes and try refreshing the page</li>
                    <li>Check our system status page for ongoing issues</li>
                    <li>Try accessing a different service from the dashboard</li>
                    <li>Contact our support team if the problem persists</li>
                </ul>
            </div>
            <div className="button-group">
                <a href="javascript:location.reload()" className="btn btn-refresh">🔄 Try Again</a>
                <a href="/" className="btn btn-primary">🏠 Back to Dashboard</a>
            </div>
        </div>
    );
};

export default Error500;
