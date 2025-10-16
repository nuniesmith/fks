import { FileText, Book, ExternalLink, Search, ChevronRight, Code, Globe, FolderOpen, File } from 'lucide-react';
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import AsyncMermaid from './AsyncMermaid';

interface DocFile {
  name: string;
  path: string;
  content?: string;
  type: 'md' | 'html' | 'txt' | 'pdf';
  lastModified: string;
  size: number;
  category: 'docs' | 'html' | 'architecture' | 'guides';
}

interface DocumentationViewerProps {
  className?: string;
}

const DocumentationViewer: React.FC<DocumentationViewerProps> = ({ className = '' }) => {
  const [docs, setDocs] = useState<DocFile[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocFile | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    loadDocumentation();
  }, []);

  const loadDocumentation = async () => {
    try {
      setLoading(true);
      
      // Load markdown documentation from docs directory
      const markdownDocs: DocFile[] = [
        {
          name: 'Development Guide',
          path: '/docs/DEVELOPMENT_GUIDE.md',
          type: 'md',
          lastModified: new Date().toISOString(),
          size: 12000,
          category: 'docs'
        },
        {
          name: 'Environment Setup',
          path: '/docs/ENVIRONMENT_SETUP.md',
          type: 'md',
          lastModified: new Date().toISOString(),
          size: 8500,
          category: 'guides'
        },
        {
          name: 'Docker Build Optimization',
          path: '/docs/DOCKER_BUILD_OPTIMIZATION.md',
          type: 'md',
          lastModified: new Date().toISOString(),
          size: 15000,
          category: 'guides'
        },
        {
          name: 'GitHub Actions Guide',
          path: '/docs/GITHUB_ACTIONS_GUIDE.md',
          type: 'md',
          lastModified: new Date().toISOString(),
          size: 10000,
          category: 'guides'
        }
      ];

    // Load HTML files from /docs (served via public/docs)
      const htmlDocs: DocFile[] = [
        {
          name: 'Architecture Diagram',
      path: '/docs/architecture-diagram.html',
          type: 'html',
          lastModified: new Date().toISOString(),
          size: 25000,
          category: 'architecture'
        },
        {
          name: 'System Status',
      path: '/docs/status.html',
          type: 'html',
          lastModified: new Date().toISOString(),
          size: 5000,
          category: 'html'
        },
        {
          name: '404 Error Page',
      path: '/docs/404.html',
          type: 'html',
          lastModified: new Date().toISOString(),
          size: 3000,
          category: 'html'
        },
        {
          name: '50x Error Page',
      path: '/docs/50x.html',
          type: 'html',
          lastModified: new Date().toISOString(),
          size: 3500,
          category: 'html'
        }
      ];

      setDocs([...markdownDocs, ...htmlDocs]);
      
    } catch (err) {
      setError('Error loading documentation files');
    } finally {
      setLoading(false);
    }
  };

  const loadDocContent = async (doc: DocFile) => {
    try {
      if (doc.type === 'html') {
        // For HTML files, we'll load them in an iframe or open in new tab
        if (doc.name === 'Architecture Diagram') {
          // Special handling for architecture diagram
          setSelectedDoc({
            ...doc,
            content: 'ARCHITECTURE_DIAGRAM' // Special marker
          });
        } else {
          // Open other HTML files in new tab
          window.open(doc.path, '_blank');
        }
        return;
      }

      // For markdown files, try to load content from local storage or mock
      const mockContent = `# ${doc.name}

This is a placeholder for the ${doc.name} documentation. 

## Overview
This documentation file contains important information about the FKS Trading System.

## Key Features
- Real-time trading capabilities
- Advanced strategy development
- Multi-account management
- Comprehensive risk management

## Getting Started
Follow the setup instructions in this guide to get your FKS system up and running.

## Implementation Details
This document covers the following topics:
- System architecture and design patterns
- API endpoints and data flows
- Configuration and environment setup
- Deployment procedures and best practices

## Next Steps
1. Review the complete documentation
2. Follow the setup instructions
3. Test the integration points
4. Configure your environment

---
*This content is loaded from: ${doc.path}*
*File size: ${(doc.size / 1024).toFixed(1)} KB*
*Last modified: ${new Date(doc.lastModified).toLocaleDateString()}*`;

      setSelectedDoc({
        ...doc,
        content: mockContent
      });
      
    } catch (err) {
      setError(`Failed to load content for ${doc.name}`);
    }
  };

  const filteredDocs = selectedCategory === 'all' 
    ? docs 
    : docs.filter(doc => doc.category === selectedCategory);

  const searchFilteredDocs = filteredDocs.filter(doc =>
    doc.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'docs':
        return <FileText className="w-4 h-4" />;
      case 'html':
        return <Globe className="w-4 h-4" />;
      case 'architecture':
        return <Code className="w-4 h-4" />;
      case 'guides':
        return <Book className="w-4 h-4" />;
      default:
        return <File className="w-4 h-4" />;
    }
  };

  const renderArchitectureDiagram = () => {
    return (
      <div className="h-full">
        <div className="mb-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <h3 className="text-lg font-semibold text-blue-400 mb-2">Architecture Diagram</h3>
          <p className="text-gray-300 text-sm">
            Interactive architecture diagram showing the complete FKS Trading System structure.
          </p>
          <button
            onClick={() => window.open('/docs/architecture-diagram.html', '_blank')}
            className="mt-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white transition-colors flex items-center space-x-2"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Open in New Tab</span>
          </button>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 h-96">
          <iframe
            src="/docs/architecture-diagram.html"
            className="w-full h-full border-0 rounded"
            title="FKS Architecture Diagram"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className={`flex items-center justify-center h-96 ${className}`}>
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">Loading documentation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center h-96 ${className}`}>
        <div className="text-center">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExternalLink className="w-8 h-8 text-red-400" />
          </div>
          <p className="text-red-400 mb-2">Error loading documentation</p>
          <p className="text-gray-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full ${className}`}>
      <div className="flex h-full">
        {/* Sidebar */}
        <div className="w-1/3 border-r border-gray-700 bg-gray-800/50">
          {/* Header */}
          <div className="p-4 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white mb-4">Documentation</h2>
            
            {/* Search */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search documentation..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap gap-2">
              {['all', 'docs', 'guides', 'architecture', 'html'].map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-3 py-1 rounded-full text-sm transition-colors capitalize ${
                    selectedCategory === category
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>

          {/* File List */}
          <div className="overflow-y-auto">
            {searchFilteredDocs.length === 0 ? (
              <div className="p-4 text-center text-gray-400">
                No documentation found
              </div>
            ) : (
              searchFilteredDocs.map((doc) => (
                <div
                  key={doc.path}
                  onClick={() => loadDocContent(doc)}
                  className={`p-4 border-b border-gray-700 cursor-pointer hover:bg-gray-700/50 transition-colors ${
                    selectedDoc?.path === doc.path ? 'bg-gray-700/70 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    {getCategoryIcon(doc.category)}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-white truncate">{doc.name}</h3>
                      <p className="text-sm text-gray-400 mt-1">
                        {doc.type.toUpperCase()} • {(doc.size / 1024).toFixed(1)} KB
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(doc.lastModified).toLocaleDateString()}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 bg-gray-900">
          {selectedDoc ? (
            <div className="h-full overflow-y-auto">
              {selectedDoc.content === 'ARCHITECTURE_DIAGRAM' ? (
                <div className="p-6 h-full">
                  {renderArchitectureDiagram()}
                </div>
              ) : (
                <div className="p-6">
                  {/* Document Header */}
                  <div className="mb-6 pb-4 border-b border-gray-700">
                    <div className="flex items-center space-x-3 mb-2">
                      {getCategoryIcon(selectedDoc.category)}
                      <h1 className="text-2xl font-bold text-white">{selectedDoc.name}</h1>
                      <span className={`px-2 py-1 rounded text-xs ${
                        selectedDoc.type === 'html' ? 'bg-orange-500/20 text-orange-400' :
                        selectedDoc.type === 'md' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {selectedDoc.type.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center space-x-4 text-sm text-gray-400">
                      <span>Size: {(selectedDoc.size / 1024).toFixed(1)} KB</span>
                      <span>Modified: {new Date(selectedDoc.lastModified).toLocaleDateString()}</span>
                      <span className="capitalize">Category: {selectedDoc.category}</span>
                    </div>
                  </div>

                  {/* Document Content */}
                  <div className="prose prose-invert max-w-none">
                    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                      <ReactMarkdown
                        components={{
                          code({node, className, children, ...props}) {
                            const txt = String(children)
                            const match = /language-(\w+)/.exec(className || '')
                            const lang = match?.[1]
                            if (lang === 'mermaid') {
                              return <AsyncMermaid chart={txt} />
                            }
                            return <code className={(className || '') + ' text-xs'} {...props}>{children}</code>
                          },
                          h1: ({children}) => <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>,
                          h2: ({children}) => <h2 className="text-xl font-semibold mt-6 mb-2">{children}</h2>,
                          p: ({children}) => <p className="mb-3 leading-relaxed">{children}</p>,
                          ul: ({children}) => <ul className="list-disc ml-6 mb-3 space-y-1">{children}</ul>
                        }}
                      >
                        {selectedDoc.content || ''}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <FolderOpen className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-white mb-2">No Document Selected</h3>
                <p className="text-gray-400">
                  Select a document from the sidebar to view its contents
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentationViewer;
