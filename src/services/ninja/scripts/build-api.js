#!/usr/bin/env node

/**
 * FKS Trading Systems - Build API
 * Provides REST API for building packages (for React integration)
 */

const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Project paths
const PROJECT_ROOT = path.join(__dirname, '..');
const SCRIPTS_DIR = path.join(PROJECT_ROOT, 'scripts');
const PACKAGES_DIR = path.join(PROJECT_ROOT, 'build', 'packages');

// Utility function to run shell commands
const runCommand = (command, cwd = PROJECT_ROOT) => {
    return new Promise((resolve, reject) => {
        exec(command, { cwd }, (error, stdout, stderr) => {
            if (error) {
                reject({ error: error.message, stderr, stdout });
            } else {
                resolve({ stdout, stderr });
            }
        });
    });
};

// Routes

/**
 * GET /api/status
 * Check build system status
 */
app.get('/api/status', async (req, res) => {
    try {
        const srcExists = fs.existsSync(path.join(PROJECT_ROOT, 'src'));
        const scriptsExist = fs.existsSync(path.join(SCRIPTS_DIR, 'build-simple.sh'));
        
        res.json({
            status: 'ok',
            timestamp: new Date().toISOString(),
            project_root: PROJECT_ROOT,
            source_files: srcExists,
            build_scripts: scriptsExist,
            node_version: process.version
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * POST /api/build
 * Build package
 * Body: { type: 'source' | 'dll', version?: string }
 */
app.post('/api/build', async (req, res) => {
    try {
        const { type = 'source', version = '1.0.0' } = req.body;
        
        let command;
        if (type === 'source') {
            command = './scripts/build-simple.sh';
        } else if (type === 'dll') {
            command = './scripts/build-package.sh --dll --json';
        } else {
            return res.status(400).json({ error: 'Invalid build type. Use "source" or "dll"' });
        }
        
        const startTime = Date.now();
        const result = await runCommand(command);
        const buildTime = ((Date.now() - startTime) / 1000).toFixed(2);
        
        // Find the created package
        const packages = fs.readdirSync(PACKAGES_DIR)
            .filter(file => file.endsWith('.zip'))
            .map(file => {
                const filePath = path.join(PACKAGES_DIR, file);
                const stats = fs.statSync(filePath);
                return {
                    name: file,
                    path: filePath,
                    size: (stats.size / 1024).toFixed(2) + 'KB',
                    created: stats.mtime
                };
            })
            .sort((a, b) => b.created - a.created);
        
        res.json({
            status: 'success',
            build_type: type,
            build_time: buildTime + 's',
            package: packages[0] || null,
            all_packages: packages,
            output: result.stdout
        });
        
    } catch (error) {
        res.status(500).json({
            status: 'error',
            error: error.error || error.message,
            stderr: error.stderr,
            stdout: error.stdout
        });
    }
});

/**
 * GET /api/packages
 * List available packages
 */
app.get('/api/packages', (req, res) => {
    try {
        if (!fs.existsSync(PACKAGES_DIR)) {
            return res.json({ packages: [] });
        }
        
        const packages = fs.readdirSync(PACKAGES_DIR)
            .filter(file => file.endsWith('.zip'))
            .map(file => {
                const filePath = path.join(PACKAGES_DIR, file);
                const stats = fs.statSync(filePath);
                return {
                    name: file,
                    size: (stats.size / 1024).toFixed(2) + 'KB',
                    created: stats.mtime,
                    download_url: `/api/download/${file}`
                };
            })
            .sort((a, b) => b.created - a.created);
        
        res.json({ packages });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * GET /api/download/:filename
 * Download package file
 */
app.get('/api/download/:filename', (req, res) => {
    try {
        const filename = req.params.filename;
        const filePath = path.join(PACKAGES_DIR, filename);
        
        if (!fs.existsSync(filePath) || !filename.endsWith('.zip')) {
            return res.status(404).json({ error: 'Package not found' });
        }
        
        res.download(filePath, filename);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

/**
 * POST /api/clean
 * Clean build artifacts
 */
app.post('/api/clean', async (req, res) => {
    try {
        const result = await runCommand('./scripts/clean.sh');
        
        res.json({
            status: 'success',
            message: 'Build artifacts cleaned',
            output: result.stdout
        });
    } catch (error) {
        res.status(500).json({
            status: 'error',
            error: error.error || error.message,
            stderr: error.stderr
        });
    }
});

/**
 * POST /api/validate
 * Validate package
 * Body: { package: 'filename.zip' }
 */
app.post('/api/validate', async (req, res) => {
    try {
        const { package: packageName } = req.body;
        
        if (!packageName) {
            return res.status(400).json({ error: 'Package name required' });
        }
        
        const packagePath = path.join(PACKAGES_DIR, packageName);
        if (!fs.existsSync(packagePath)) {
            return res.status(404).json({ error: 'Package not found' });
        }
        
        const result = await runCommand(`./scripts/validate.sh "${packagePath}" --json`);
        
        try {
            const validationResult = JSON.parse(result.stdout);
            res.json({
                status: 'success',
                validation: validationResult
            });
        } catch (parseError) {
            res.json({
                status: 'success',
                validation: { raw_output: result.stdout }
            });
        }
        
    } catch (error) {
        res.status(500).json({
            status: 'error',
            error: error.error || error.message,
            stderr: error.stderr
        });
    }
});

// Error handling
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(PORT, () => {
    console.log(`FKS Build API running on port ${PORT}`);
    console.log(`Project root: ${PROJECT_ROOT}`);
    console.log(`API endpoints:`);
    console.log(`  GET  /api/status`);
    console.log(`  POST /api/build`);
    console.log(`  GET  /api/packages`);
    console.log(`  GET  /api/download/:filename`);
    console.log(`  POST /api/clean`);
    console.log(`  POST /api/validate`);
});

module.exports = app;
