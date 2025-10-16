import { Target, CheckCircle, Clock, Award } from 'lucide-react';
import SectionHeader from '@layout/SectionHeader';
import React from 'react';

import { useMilestones } from '../../context/MilestoneContext';

const MilestoneTracker: React.FC = () => {
  const { 
    availableMilestones, 
    userProgress, 
    getActiveMilestones, 
    getCompletedMilestones,
    getNextPriorityMilestone,
    completeMilestone,
  updateMilestoneProgress,
  updateMilestoneRequirement,
  calculateTaxOptimizationScore,
  getCanadianTaxSavings
  } = useMilestones();

  const activeMilestones = getActiveMilestones();
  const completedMilestones = getCompletedMilestones();
  const nextPriorityMilestone = getNextPriorityMilestone();

  // Pending docs panel ref for smooth scroll
  const pendingPanelRef = React.useRef<HTMLDivElement | null>(null);
  const taxScore = calculateTaxOptimizationScore();
  const estSavings = getCanadianTaxSavings();
  const expenseCoverage = userProgress.financialSnapshot?.expenseCoverage ?? 0;

  // Simple modal state for attaching evidence
  const [attachOpen, setAttachOpen] = React.useState(false);
  const [attachMilestoneId, setAttachMilestoneId] = React.useState<string | null>(null);
  const [attachRequirementId, setAttachRequirementId] = React.useState<string | null>(null);
  const [attachLink, setAttachLink] = React.useState('');
  const [attachNotes, setAttachNotes] = React.useState('');
  const [attachExisting, setAttachExisting] = React.useState<string[]>([]);

  // Filters
  const [showPendingDocsOnly, setShowPendingDocsOnly] = React.useState(false);
  const [priorityFilter, setPriorityFilter] = React.useState<'all' | 'critical' | 'high' | 'medium' | 'low'>('all');

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'high': return 'text-orange-600 bg-orange-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-green-600 bg-green-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'prop_firm_scaling': return '🏢';
      case 'expense_coverage': return '💰';
      case 'tax_optimization': return '🇨🇦';
      case 'long_term_wealth': return '🏗️';
      case 'strategy_development': return '🧠';
      case 'profit_tracking': return '📈';
      case 'business_setup': return '🏪';
      default: return '🎯';
    }
  };

  const handleTestComplete = (milestoneId: string) => {
    completeMilestone(milestoneId);
  };

  const handleTestProgress = (milestoneId: string, progress: number) => {
    updateMilestoneProgress(milestoneId, progress);
  };

  const markRequirement = (milestoneId: string, requirementId: string) => {
    updateMilestoneRequirement(milestoneId, requirementId, { isCompleted: true, current: true });
  };

  const openAttachModal = (
    milestoneId: string,
    requirementId: string,
    currentEvidence?: string[],
    currentNotes?: string
  ) => {
    setAttachMilestoneId(milestoneId);
    setAttachRequirementId(requirementId);
    setAttachExisting(currentEvidence || []);
    setAttachLink('');
    setAttachNotes(currentNotes || '');
    setAttachOpen(true);
  };

  const saveAttachment = () => {
    if (!attachMilestoneId || !attachRequirementId) return;
  const trimmed = attachLink.trim();
  const newEvidence = trimmed ? [...attachExisting, trimmed] : [...attachExisting];
  updateMilestoneRequirement(attachMilestoneId, attachRequirementId, { evidence: newEvidence, notes: attachNotes });
    setAttachOpen(false);
  };

  // Compute pending document uploads count
  const pendingDocsCount = availableMilestones.reduce((acc, m) => {
    const reqs = m.requirements || [];
    return acc + reqs.filter(r => r.verificationMethod === 'document_upload' && !r.isCompleted).length;
  }, 0);

  const pendingDocsItems = React.useMemo(() => {
    const items: Array<{ milestoneId: string; milestoneTitle: string; requirementId: string; requirementDesc: string; evidence?: string[]; notes?: string }>[] = [] as any;
    const flat: Array<{ milestoneId: string; milestoneTitle: string; requirementId: string; requirementDesc: string; evidence?: string[]; notes?: string }> = [];
    availableMilestones.forEach((m) => {
      (m.requirements || []).forEach((r) => {
        if (r.verificationMethod === 'document_upload' && !r.isCompleted) {
          flat.push({
            milestoneId: m.id,
            milestoneTitle: m.title,
            requirementId: r.id,
            requirementDesc: r.description,
            evidence: r.evidence as string[] | undefined,
            notes: r.notes as string | undefined,
          });
        }
      });
    });
    return flat;
  }, [availableMilestones]);

  // Derived filtered active milestones
  const filteredActiveMilestones = React.useMemo(() => {
    let list = [...activeMilestones];
    if (showPendingDocsOnly) {
      list = list.filter(m => (m.requirements || []).some(r => r.verificationMethod === 'document_upload' && !r.isCompleted));
    }
    if (priorityFilter !== 'all') {
      list = list.filter(m => m.priority === priorityFilter);
    }
    return list;
  }, [activeMilestones, showPendingDocsOnly, priorityFilter]);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Milestone Tracker</h1>
          <p className="text-xl text-gray-600">
            Track your progress towards Canadian tax-optimized trading success
          </p>
          <div className="mt-3">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border" style={{ borderColor: '#e5e7eb' }}>
              <span className="text-lg" title="User Title">{userProgress.titleIcon}</span>
              <span className="text-sm" style={{ color: userProgress.titleColor }}>
                {userProgress.currentTitle}
              </span>
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 md:gap-6 mt-4">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-blue-600" />
              <span className="text-gray-700">
                <span className="font-semibold">{activeMilestones.length}</span> Active Milestones
              </span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <span className="text-gray-700">
                <span className="font-semibold">{completedMilestones.length}</span> Completed
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-yellow-600" />
              <span className="text-gray-700">
                <span className="font-semibold">{userProgress.totalXP.toLocaleString()}</span> Total XP
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => pendingPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                disabled={pendingDocsCount === 0}
                className={`inline-flex items-center gap-2 px-2 py-1 rounded-full text-xs ${pendingDocsCount > 0 ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
                title={pendingDocsCount > 0 ? 'Scroll to pending documents panel' : 'No pending documents'}
              >
                📎 Docs pending: <span className="font-semibold">{pendingDocsCount}</span>
              </button>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-green-100 text-green-700 text-xs" title="Estimated Canadian tax savings">
                🇨🇦 Savings: <span className="font-semibold">${estSavings.toLocaleString()}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-purple-100 text-purple-700 text-xs" title="Tax optimization score (0-100)">
                📊 Tax Score: <span className="font-semibold">{taxScore}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-amber-100 text-amber-700 text-xs" title="Monthly expense coverage">
                💸 Coverage: <span className="font-semibold">{Math.min(100, Math.max(0, Math.round(expenseCoverage)))}%</span>
              </span>
            </div>
          </div>
        </div>

        {/* Next Priority Milestone */}
        {nextPriorityMilestone && (
          <div className="mb-8 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <SectionHeader
                  icon={<span className="text-2xl">{getCategoryIcon(nextPriorityMilestone.category)}</span>}
                  title={`Next Priority: ${nextPriorityMilestone.title}`}
                  className="mb-2"
                  headingLevel={3}
                  trailing={<span className={`px-3 py-1 rounded-full text-sm font-medium ${getPriorityColor(nextPriorityMilestone.priority)}`}>{nextPriorityMilestone.priority.toUpperCase()}</span>}
                />
                <p className="text-blue-800 mb-4">{nextPriorityMilestone.description}</p>
                
                {/* Progress */}
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-blue-700 font-medium">
                      Progress: {nextPriorityMilestone.current}/{nextPriorityMilestone.target} {nextPriorityMilestone.unit}
                    </span>
                    <span className="text-sm text-blue-600">
                      +{nextPriorityMilestone.xpReward} XP
                    </span>
                  </div>
                  <div className="bg-blue-200 rounded-full h-3">
                    <div 
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min((nextPriorityMilestone.current / nextPriorityMilestone.target) * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Canadian Tax Benefit */}
                {nextPriorityMilestone.canadianTaxBenefit && (
                  <div className="bg-green-100 border border-green-200 rounded-lg p-3">
                    <p className="text-green-800 text-sm">
                      <span className="font-semibold">🇨🇦 Tax Benefit:</span> {nextPriorityMilestone.canadianTaxBenefit}
                    </p>
                  </div>
                )}

                {/* Requirements */}
                {nextPriorityMilestone.requirements && nextPriorityMilestone.requirements.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-blue-900 mb-2">Requirements</p>
                    <ul className="space-y-2">
                      {nextPriorityMilestone.requirements.map((req) => (
                        <li key={req.id} className="flex items-center justify-between text-sm bg-white/50 border border-blue-200 rounded px-2 py-1">
                          <span className="text-blue-900 flex-1 pr-2">{req.description}</span>
                          <span className={`mr-2 ${req.isCompleted ? 'text-green-600' : 'text-blue-700'}`}>
                            {req.isCompleted ? 'Done' : 'Pending'}
                          </span>
                              {req.evidence && req.evidence.length > 0 && (
                            <span className="text-xs text-blue-900 mr-2" title="Evidence attached">📎 {req.evidence.length}</span>
                          )}
                          {(req.verificationMethod === 'manual' || req.verificationMethod === 'document_upload') && (
                            <div className="flex items-center gap-2">
                              {!req.isCompleted && (
                                <button
                                  onClick={() => markRequirement(nextPriorityMilestone.id, req.id)}
                                  className="px-2 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs"
                                >
                                  Mark Done
                                </button>
                              )}
                              {req.verificationMethod === 'document_upload' && (
                                    <button
                                      onClick={() => openAttachModal(nextPriorityMilestone.id, req.id, req.evidence as string[] | undefined, req.notes as string | undefined)}
                                      className="text-blue-600 hover:underline text-xs"
                                      title="Attach a link or note"
                                    >
                                      Attach
                                    </button>
                              )}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              
              {/* Test Actions (Development) */}
              <div className="ml-6 space-y-2">
                <button
                  onClick={() => handleTestProgress(nextPriorityMilestone.id, nextPriorityMilestone.current + 1)}
                  className="block w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                >
                  +1 Progress
                </button>
                <button
                  onClick={() => handleTestComplete(nextPriorityMilestone.id)}
                  className="block w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                >
                  Complete
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Milestone Categories */}
        <div className="grid gap-8">
          {/* Pending Documents Panel */}
          {pendingDocsItems.length > 0 && (
            <div ref={pendingPanelRef} className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <SectionHeader title={`Pending Document Uploads (${pendingDocsItems.length})`} titleClassName="text-base font-semibold text-blue-900" dense className="mb-0" />
                <span className="text-xs text-blue-700">Attach links/notes, then mark done</span>
              </div>
              <ul className="space-y-2">
                {pendingDocsItems.map((item) => (
                  <li key={`${item.milestoneId}:${item.requirementId}`} className="flex items-center justify-between bg-white rounded border border-blue-200 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="text-blue-900 font-medium truncate">{item.milestoneTitle}</p>
                      <p className="text-blue-800 truncate">{item.requirementDesc}</p>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      {item.evidence && item.evidence.length > 0 && (
                        <span className="text-xs text-blue-900" title="Evidence attached">📎 {item.evidence.length}</span>
                      )}
                      <button
                        onClick={() => openAttachModal(item.milestoneId, item.requirementId, item.evidence, item.notes)}
                        className="text-blue-700 hover:underline text-xs"
                      >
                        Attach
                      </button>
                      <button
                        onClick={() => markRequirement(item.milestoneId, item.requirementId)}
                        className="px-2 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 text-xs"
                      >
                        Mark Done
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Active Milestones */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <SectionHeader
              icon={<Clock className="h-6 w-6 text-orange-600" />}
              title={`Active Milestones (${filteredActiveMilestones.length})`}
              headingLevel={2}
              titleClassName="text-2xl font-bold text-gray-900"
              className="mb-6"
            />

            {/* Filters */}
            <div className="flex items-center gap-3 mb-4">
              <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={showPendingDocsOnly}
                  onChange={(e) => setShowPendingDocsOnly(e.target.checked)}
                />
                Pending docs only
              </label>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value as any)}
                className="px-2 py-1 border border-gray-300 rounded text-sm text-gray-700"
                title="Filter by priority"
              >
                <option value="all">All priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            
            {filteredActiveMilestones.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                🎉 Congratulations! You've completed all available milestones!
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredActiveMilestones.map((milestone) => (
                  <div key={milestone.id} className="border border-gray-200 rounded-lg p-5 hover:border-blue-300 transition-colors">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{getCategoryIcon(milestone.category)}</span>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(milestone.priority)}`}>
                          {milestone.priority}
                        </span>
                      </div>
                      <span className="text-sm text-blue-600 font-medium">+{milestone.xpReward} XP</span>
                    </div>
                    
                    <h4 className="font-semibold text-gray-900 mb-2">{milestone.title}</h4>
                    <p className="text-gray-600 text-sm mb-4">{milestone.description}</p>
                    
                    {/* Progress */}
                    <div className="mb-3">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs text-gray-500">
                          {milestone.current}/{milestone.target} {milestone.unit}
                        </span>
                        <span className="text-xs text-gray-500">
                          {Math.round((milestone.current / milestone.target) * 100)}%
                        </span>
                      </div>
                      <div className="bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${Math.min((milestone.current / milestone.target) * 100, 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* Canadian Tax Benefit */}
                    {milestone.canadianTaxBenefit && (
                      <div className="bg-green-50 border border-green-200 rounded p-2 mb-3">
                        <p className="text-green-800 text-xs">
                          <span className="font-medium">🇨🇦 Tax Benefit:</span> {milestone.canadianTaxBenefit}
                        </p>
                      </div>
                    )}

                    {/* Requirements List */}
                    {milestone.requirements && milestone.requirements.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs text-gray-600 font-medium mb-1">Requirements</p>
                        <ul className="space-y-1">
                          {milestone.requirements.map((req) => (
                            <li key={req.id} className="flex items-center justify-between text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1">
                              <span className="text-gray-700 flex-1 pr-2">
                                {req.description}
                                {/* Progress badge for numeric requirements */}
                                {req.type !== 'boolean' && typeof req.current === 'number' && typeof req.target === 'number' && (
                                  <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded bg-gray-200 text-gray-700">
                                    {req.current}/{req.target}{req.type === 'percentage' ? '%' : ''}
                                  </span>
                                )}
                              </span>
                              {/* Verification method tag */}
                              <span className="mr-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-600" title="Verification method">
                                {req.verificationMethod === 'document_upload' ? 'doc' : req.verificationMethod}
                              </span>
                              <span className={`mr-2 ${req.isCompleted ? 'text-green-600' : 'text-gray-500'}`}>
                                {req.isCompleted ? 'Done' : 'Pending'}
                              </span>
                              {req.evidence && req.evidence.length > 0 && (
                                <span className="text-xs text-gray-700 mr-2" title="Evidence attached">📎 {req.evidence.length}</span>
                              )}
                              {(req.verificationMethod === 'manual' || req.verificationMethod === 'document_upload') && (
                                <div className="flex items-center gap-2">
                                  {!req.isCompleted && (
                                    <button
                                      onClick={() => markRequirement(milestone.id, req.id)}
                                      className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                                    >
                                      Mark Done
                                    </button>
                                  )}
                                  {req.verificationMethod === 'document_upload' && (
                                    <button
                                      onClick={() => openAttachModal(milestone.id, req.id, req.evidence as string[] | undefined, req.notes as string | undefined)}
                                      className="text-blue-700 hover:underline text-xs"
                                    >
                                      {req.evidence && req.evidence.length > 0 ? 'Manage' : 'Attach'}
                                    </button>
                                  )}
                                </div>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Test Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleTestProgress(milestone.id, milestone.current + 1)}
                        className="flex-1 px-3 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200 transition-colors"
                      >
                        +1 Progress
                      </button>
                      <button
                        onClick={() => handleTestComplete(milestone.id)}
                        className="flex-1 px-3 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200 transition-colors"
                      >
                        Complete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Completed Milestones */}
          {completedMilestones.length > 0 && (
            <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
              <SectionHeader
                icon={<CheckCircle className="h-6 w-6 text-green-600" />}
                title={`Completed Milestones (${completedMilestones.length})`}
                headingLevel={2}
                titleClassName="text-2xl font-bold text-gray-900"
                className="mb-6"
              />
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {completedMilestones.map((milestone) => (
                  <div key={milestone.id} className="border border-green-200 bg-green-50 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{getCategoryIcon(milestone.category)}</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                    <h4 className="font-semibold text-green-900 mb-1">{milestone.title}</h4>
                    <p className="text-green-700 text-sm">+{milestone.xpReward} XP earned</p>
                    {milestone.completedAt && (
                      <p className="text-green-600 text-xs mt-1">
                        Completed: {new Date(milestone.completedAt).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Attach Evidence Modal */}
      {attachOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-4">
            <div className="mb-3">
              <h3 className="text-lg font-semibold text-gray-900">Attach Evidence</h3>
              <p className="text-sm text-gray-600">Paste a link (URL) to your document or note. This will be saved to the requirement.</p>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Link (URL)</label>
                <input
                  value={attachLink}
                  onChange={(e) => setAttachLink(e.target.value)}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Notes (optional)</label>
                <textarea
                  value={attachNotes}
                  onChange={(e) => setAttachNotes(e.target.value)}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                  rows={3}
                />
              </div>
              {attachExisting.length > 0 && (
                <div>
                  <p className="text-xs text-gray-600 mb-1">Existing attachments</p>
                  <ul className="space-y-1">
                    {attachExisting.map((evi, idx) => (
                      <li key={idx} className="flex items-center justify-between text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1">
                        <a className="text-blue-700 hover:underline truncate max-w-[220px]" href={evi} target="_blank" rel="noreferrer">
                          {evi}
                        </a>
                        <button
                          onClick={() => setAttachExisting(attachExisting.filter((_, i) => i !== idx))}
                          className="text-red-600 hover:underline"
                          title="Remove"
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setAttachOpen(false)} className="px-3 py-1 rounded border border-gray-300 text-gray-700 text-sm">Cancel</button>
              <button onClick={saveAttachment} className="px-3 py-1 rounded bg-blue-600 text-white text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MilestoneTracker;
