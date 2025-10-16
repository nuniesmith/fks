import { ChevronRight, FileText, Folder, Home } from 'lucide-react';
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

interface DocFile {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: DocFile[];
}

const DocsViewer: React.FC = () => {
  const [selectedDoc, setSelectedDoc] = useState<string>('');
  const [docContent, setDocContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['docs']));

  // Documentation structure
  const docStructure: DocFile[] = [
    {
      name: 'Core Documentation',
      path: 'docs',
      type: 'directory',
      children: [
        { name: 'Trading Guide', path: 'docs/TRADING_GUIDE.md', type: 'file' },
        { name: 'Deployment Guide', path: 'docs/DEPLOYMENT_GUIDE.md', type: 'file' },
        { name: 'Development Guide', path: 'docs/DEVELOPMENT_GUIDE.md', type: 'file' },
        { name: 'Troubleshooting Guide', path: 'docs/TROUBLESHOOTING_GUIDE.md', type: 'file' },
        { name: 'Trader Playbook', path: 'docs/TRADER_PLAYBOOK.md', type: 'file' },
      ]
    },
    {
      name: 'Guides & References',
      path: 'guides',
      type: 'directory',
      children: [
        { name: 'GitHub Actions Guide', path: 'docs/GITHUB_ACTIONS_GUIDE.md', type: 'file' },
        { name: 'Auto Update Reference', path: 'docs/AUTO_UPDATE_QUICK_REFERENCE.md', type: 'file' },
        { name: 'Linode Automation', path: 'docs/LINODE_AUTOMATION_GUIDE.md', type: 'file' },
        { name: 'Environment Setup', path: 'docs/ENVIRONMENT_SETUP.md', type: 'file' },
        { name: 'Docker Images', path: 'docs/DOCKER_IMAGES.md', type: 'file' },
      ]
    },
    {
      name: 'Quick References',
      path: 'quick',
      type: 'directory',
      children: [
        { name: 'Environment Quick Ref', path: 'docs/ENVIRONMENT_QUICK_REFERENCE.md', type: 'file' },
        { name: 'Secrets Quick Ref', path: 'docs/SECRETS_QUICK_REFERENCE.md', type: 'file' },
        { name: 'Linode Quick Ref', path: 'docs/LINODE_AUTOMATION_QUICK_REFERENCE.md', type: 'file' },
      ]
    },
    {
      name: 'Archived Documentation',
      path: 'archived',
      type: 'directory',
      children: [
        { name: 'View Archived Docs', path: 'docs/archived/README.md', type: 'file' },
      ]
    }
  ];

// Fetch document content
  const fetchDocContent = async (path: string) => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch from the API endpoint
  const API_BASE = import.meta.env.VITE_API_URL || 'https://api.fkstrading.xyz';
      const response = await fetch(`${API_BASE}/api/${path}`);
      if (!response.ok) {
        throw new Error('Document not found');
      }
      const content = await response.text();
      setDocContent(content);
    } catch (err) {
      setError(`Failed to load document: ${err instanceof Error ? err.message : 'Unknown error'}`);
      // Placeholder content for demonstration
      setDocContent(`# ${path.split('/').pop()?.replace('.md', '')}\n\nDocument content would be loaded here from: ${path}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle document selection
  const handleDocSelect = (path: string) => {
    setSelectedDoc(path);
    fetchDocContent(path);
  };

  // Toggle folder expansion
  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedFolders(newExpanded);
  };

  // Render file tree
  const renderFileTree = (items: DocFile[], level: number = 0) => {
    return items.map((item) => {
      const isExpanded = expandedFolders.has(item.path);
      const isSelected = selectedDoc === item.path;

      if (item.type === 'directory') {
        return (
          <div key={item.path}>
            <div
              className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/10 rounded transition-colors`}
              style={{ paddingLeft: `${level * 1.5 + 0.75}rem` }}
              onClick={() => toggleFolder(item.path)}
            >
              <ChevronRight
                className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
              />
              <Folder className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium">{item.name}</span>
            </div>
            {isExpanded && item.children && (
              <div>{renderFileTree(item.children, level + 1)}</div>
            )}
          </div>
        );
      }

      return (
        <div
          key={item.path}
          className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/10 rounded transition-colors ${
            isSelected ? 'bg-white/20' : ''
          }`}
          style={{ paddingLeft: `${level * 1.5 + 2.25}rem` }}
          onClick={() => handleDocSelect(item.path)}
        >
          <FileText className="w-4 h-4 text-gray-400" />
          <span className="text-sm">{item.name}</span>
        </div>
      );
    });
  };

  // Load default document on mount
  useEffect(() => {
    handleDocSelect('docs/TRADING_GUIDE.md');
  }, []);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-80 bg-gray-900/50 border-r border-white/10 overflow-y-auto">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <Home className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold">Documentation</h2>
          </div>
          <div className="space-y-1">
            {renderFileTree(docStructure)}
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-8">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          )}
          
          {error && (
            <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-4 mb-4">
              <p className="text-red-400">{error}</p>
            </div>
          )}

          {!loading && !error && (
            <div className="prose prose-invert max-w-none">
              <ReactMarkdown
                components={{
                  // Custom styling for markdown elements
                  h1: ({ children }) => (
                    <h1 className="text-3xl font-bold mb-6 text-white">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-2xl font-semibold mb-4 mt-8 text-white">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-xl font-semibold mb-3 mt-6 text-white">{children}</h3>
                  ),
                  p: ({ children }) => (
                    <p className="mb-4 text-gray-300 leading-relaxed">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc pl-6 mb-4 space-y-2">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal pl-6 mb-4 space-y-2">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-gray-300">{children}</li>
                  ),
                  code: ({ node, ...props }: any) => {
                    const { inline, children } = props;
                    if (inline) {
                      return (
                        <code className="bg-gray-800 px-1.5 py-0.5 rounded text-sm text-blue-400">
                          {children}
                        </code>
                      );
                    }
                    return (
                      <pre className="bg-gray-900 p-4 rounded-lg overflow-x-auto">
                        <code className="text-gray-300">{children}</code>
                      </pre>
                    );
                  },
                  pre: ({ children }) => (
                    <pre className="mb-4">{children}</pre>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-blue-500 pl-4 italic text-gray-400">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto mb-4">
                      <table className="min-w-full divide-y divide-gray-700">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-2 bg-gray-800 text-left text-sm font-semibold text-white">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-2 text-sm text-gray-300 border-t border-gray-700">
                      {children}
                    </td>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      className="text-blue-400 hover:text-blue-300 underline"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {docContent}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocsViewer;
