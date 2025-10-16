import {
  BookOpen,
  Code,
  FileText,
  Search,
  Shield,
  AlertCircle,
  ExternalLink,
  Download,
  Clock,
  Tag
} from 'lucide-react';
import React, { useState } from 'react';

interface DocumentSection {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  lastUpdated: string;
  tags: string[];
  path?: string;
}

const Documentation: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const documentSections: DocumentSection[] = [
    {
      id: 'getting-started',
      title: 'Getting Started Guide',
      description: 'Complete setup and installation instructions for the FKS Trading Systems',
      icon: <BookOpen className="w-5 h-5" />,
      lastUpdated: '2024-01-15',
      tags: ['setup', 'installation', 'beginner'],
      path: '/docs/README.md'
    },
    {
      id: 'api-reference',
      title: 'API Reference',
      description: 'Complete API documentation for all endpoints and services',
      icon: <Code className="w-5 h-5" />,
      lastUpdated: '2024-01-20',
      tags: ['api', 'reference', 'endpoints'],
      path: '/docs/API_REFERENCE.md'
    },
    {
      id: 'development-guide',
      title: 'Development Guide',
      description: 'Guidelines for contributing to and extending the FKS system',
      icon: <FileText className="w-5 h-5" />,
      lastUpdated: '2024-01-18',
      tags: ['development', 'contributing', 'architecture'],
      path: '/docs/DEVELOPMENT_GUIDE.md'
    },
    {
      id: 'environment-setup',
      title: 'Environment Setup',
      description: 'Detailed instructions for setting up development and production environments',
      icon: <FileText className="w-5 h-5" />,
      lastUpdated: '2024-01-12',
      tags: ['environment', 'docker', 'deployment'],
      path: '/docs/ENVIRONMENT_SETUP.md'
    },
    {
      id: 'github-actions',
      title: 'GitHub Actions Guide',
      description: 'CI/CD pipeline configuration and deployment automation',
      icon: <FileText className="w-5 h-5" />,
      lastUpdated: '2024-01-16',
      tags: ['ci-cd', 'automation', 'deployment'],
      path: '/docs/GITHUB_ACTIONS_GUIDE.md'
    },
    {
      id: 'ninjatrader',
      title: 'NinjaTrader Integration',
      description: 'Complete guide for NinjaTrader 8 integration and strategy deployment',
      icon: <FileText className="w-5 h-5" />,
      lastUpdated: '2024-01-14',
      tags: ['ninjatrader', 'integration', 'trading'],
      path: '/docs/NINJATRADER_INTEGRATION_COMPLETE.md'
    },
    {
      id: 'rithmic',
      title: 'Rithmic Integration',
      description: 'Data feed integration and configuration for Rithmic API',
      icon: <FileText className="w-5 h-5" />,
      lastUpdated: '2024-01-13',
      tags: ['rithmic', 'data-feed', 'integration'],
      path: '/docs/RITHMIC_INTEGRATION_COMPLETE.md'
    },
    {
      id: 'secrets-management',
      title: 'Secrets Management',
      description: 'Secure handling of API keys, tokens, and sensitive configuration',
      icon: <Shield className="w-5 h-5" />,
      lastUpdated: '2024-01-17',
      tags: ['security', 'secrets', 'configuration'],
      path: '/docs/SECRETS.md'
    }
  ];

  const quickLinks = [
    {
      title: 'Architecture',
      description: 'High-level overview of system components',
      icon: <FileText className="w-4 h-4" />,
      path: '/docs/INDEX.md'
    },
    {
      title: 'Troubleshooting',
      description: 'Common issues and solutions',
      icon: <AlertCircle className="w-4 h-4" />,
      path: '/docs/TROUBLESHOOTING.md'
    },
    {
      title: 'Performance Tuning',
      description: 'Optimization guidelines',
      icon: <FileText className="w-4 h-4" />,
      path: '/docs/PERFORMANCE.md'
    }
  ];

  const categories = [
    { id: 'all', label: 'All Documentation' },
    { id: 'setup', label: 'Setup & Installation' },
    { id: 'development', label: 'Development' },
    { id: 'integration', label: 'Integrations' },
    { id: 'security', label: 'Security' },
    { id: 'deployment', label: 'Deployment' }
  ];

  const filteredSections = documentSections.filter(section => {
    const matchesSearch = searchTerm === '' || 
      section.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      section.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      section.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCategory = selectedCategory === 'all' || 
      section.tags.some(tag => tag.toLowerCase().includes(selectedCategory.toLowerCase()));

    return matchesSearch && matchesCategory;
  });

  const handleDocumentClick = (section: DocumentSection) => {
    // In a real implementation, this would navigate to the document
    console.log(`Opening document: ${section.title}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <BookOpen className="w-8 h-8 mr-3 text-blue-400" />
              Documentation Hub
            </h1>
            <p className="text-gray-400">Comprehensive guides and references for the FKS Trading Systems</p>
          </div>
          <div className="flex items-center space-x-4">
            <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors">
              <Download className="w-4 h-4" />
              <span>Download All</span>
            </button>
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors">
              <ExternalLink className="w-4 h-4" />
              <span>View on GitHub</span>
            </button>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search documentation..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:outline-none"
            >
              {categories.map(category => (
                <option key={category.id} value={category.id}>
                  {category.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Quick Links</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {quickLinks.map((link, index) => (
            <button
              key={index}
              onClick={() => console.log(`Opening: ${link.title}`)}
              className="flex items-start space-x-3 p-4 bg-gray-900/50 hover:bg-gray-700 rounded-lg transition-colors text-left"
            >
              <div className="text-blue-400 mt-1">{link.icon}</div>
              <div>
                <div className="font-medium text-white">{link.title}</div>
                <div className="text-sm text-gray-400">{link.description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Documentation Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {filteredSections.map((section) => (
          <div
            key={section.id}
            className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-blue-500/50 transition-colors cursor-pointer"
            onClick={() => handleDocumentClick(section)}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="text-blue-400">{section.icon}</div>
              <div className="flex items-center text-xs text-gray-500">
                <Clock className="w-3 h-3 mr-1" />
                {section.lastUpdated}
              </div>
            </div>
            
            <h3 className="text-lg font-semibold text-white mb-2">{section.title}</h3>
            <p className="text-gray-400 text-sm mb-4 line-clamp-3">{section.description}</p>
            
            <div className="flex flex-wrap gap-2 mb-4">
              {section.tags.map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded border border-blue-500/30"
                >
                  <Tag className="w-3 h-3 mr-1" />
                  {tag}
                </span>
              ))}
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">
                {section.path}
              </span>
              <ExternalLink className="w-4 h-4 text-gray-400" />
            </div>
          </div>
        ))}
      </div>

      {/* No Results */}
      {filteredSections.length === 0 && (
        <div className="bg-gray-800 rounded-lg p-12 border border-gray-700 text-center">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">No Documentation Found</h3>
          <p className="text-gray-400">
            Try adjusting your search terms or filter criteria to find relevant documentation.
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">Need Help?</h3>
            <p className="text-gray-400">Can't find what you're looking for? Check our support resources.</p>
          </div>
          <div className="flex items-center space-x-4">
            <button className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
              Contact Support
            </button>
            <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors">
              Report Issue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Documentation;
