import { 
  Target, 
  TrendingUp, 
  Building2, 
  Coins, 
  Home, 
  PiggyBank,
  CheckCircle,
  Clock,
  ArrowRight,
  Award,
  Calendar,
  Lock,
  Unlock
} from 'lucide-react';
import React, { useState } from 'react';

import { useGamification } from '../../context/GamificationContext';

const PhaseManager: React.FC = () => {
  const { userProgress, updatePhaseProgress, awardExperience } = useGamification();
  const [selectedPhase, setSelectedPhase] = useState<'phase_1' | 'phase_2'>('phase_1');

  if (!userProgress) {
    return <div className="p-6 text-white">Loading...</div>;
  }

  const phase1 = userProgress.phases.find(p => p.id === 'phase_1');
  const phase2 = userProgress.phases.find(p => p.id === 'phase_2');
  const currentPhase = userProgress.phases.find(p => p.id === selectedPhase);

  const calculatePhaseProgress = (phase: any) => {
    if (!phase) return 0;
    const totalObjectives = phase.objectives.length;
    const completedObjectives = phase.objectives.filter((obj: any) => obj.isCompleted).length;
    return totalObjectives > 0 ? (completedObjectives / totalObjectives) * 100 : 0;
  };

  const getObjectiveIcon = (category: string) => {
    switch (category) {
      case 'prop_firm': return Building2;
      case 'crypto': return Coins;
      case 'expenses': return Home;
      case 'accounts': return PiggyBank;
      case 'profit': return TrendingUp;
      default: return Target;
    }
  };

  const getObjectiveColor = (category: string) => {
    switch (category) {
      case 'prop_firm': return 'text-blue-400';
      case 'crypto': return 'text-yellow-400';
      case 'expenses': return 'text-green-400';
      case 'accounts': return 'text-purple-400';
      case 'profit': return 'text-orange-400';
      default: return 'text-gray-400';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'low': return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const phase1Progress = calculatePhaseProgress(phase1);
  const phase2Progress = calculatePhaseProgress(phase2);

  return (
    <div className="p-6 bg-gray-900 text-white space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Phase Management</h1>
          <p className="text-gray-400">Track your journey from trading novice to financial independence</p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-400">Current Phase</div>
          <div className="text-2xl font-bold text-blue-400">
            Phase {userProgress.currentPhase === 'phase_1' ? '1' : '2'}
          </div>
        </div>
      </div>

      {/* Phase Overview Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Phase 1 Card */}
        <div className={`rounded-lg p-6 border-2 transition-all cursor-pointer ${
          selectedPhase === 'phase_1'
            ? 'bg-blue-900/30 border-blue-500'
            : phase1?.isActive
              ? 'bg-gray-800 border-blue-500/50 hover:border-blue-500'
              : 'bg-gray-800 border-gray-700 hover:border-gray-600'
        }`} onClick={() => setSelectedPhase('phase_1')}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Building2 className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold">Phase 1: Foundation</h2>
                <p className="text-sm text-gray-400">Active Trading & Prop Firms</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {phase1?.isActive ? (
                <div className="px-3 py-1 bg-green-500/20 text-green-400 text-xs rounded-full border border-green-500/30">
                  ACTIVE
                </div>
              ) : phase1?.isCompleted ? (
                <CheckCircle className="w-6 h-6 text-green-400" />
              ) : (
                <Clock className="w-6 h-6 text-gray-400" />
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2 mb-4">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{phase1Progress.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-3">
              <div 
                className="bg-gradient-to-r from-blue-500 to-cyan-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${phase1Progress}%` }}
              ></div>
            </div>
          </div>

          {/* Key Objectives */}
          <div className="space-y-2">
            <h3 className="font-medium text-gray-300">Key Objectives:</h3>
            <div className="grid grid-cols-1 gap-2">
              {phase1?.objectives.slice(0, 3).map((objective, index) => {
                const IconComponent = getObjectiveIcon(objective.category);
                const progress = objective.target > 0 ? (objective.current / objective.target) * 100 : 0;
                
                return (
                  <div key={index} className="flex items-center justify-between text-sm">
                    <div className="flex items-center space-x-2">
                      <IconComponent className={`w-4 h-4 ${getObjectiveColor(objective.category)}`} />
                      <span>{objective.title}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-gray-400">{objective.current}/{objective.target}</span>
                      {objective.isCompleted && <CheckCircle className="w-4 h-4 text-green-400" />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Phase 2 Card */}
        <div className={`rounded-lg p-6 border-2 transition-all cursor-pointer ${
          selectedPhase === 'phase_2'
            ? 'bg-purple-900/30 border-purple-500'
            : phase2?.isActive
              ? 'bg-gray-800 border-purple-500/50 hover:border-purple-500'
              : 'bg-gray-800 border-gray-700 hover:border-gray-600 opacity-75'
        }`} onClick={() => phase2?.isActive && setSelectedPhase('phase_2')}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <PiggyBank className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold">Phase 2: Wealth Building</h2>
                <p className="text-sm text-gray-400">Long-term Investment Portfolio</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {phase2?.isActive ? (
                <div className="px-3 py-1 bg-green-500/20 text-green-400 text-xs rounded-full border border-green-500/30">
                  ACTIVE
                </div>
              ) : phase2?.isCompleted ? (
                <CheckCircle className="w-6 h-6 text-green-400" />
              ) : phase1?.isCompleted ? (
                <Unlock className="w-6 h-6 text-yellow-400" />
              ) : (
                <Lock className="w-6 h-6 text-gray-500" />
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2 mb-4">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{phase2?.isActive ? phase2Progress.toFixed(1) : '0.0'}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-3">
              <div 
                className="bg-gradient-to-r from-purple-500 to-pink-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${phase2?.isActive ? phase2Progress : 0}%` }}
              ></div>
            </div>
          </div>

          {/* Key Objectives */}
          <div className="space-y-2">
            <h3 className="font-medium text-gray-300">Key Objectives:</h3>
            {phase2?.isActive ? (
              <div className="grid grid-cols-1 gap-2">
                {phase2.objectives.slice(0, 3).map((objective, index) => {
                  const IconComponent = getObjectiveIcon(objective.category);
                  
                  return (
                    <div key={index} className="flex items-center justify-between text-sm">
                      <div className="flex items-center space-x-2">
                        <IconComponent className={`w-4 h-4 ${getObjectiveColor(objective.category)}`} />
                        <span>{objective.title}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-gray-400">{objective.current}/{objective.target}</span>
                        {objective.isCompleted && <CheckCircle className="w-4 h-4 text-green-400" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-500">
                Complete Phase 1 to unlock Phase 2 objectives
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detailed Phase View */}
      {currentPhase && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">{currentPhase.title}</h2>
            <div className="flex items-center space-x-2">
              <Calendar className="w-5 h-5 text-gray-400" />
              <span className="text-sm text-gray-400">
                {currentPhase.startedAt ? `Started ${new Date(currentPhase.startedAt).toLocaleDateString()}` : 'Not started'}
              </span>
            </div>
          </div>

          <p className="text-gray-400 mb-6">{currentPhase.description}</p>

          {/* Objectives Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {currentPhase.objectives.map((objective) => {
              const IconComponent = getObjectiveIcon(objective.category);
              const progress = objective.target > 0 ? (objective.current / objective.target) * 100 : 0;
              
              return (
                <div key={objective.id} className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <IconComponent className={`w-6 h-6 ${getObjectiveColor(objective.category)}`} />
                      <div>
                        <h3 className="font-bold">{objective.title}</h3>
                        <p className="text-sm text-gray-400">{objective.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className={`px-2 py-1 rounded text-xs border ${getPriorityColor(objective.priority)}`}>
                        {objective.priority}
                      </div>
                      {objective.isCompleted && <CheckCircle className="w-5 h-5 text-green-400" />}
                    </div>
                  </div>

                  {/* Progress */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Progress</span>
                      <span>{objective.current} / {objective.target} {objective.unit}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full transition-all duration-300 ${
                          objective.isCompleted 
                            ? 'bg-green-500' 
                            : selectedPhase === 'phase_1' 
                              ? 'bg-blue-500' 
                              : 'bg-purple-500'
                        }`}
                        style={{ width: `${Math.min(progress, 100)}%` }}
                      ></div>
                    </div>
                    <div className="text-xs text-gray-400">
                      {progress.toFixed(1)}% complete
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Requirements */}
          <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
            <h3 className="text-lg font-bold mb-4 flex items-center">
              <Award className="w-5 h-5 text-yellow-400 mr-2" />
              Phase Requirements
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {currentPhase.requirements.map((requirement) => (
                <div key={requirement.id} className="flex items-center space-x-3">
                  {requirement.isCompleted ? (
                    <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                  ) : (
                    <Clock className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  )}
                  <span className={`text-sm ${requirement.isCompleted ? 'text-green-400' : 'text-gray-300'}`}>
                    {requirement.description}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Phase Transition */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold mb-4 flex items-center">
          <ArrowRight className="w-6 h-6 text-blue-400 mr-2" />
          Phase Progression
        </h3>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-8">
            {/* Phase 1 Status */}
            <div className="text-center">
              <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center ${
                phase1?.isCompleted 
                  ? 'border-green-500 bg-green-500/20' 
                  : phase1?.isActive 
                    ? 'border-blue-500 bg-blue-500/20' 
                    : 'border-gray-500 bg-gray-500/20'
              }`}>
                <Building2 className={`w-8 h-8 ${
                  phase1?.isCompleted ? 'text-green-400' : phase1?.isActive ? 'text-blue-400' : 'text-gray-400'
                }`} />
              </div>
              <div className="mt-2 text-sm font-medium">Phase 1</div>
              <div className="text-xs text-gray-400">
                {phase1?.isCompleted ? 'Completed' : phase1?.isActive ? 'Active' : 'Pending'}
              </div>
            </div>

            {/* Arrow */}
            <ArrowRight className="w-8 h-8 text-gray-400" />

            {/* Phase 2 Status */}
            <div className="text-center">
              <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center ${
                phase2?.isCompleted 
                  ? 'border-green-500 bg-green-500/20' 
                  : phase2?.isActive 
                    ? 'border-purple-500 bg-purple-500/20' 
                    : 'border-gray-500 bg-gray-500/20'
              }`}>
                <PiggyBank className={`w-8 h-8 ${
                  phase2?.isCompleted ? 'text-green-400' : phase2?.isActive ? 'text-purple-400' : 'text-gray-400'
                }`} />
              </div>
              <div className="mt-2 text-sm font-medium">Phase 2</div>
              <div className="text-xs text-gray-400">
                {phase2?.isCompleted ? 'Completed' : phase2?.isActive ? 'Active' : 'Locked'}
              </div>
            </div>
          </div>

          {/* Current Status */}
          <div className="text-right">
            <div className="text-lg font-bold">
              Current Focus: {userProgress.currentPhase === 'phase_1' ? 'Active Trading' : 'Wealth Building'}
            </div>
            <div className="text-sm text-gray-400">
              {userProgress.currentPhase === 'phase_1' 
                ? 'Building prop firm portfolio and covering expenses' 
                : 'Diversifying investments for long-term growth'
              }
            </div>
            <div className="mt-2">
              {!phase2?.isActive && phase1Progress >= 80 && (
                <button 
                  onClick={() => awardExperience('PHASE_2_UNLOCKED')}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm transition-colors"
                >
                  Unlock Phase 2
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PhaseManager;
