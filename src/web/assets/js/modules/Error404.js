import React from 'react';
import './ErrorPage.css';

const Error404 = () => {
    return (
        <div className="container">
            <div className="error-illustration">🤖</div>
            <div className="error-code">404</div>
            <h1>Oops! Page Not Found</h1>
            <p className="subtitle">The digital bees couldn't find this honeycomb!</p>
            <p className="description">
                The page you're looking for seems to have wandered off into the digital wilderness.
                Don't worry, even the best navigation systems occasionally take a wrong turn!
            </p>
            <div className="suggestions">
                <h3>🔍 Here's what you can try:</h3>
                <ul>
                    <li>Check the URL for any typos or missing characters</li>
                    <li>Use the search function on our main dashboard</li>
                    <li>Navigate back to the home page and try again</li>
                    <li>Contact us if you believe this is an error</li>
                </ul>
            </div>
            <div className="button-group">
                <a href="/" className="btn btn-primary">🏠 Back to Dashboard</a>
                <a href="javascript:history.back()" className="btn btn-secondary">← Go Back</a>
            </div>
        </div>
    );
};

export default Error404;
