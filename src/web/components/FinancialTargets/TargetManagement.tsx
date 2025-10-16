import { Plus, Edit3, Trash2, Save, X, Calculator, TrendingUp } from 'lucide-react';
import React, { useState } from 'react';

import type { FinancialTarget } from '../../types';

interface TargetFormProps {
  target?: FinancialTarget;
  onSave: (target: Omit<FinancialTarget, 'id' | 'createdAt' | 'lastModified'>) => void;
  onCancel: () => void;
}

const TargetForm: React.FC<TargetFormProps> = ({ target, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: target?.name || '',
    description: target?.description || '',
    targetAmount: target?.targetAmount || 0,
    period: target?.period || 'daily' as const,
    category: target?.category || 'living-expenses' as const,
    priority: target?.priority || 'medium' as const,
    isActive: target?.isActive !== false
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };

  // Calculate annual equivalent for comparison
  const getAnnualEquivalent = (amount: number, period: string) => {
    switch (period) {
      case 'daily': return amount * 365;
      case 'weekly': return amount * 52;
      case 'monthly': return amount * 12;
      case 'yearly': return amount;
      default: return amount;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">
            {target ? 'Edit Financial Target' : 'Create New Financial Target'}
          </h3>
          <p className="text-gray-600 text-sm mt-1">
            Set up income targets to ensure you cover expenses and maintain trading capital
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Basic Information */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Daily Living Expenses"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Category *
              </label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="living-expenses">Living Expenses</option>
                <option value="trading-capital">Trading Capital</option>
                <option value="savings">Savings & Investment</option>
                <option value="emergency-fund">Emergency Fund</option>
                <option value="investment-goal">Investment Goal</option>
                <option value="custom">Custom</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="Brief description of this financial target..."
            />
          </div>

          {/* Amount and Period */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Amount (CAD) *
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-gray-500">$</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.targetAmount}
                  onChange={(e) => setFormData({ ...formData, targetAmount: parseFloat(e.target.value) || 0 })}
                  className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="0.00"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Period *
              </label>
              <select
                value={formData.period}
                onChange={(e) => setFormData({ ...formData, period: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
          </div>

          {/* Annual Equivalent Display */}
          {formData.targetAmount > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center space-x-2">
                <Calculator className="h-5 w-5 text-blue-600" />
                <span className="font-medium text-blue-900">Annual Equivalent</span>
              </div>
              <p className="text-blue-800 mt-1">
                {formatCurrency(formData.targetAmount)} per {formData.period} = {' '}
                <span className="font-bold">
                  {formatCurrency(getAnnualEquivalent(formData.targetAmount, formData.period))} per year
                </span>
              </p>
            </div>
          )}

          {/* Priority and Status */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Priority Level
              </label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="critical">Critical - Must achieve</option>
                <option value="high">High - Very important</option>
                <option value="medium">Medium - Important</option>
                <option value="low">Low - Nice to have</option>
              </select>
            </div>

            <div className="flex items-center space-x-3 pt-8">
              <input
                type="checkbox"
                id="isActive"
                checked={formData.isActive}
                onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="isActive" className="text-sm font-medium text-gray-700">
                Active Target
              </label>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 pt-6 border-t">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors flex items-center space-x-2"
            >
              <X className="h-4 w-4" />
              <span>Cancel</span>
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
            >
              <Save className="h-4 w-4" />
              <span>{target ? 'Update Target' : 'Create Target'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface TargetManagementProps {
  targets: FinancialTarget[];
  onTargetUpdate: (targets: FinancialTarget[]) => void;
}

const TargetManagement: React.FC<TargetManagementProps> = ({ targets, onTargetUpdate }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingTarget, setEditingTarget] = useState<FinancialTarget | null>(null);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'high': return 'text-orange-600 bg-orange-100';
      case 'medium': return 'text-blue-600 bg-blue-100';
      case 'low': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'living-expenses': return '🏠';
      case 'trading-capital': return '📈';
      case 'savings': return '💰';
      case 'emergency-fund': return '🛡️';
      case 'investment-goal': return '🎯';
      default: return '📋';
    }
  };

  const handleSaveTarget = (targetData: Omit<FinancialTarget, 'id' | 'createdAt' | 'lastModified'>) => {
    const now = new Date().toISOString();
    
    if (editingTarget) {
      // Update existing target
      const updatedTargets = targets.map(target => 
        target.id === editingTarget.id 
          ? { ...target, ...targetData, lastModified: now }
          : target
      );
      onTargetUpdate(updatedTargets);
    } else {
      // Create new target
      const newTarget: FinancialTarget = {
        ...targetData,
        id: Date.now().toString(),
        createdAt: now,
        lastModified: now
      };
      onTargetUpdate([...targets, newTarget]);
    }
    
    setShowForm(false);
    setEditingTarget(null);
  };

  const handleDeleteTarget = (targetId: string) => {
    if (confirm('Are you sure you want to delete this target?')) {
      const updatedTargets = targets.filter(target => target.id !== targetId);
      onTargetUpdate(updatedTargets);
    }
  };

  const handleEditTarget = (target: FinancialTarget) => {
    setEditingTarget(target);
    setShowForm(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Financial Targets</h2>
          <p className="text-gray-600">Manage your income targets to cover expenses and maintain capital</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="h-4 w-4" />
          <span>Add Target</span>
        </button>
      </div>

      {/* Targets List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {targets.map(target => (
          <div key={target.id} className="bg-white rounded-lg border p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">{getCategoryIcon(target.category)}</span>
                <div>
                  <h3 className="font-semibold text-gray-900">{target.name}</h3>
                  <p className="text-sm text-gray-600">{target.description}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(target.priority)}`}>
                  {target.priority}
                </span>
                <div className="flex space-x-1">
                  <button
                    onClick={() => handleEditTarget(target)}
                    className="p-1 text-gray-500 hover:text-blue-600 transition-colors"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteTarget(target.id)}
                    className="p-1 text-gray-500 hover:text-red-600 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Target Amount</span>
                <span className="font-bold text-xl">{formatCurrency(target.targetAmount)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Period</span>
                <span className="font-medium capitalize">{target.period}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Status</span>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  target.isActive ? 'text-green-600 bg-green-100' : 'text-gray-600 bg-gray-100'
                }`}>
                  {target.isActive ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {targets.length === 0 && (
        <div className="text-center py-12">
          <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Financial Targets Yet</h3>
          <p className="text-gray-600 mb-6">
            Create your first financial target to start tracking your income goals
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Create First Target
          </button>
        </div>
      )}

      {/* Target Form Modal */}
      {showForm && (
        <TargetForm
          target={editingTarget || undefined}
          onSave={handleSaveTarget}
          onCancel={() => {
            setShowForm(false);
            setEditingTarget(null);
          }}
        />
      )}
    </div>
  );
};

export default TargetManagement;
