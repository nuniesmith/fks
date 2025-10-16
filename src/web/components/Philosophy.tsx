import { Code, Target, TrendingUp, Shield } from 'lucide-react';
import React from 'react';

const Philosophy: React.FC = () => {
  const principles = [
    {
      title: 'Edge-Driven Approach',
      description: 'Only trade setups with a statistically proven edge',
      icon: <Target className="w-6 h-6 text-blue-400" />,
      details: 'Every trade must be backed by data-driven analysis and historical performance metrics.'
    },
    {
      title: 'Probabilistic Mindset',
      description: 'Accept that any single trade can lose; focus on long-term edge',
      icon: <TrendingUp className="w-6 h-6 text-green-400" />,
      details: 'Think in probabilities, not certainties. Success comes from consistent application of profitable strategies.'
    },
    {
      title: 'Process Over Outcome',
      description: 'Judge decisions by adherence to process, not individual results',
      icon: <Code className="w-6 h-6 text-purple-400" />,
      details: 'Focus on executing the system correctly. Good process leads to good outcomes over time.'
    },
    {
      title: 'Sustainable Growth',
      description: 'Target consistent compounding rather than outsized gains',
      icon: <Shield className="w-6 h-6 text-orange-400" />,
      details: 'Protect capital above all else. Steady, consistent returns compound to extraordinary results.'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Code className="w-8 h-8 mr-3 text-purple-400" />
          Trading Philosophy
        </h1>
        <p className="text-gray-400">Core principles that guide the FKS Trading Systems</p>
      </div>

      {/* Philosophy Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {principles.map((principle, index) => (
          <div key={index} className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-gray-600 transition-colors">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                {principle.icon}
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-semibold text-white mb-2">{principle.title}</h3>
                <p className="text-gray-300 mb-3">{principle.description}</p>
                <p className="text-gray-400 text-sm">{principle.details}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Core Values */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Core Values</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-400 mb-2">Discipline</div>
            <div className="text-sm text-gray-400">Stick to the plan regardless of emotions</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-400 mb-2">Patience</div>
            <div className="text-sm text-gray-400">Wait for high-quality setups</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-purple-400 mb-2">Adaptation</div>
            <div className="text-sm text-gray-400">Evolve with changing market conditions</div>
          </div>
        </div>
      </div>

      {/* Implementation */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Implementation in FKS</h2>
        <div className="space-y-4">
          <div className="flex items-start space-x-3">
            <div className="w-2 h-2 bg-blue-400 rounded-full mt-2"></div>
            <div>
              <div className="text-white font-medium">Automated Signal Generation</div>
              <div className="text-gray-400 text-sm">Remove emotional decision-making from signal identification</div>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-2 h-2 bg-green-400 rounded-full mt-2"></div>
            <div>
              <div className="text-white font-medium">Risk Management Integration</div>
              <div className="text-gray-400 text-sm">Built-in position sizing and stop-loss protocols</div>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-2 h-2 bg-purple-400 rounded-full mt-2"></div>
            <div>
              <div className="text-white font-medium">Performance Tracking</div>
              <div className="text-gray-400 text-sm">Continuous monitoring of system performance and edge validation</div>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-2 h-2 bg-orange-400 rounded-full mt-2"></div>
            <div>
              <div className="text-white font-medium">Market Regime Awareness</div>
              <div className="text-gray-400 text-sm">Adapt strategies based on current market conditions</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Philosophy;
