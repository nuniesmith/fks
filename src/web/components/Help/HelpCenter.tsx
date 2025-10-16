import {
  HelpCircle,
  BookOpen,
  MessageCircle,
  Video,
  Download,
  ExternalLink,
  Search,
  ChevronRight,
  Mail,
  Clock,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import React, { useState } from 'react';


interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  helpful: number;
  notHelpful: number;
}

interface Tutorial {
  id: string;
  title: string;
  description: string;
  duration: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  videoUrl?: string;
}

const HelpCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'faq' | 'tutorials' | 'guides' | 'contact'>('faq');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const faqs: FAQ[] = [
    {
      id: '1',
      question: 'How do I switch between simulated and live trading?',
      answer: 'You can switch between simulated and live trading modes from the Trading Interface. Click the "Switch to Live/Simulation" button in the top right corner. Live trading requires enabled accounts in the Accounts page.',
      category: 'trading',
      helpful: 45,
      notHelpful: 2
    },
    {
      id: '2',
      question: 'What is the difference between prop firm and personal accounts?',
      answer: 'Prop firm accounts are funded by proprietary trading firms with specific rules and profit sharing. Personal accounts use your own capital. Prop firm accounts are typically used for active trading strategies while personal accounts are better for long-term investments.',
      category: 'accounts',
      helpful: 38,
      notHelpful: 5
    },
    {
      id: '3',
      question: 'How do I create and test a trading strategy?',
      answer: 'Use the Strategy Development section to create new strategies. You can backtest them using historical data, then deploy to simulation mode for live testing before applying to real accounts.',
      category: 'strategies',
      helpful: 52,
      notHelpful: 1
    },
    {
      id: '4',
      question: 'What risk management features are available?',
      answer: 'FKS includes max drawdown limits, position sizing controls, stop-loss enforcement, and automated risk monitoring across all accounts. Configure these in your Profile settings.',
      category: 'risk',
      helpful: 41,
      notHelpful: 3
    }
  ];

  const tutorials: Tutorial[] = [
    {
      id: '1',
      title: 'Getting Started with FKS Trading',
      description: 'Complete walkthrough of the platform basics',
      duration: '15 min',
      difficulty: 'beginner'
    },
    {
      id: '2',
      title: 'Setting Up Your First Trading Strategy',
      description: 'Learn how to create and deploy automated strategies',
      duration: '25 min',
      difficulty: 'intermediate'
    },
    {
      id: '3',
      title: 'Advanced Risk Management',
      description: 'Master risk controls and portfolio management',
      duration: '20 min',
      difficulty: 'advanced'
    },
    {
      id: '4',
      title: 'Using Multiple Accounts Effectively',
      description: 'Best practices for managing prop firm and personal accounts',
      duration: '18 min',
      difficulty: 'intermediate'
    }
  ];

  const categories = [
    { id: 'all', label: 'All Categories' },
    { id: 'trading', label: 'Trading' },
    { id: 'accounts', label: 'Accounts' },
    { id: 'strategies', label: 'Strategies' },
    { id: 'risk', label: 'Risk Management' },
    { id: 'technical', label: 'Technical Issues' }
  ];

  const filteredFAQs = faqs.filter(faq => {
    const matchesSearch = faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         faq.answer.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || faq.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'text-green-400 bg-green-500/20';
      case 'intermediate': return 'text-yellow-400 bg-yellow-500/20';
      case 'advanced': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const handleFeedback = (faqId: string, isHelpful: boolean) => {
    // Handle feedback submission
    console.log(`FAQ ${faqId} marked as ${isHelpful ? 'helpful' : 'not helpful'}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Help Center</h1>
            <p className="text-gray-400">Get support and learn how to use FKS Trading effectively</p>
          </div>
          
          <div className="flex items-center space-x-4">
            <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors">
              <MessageCircle className="w-4 h-4" />
              <span>Live Chat</span>
            </button>
            <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
              <Mail className="w-4 h-4" />
              <span>Contact Support</span>
            </button>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search for help topics, guides, or tutorials..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex border-b border-gray-700">
          {[
            { id: 'faq', label: 'FAQ', icon: HelpCircle },
            { id: 'tutorials', label: 'Video Tutorials', icon: Video },
            { id: 'guides', label: 'User Guides', icon: BookOpen },
            { id: 'contact', label: 'Contact Support', icon: MessageCircle }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex-1 flex items-center justify-center space-x-2 px-6 py-4 font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'faq' && (
            <div className="space-y-6">
              {/* Category Filter */}
              <div className="flex flex-wrap gap-2">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    onClick={() => setSelectedCategory(category.id)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      selectedCategory === category.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {category.label}
                  </button>
                ))}
              </div>

              {/* FAQ List */}
              <div className="space-y-4">
                {filteredFAQs.map((faq) => (
                  <div key={faq.id} className="bg-gray-700/30 rounded-lg border border-gray-600">
                    <div className="p-4">
                      <div className="flex items-start justify-between">
                        <h3 className="text-white font-medium pr-4">{faq.question}</h3>
                        <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                      </div>
                      <p className="text-gray-400 mt-2 text-sm">{faq.answer}</p>
                      
                      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-600">
                        <div className="flex items-center space-x-4 text-sm text-gray-400">
                          <span className="capitalize">{faq.category}</span>
                        </div>
                        
                        <div className="flex items-center space-x-4">
                          <span className="text-sm text-gray-400">Was this helpful?</span>
                          <button
                            onClick={() => handleFeedback(faq.id, true)}
                            className="flex items-center space-x-1 text-green-400 hover:text-green-300 transition-colors"
                          >
                            <ThumbsUp className="w-4 h-4" />
                            <span className="text-sm">{faq.helpful}</span>
                          </button>
                          <button
                            onClick={() => handleFeedback(faq.id, false)}
                            className="flex items-center space-x-1 text-red-400 hover:text-red-300 transition-colors"
                          >
                            <ThumbsDown className="w-4 h-4" />
                            <span className="text-sm">{faq.notHelpful}</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'tutorials' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {tutorials.map((tutorial) => (
                  <div key={tutorial.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h3 className="text-white font-medium mb-1">{tutorial.title}</h3>
                        <p className="text-gray-400 text-sm">{tutorial.description}</p>
                      </div>
                      <Video className="w-6 h-6 text-blue-400 flex-shrink-0 ml-3" />
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="flex items-center space-x-1 text-gray-400 text-sm">
                          <Clock className="w-4 h-4" />
                          <span>{tutorial.duration}</span>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getDifficultyColor(tutorial.difficulty)}`}>
                          {tutorial.difficulty}
                        </span>
                      </div>
                      
                      <button className="flex items-center space-x-1 text-blue-400 hover:text-blue-300 transition-colors">
                        <span className="text-sm">Watch</span>
                        <ExternalLink className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'guides' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { title: 'Platform Overview', description: 'Complete guide to FKS features', pages: 12 },
                  { title: 'Trading Strategies', description: 'How to develop winning strategies', pages: 24 },
                  { title: 'Risk Management', description: 'Protect your capital effectively', pages: 16 },
                  { title: 'Account Setup', description: 'Connect and configure accounts', pages: 8 },
                  { title: 'API Integration', description: 'Technical integration guide', pages: 20 },
                  { title: 'Troubleshooting', description: 'Common issues and solutions', pages: 14 }
                ].map((guide, index) => (
                  <div key={index} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                    <div className="flex items-start justify-between mb-3">
                      <BookOpen className="w-6 h-6 text-green-400" />
                      <span className="text-xs text-gray-400">{guide.pages} pages</span>
                    </div>
                    
                    <h3 className="text-white font-medium mb-1">{guide.title}</h3>
                    <p className="text-gray-400 text-sm mb-3">{guide.description}</p>
                    
                    <div className="flex items-center space-x-2">
                      <button className="flex items-center space-x-1 text-blue-400 hover:text-blue-300 transition-colors text-sm">
                        <span>Read Online</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                      <button className="flex items-center space-x-1 text-gray-400 hover:text-white transition-colors text-sm">
                        <Download className="w-3 h-3" />
                        <span>PDF</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'contact' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-6">
                <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center space-x-3 mb-3">
                    <MessageCircle className="w-6 h-6 text-blue-400" />
                    <h3 className="text-white font-medium">Live Chat Support</h3>
                  </div>
                  <p className="text-gray-400 text-sm mb-3">
                    Get instant help from our support team during business hours.
                  </p>
                  <div className="flex items-center space-x-2 text-sm text-green-400 mb-3">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                    <span>Online now</span>
                  </div>
                  <button className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors">
                    Start Chat
                  </button>
                </div>
                
                <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center space-x-3 mb-3">
                    <Mail className="w-6 h-6 text-green-400" />
                    <h3 className="text-white font-medium">Email Support</h3>
                  </div>
                  <p className="text-gray-400 text-sm mb-3">
                    Send us a detailed message and we'll respond within 24 hours.
                  </p>
                  <p className="text-gray-400 text-sm mb-3">
                    support@fkstrading.xyz
                  </p>
                  <button className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
                    Send Email
                  </button>
                </div>
              </div>
              
              <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                <h3 className="text-white font-medium mb-4">Submit a Support Ticket</h3>
                
                <form className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Subject
                    </label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                      placeholder="Brief description of your issue"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Category
                    </label>
                    <select className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500">
                      <option>Technical Issue</option>
                      <option>Account Problem</option>
                      <option>Trading Question</option>
                      <option>Feature Request</option>
                      <option>Other</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Priority
                    </label>
                    <select className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500">
                      <option>Low</option>
                      <option>Medium</option>
                      <option>High</option>
                      <option>Critical</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Description
                    </label>
                    <textarea
                      rows={4}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                      placeholder="Please provide as much detail as possible..."
                    />
                  </div>
                  
                  <button
                    type="submit"
                    className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                  >
                    Submit Ticket
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Support Hours */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Clock className="w-5 h-5 text-blue-400" />
            <div>
              <h3 className="text-white font-medium">Support Hours</h3>
              <p className="text-gray-400 text-sm">Monday - Friday: 9:00 AM - 6:00 PM EST</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-green-400">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            <span className="text-sm">Currently Available</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HelpCenter;
