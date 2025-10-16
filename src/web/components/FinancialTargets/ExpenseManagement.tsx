import { Plus, Edit3, Trash2, Save, X, Home, Car, Utensils, Zap, Shield, CreditCard, Gamepad2, Heart, MoreHorizontal } from 'lucide-react';
import React, { useState } from 'react';

import type { ExpenseItem } from '../../types';

interface ExpenseFormProps {
  expense?: ExpenseItem;
  onSave: (expense: Omit<ExpenseItem, 'id'>) => void;
  onCancel: () => void;
}

const ExpenseForm: React.FC<ExpenseFormProps> = ({ expense, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    category: expense?.category || 'other' as const,
    name: expense?.name || '',
    amount: expense?.amount || 0,
    frequency: expense?.frequency || 'monthly' as const,
    isEssential: expense?.isEssential !== false,
    notes: expense?.notes || ''
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

  // Calculate monthly equivalent for comparison
  const getMonthlyEquivalent = (amount: number, frequency: string) => {
    switch (frequency) {
      case 'daily': return amount * 30;
      case 'weekly': return amount * 4.33;
      case 'monthly': return amount;
      case 'yearly': return amount / 12;
      default: return amount;
    }
  };

  const expenseCategories = [
    { id: 'housing', label: 'Housing & Rent', icon: Home },
    { id: 'food', label: 'Food & Groceries', icon: Utensils },
    { id: 'transportation', label: 'Transportation', icon: Car },
    { id: 'utilities', label: 'Utilities', icon: Zap },
    { id: 'insurance', label: 'Insurance', icon: Shield },
    { id: 'debt', label: 'Debt Payments', icon: CreditCard },
    { id: 'entertainment', label: 'Entertainment', icon: Gamepad2 },
    { id: 'healthcare', label: 'Healthcare', icon: Heart },
    { id: 'other', label: 'Other', icon: MoreHorizontal }
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">
            {expense ? 'Edit Expense' : 'Add New Expense'}
          </h3>
          <p className="text-gray-600 text-sm mt-1">
            Track your personal expenses to calculate accurate financial targets
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Category Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Expense Category *
            </label>
            <div className="grid grid-cols-3 gap-3">
              {expenseCategories.map(category => {
                const Icon = category.icon;
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, category: category.id as any })}
                    className={`p-3 border rounded-lg text-center transition-colors ${
                      formData.category === category.id
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <Icon className="h-6 w-6 mx-auto mb-1" />
                    <span className="text-xs font-medium">{category.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Basic Information */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Expense Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Rent, Groceries, Gas"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Frequency *
              </label>
              <select
                value={formData.frequency}
                onChange={(e) => setFormData({ ...formData, frequency: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
          </div>

          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Amount (CAD) *
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-gray-500">$</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="0.00"
                required
              />
            </div>
          </div>

          {/* Monthly Equivalent Display */}
          {formData.amount > 0 && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-700">
                <span className="font-medium">Monthly equivalent:</span> {' '}
                {formatCurrency(getMonthlyEquivalent(formData.amount, formData.frequency))}
              </p>
            </div>
          )}

          {/* Essential Toggle */}
          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              id="isEssential"
              checked={formData.isEssential}
              onChange={(e) => setFormData({ ...formData, isEssential: e.target.checked })}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="isEssential" className="text-sm font-medium text-gray-700">
              Essential Expense
              <span className="text-gray-500 block text-xs">
                Mark as essential if this expense is necessary for basic living
              </span>
            </label>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Notes (Optional)
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="Additional details about this expense..."
            />
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
              <span>{expense ? 'Update Expense' : 'Add Expense'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface ExpenseManagementProps {
  expenses: ExpenseItem[];
  onExpenseUpdate: (expenses: ExpenseItem[]) => void;
}

const ExpenseManagement: React.FC<ExpenseManagementProps> = ({ expenses, onExpenseUpdate }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseItem | null>(null);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };

  const getCategoryIcon = (category: string) => {
    const icons = {
      housing: Home,
      food: Utensils,
      transportation: Car,
      utilities: Zap,
      insurance: Shield,
      debt: CreditCard,
      entertainment: Gamepad2,
      healthcare: Heart,
      other: MoreHorizontal
    };
    return icons[category as keyof typeof icons] || MoreHorizontal;
  };

  const getCategoryColor = (category: string) => {
    const colors = {
      housing: 'text-blue-600 bg-blue-100',
      food: 'text-green-600 bg-green-100',
      transportation: 'text-purple-600 bg-purple-100',
      utilities: 'text-yellow-600 bg-yellow-100',
      insurance: 'text-red-600 bg-red-100',
      debt: 'text-orange-600 bg-orange-100',
      entertainment: 'text-pink-600 bg-pink-100',
      healthcare: 'text-indigo-600 bg-indigo-100',
      other: 'text-gray-600 bg-gray-100'
    };
    return colors[category as keyof typeof colors] || 'text-gray-600 bg-gray-100';
  };

  const getMonthlyEquivalent = (amount: number, frequency: string) => {
    switch (frequency) {
      case 'daily': return amount * 30;
      case 'weekly': return amount * 4.33;
      case 'monthly': return amount;
      case 'yearly': return amount / 12;
      default: return amount;
    }
  };

  const calculateTotals = () => {
    const monthlyTotal = expenses.reduce((total, expense) => 
      total + getMonthlyEquivalent(expense.amount, expense.frequency), 0
    );
    const essentialTotal = expenses
      .filter(expense => expense.isEssential)
      .reduce((total, expense) => 
        total + getMonthlyEquivalent(expense.amount, expense.frequency), 0
      );
    
    return { monthlyTotal, essentialTotal, nonEssentialTotal: monthlyTotal - essentialTotal };
  };

  const handleSaveExpense = (expenseData: Omit<ExpenseItem, 'id'>) => {
    if (editingExpense) {
      // Update existing expense
      const updatedExpenses = expenses.map(expense => 
        expense.id === editingExpense.id 
          ? { ...expense, ...expenseData }
          : expense
      );
      onExpenseUpdate(updatedExpenses);
    } else {
      // Create new expense
      const newExpense: ExpenseItem = {
        ...expenseData,
        id: Date.now().toString()
      };
      onExpenseUpdate([...expenses, newExpense]);
    }
    
    setShowForm(false);
    setEditingExpense(null);
  };

  const handleDeleteExpense = (expenseId: string) => {
    if (confirm('Are you sure you want to delete this expense?')) {
      const updatedExpenses = expenses.filter(expense => expense.id !== expenseId);
      onExpenseUpdate(updatedExpenses);
    }
  };

  const handleEditExpense = (expense: ExpenseItem) => {
    setEditingExpense(expense);
    setShowForm(true);
  };

  const totals = calculateTotals();
  const expensesByCategory = expenses.reduce((acc, expense) => {
    if (!acc[expense.category]) acc[expense.category] = [];
    acc[expense.category].push(expense);
    return acc;
  }, {} as Record<string, ExpenseItem[]>);

  return (
    <div className="space-y-6">
      {/* Header with Totals */}
      <div className="bg-white rounded-lg border p-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Personal Expenses</h2>
            <p className="text-gray-600">Track and categorize your monthly expenses</p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <Plus className="h-4 w-4" />
            <span>Add Expense</span>
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="text-sm font-medium text-blue-600">Total Monthly Expenses</div>
            <div className="text-2xl font-bold text-blue-900">{formatCurrency(totals.monthlyTotal)}</div>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="text-sm font-medium text-red-600">Essential Expenses</div>
            <div className="text-2xl font-bold text-red-900">{formatCurrency(totals.essentialTotal)}</div>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-sm font-medium text-green-600">Non-Essential</div>
            <div className="text-2xl font-bold text-green-900">{formatCurrency(totals.nonEssentialTotal)}</div>
          </div>
        </div>
      </div>

      {/* Expenses by Category */}
      {Object.entries(expensesByCategory).map(([category, categoryExpenses]) => {
        const Icon = getCategoryIcon(category);
        const categoryTotal = categoryExpenses.reduce((total, expense) => 
          total + getMonthlyEquivalent(expense.amount, expense.frequency), 0
        );

        return (
          <div key={category} className="bg-white rounded-lg border">
            <div className="p-4 border-b bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${getCategoryColor(category)}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 capitalize">
                      {category.replace('-', ' ')}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {categoryExpenses.length} {categoryExpenses.length === 1 ? 'expense' : 'expenses'}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-lg">{formatCurrency(categoryTotal)}</div>
                  <div className="text-sm text-gray-600">per month</div>
                </div>
              </div>
            </div>
            
            <div className="p-4">
              <div className="space-y-3">
                {categoryExpenses.map(expense => (
                  <div key={expense.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">{expense.name}</span>
                        {expense.isEssential && (
                          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full">
                            Essential
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-600">
                        {formatCurrency(expense.amount)} per {expense.frequency}
                        {expense.frequency !== 'monthly' && (
                          <span className="ml-2 text-gray-500">
                            ({formatCurrency(getMonthlyEquivalent(expense.amount, expense.frequency))} monthly)
                          </span>
                        )}
                      </div>
                      {expense.notes && (
                        <div className="text-sm text-gray-500 mt-1">{expense.notes}</div>
                      )}
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleEditExpense(expense)}
                        className="p-1 text-gray-500 hover:text-blue-600 transition-colors"
                      >
                        <Edit3 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteExpense(expense.id)}
                        className="p-1 text-gray-500 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })}

      {expenses.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg border">
          <Utensils className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Expenses Tracked Yet</h3>
          <p className="text-gray-600 mb-6">
            Start by adding your monthly expenses to calculate accurate financial targets
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add First Expense
          </button>
        </div>
      )}

      {/* Expense Form Modal */}
      {showForm && (
        <ExpenseForm
          expense={editingExpense || undefined}
          onSave={handleSaveExpense}
          onCancel={() => {
            setShowForm(false);
            setEditingExpense(null);
          }}
        />
      )}
    </div>
  );
};

export default ExpenseManagement;
