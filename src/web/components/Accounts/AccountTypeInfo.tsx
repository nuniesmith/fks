import { Shield, PiggyBank, TrendingUp, Building, Globe, Settings, AlertCircle, Info } from 'lucide-react';
import React from 'react';

import { ACCOUNT_TYPES } from '../../types';

import type { AccountType} from '../../types';

interface AccountTypeInfoProps {
  type: AccountType;
  showDetails?: boolean;
  className?: string;
}

const AccountTypeInfo: React.FC<AccountTypeInfoProps> = ({ 
  type, 
  showDetails = false, 
  className = "" 
}) => {
  const accountInfo = ACCOUNT_TYPES[type];
  
  const getIcon = () => {
    switch (accountInfo.category) {
      case 'retirement': return <Shield className="w-4 h-4" />;
      case 'tax-free': return <PiggyBank className="w-4 h-4" />;
      case 'taxable': return <TrendingUp className="w-4 h-4" />;
      case 'corporate': return <Building className="w-4 h-4" />;
      case 'specialized':
        if (type === 'prop-firm') return <TrendingUp className="w-4 h-4" />;
        if (type === 'fx-cfd') return <Globe className="w-4 h-4" />;
        return <Settings className="w-4 h-4" />;
      case 'demo': return <Settings className="w-4 h-4" />;
      default: return <Settings className="w-4 h-4" />;
    }
  };

  const getColor = () => {
    switch (accountInfo.category) {
      case 'retirement': return 'text-purple-400 bg-purple-500/20 border-purple-500/30';
      case 'tax-free': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'taxable': return 'text-blue-400 bg-blue-500/20 border-blue-500/30';
      case 'corporate': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'specialized': 
        if (type === 'prop-firm') return 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30';
        if (type === 'fx-cfd') return 'text-red-400 bg-red-500/20 border-red-500/30';
        return 'text-indigo-400 bg-indigo-500/20 border-indigo-500/30';
      case 'demo': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      default: return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
    }
  };

  if (!showDetails) {
    return (
      <div className={`inline-flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium border ${getColor()} ${className}`}>
        {getIcon()}
        <span>{accountInfo.displayName}</span>
      </div>
    );
  }

  return (
    <div className={`p-3 rounded-lg border ${getColor()} ${className}`}>
      <div className="flex items-center space-x-2 mb-2">
        {getIcon()}
        <span className="font-medium">{accountInfo.displayName}</span>
      </div>
      
      <p className="text-sm opacity-90 mb-3">{accountInfo.description}</p>
      
      <div className="space-y-1 text-xs">
        <div className="flex items-center space-x-2">
          {accountInfo.taxAdvantaged ? (
            <div className="flex items-center space-x-1 text-green-400">
              <Shield className="w-3 h-3" />
              <span>Tax Advantaged</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1 text-gray-400">
              <Info className="w-3 h-3" />
              <span>Taxable</span>
            </div>
          )}
        </div>
        
        {accountInfo.contributionLimits && (
          <div className="flex items-center space-x-1 text-blue-400">
            <AlertCircle className="w-3 h-3" />
            <span>Has contribution limits</span>
          </div>
        )}
        
        {accountInfo.withdrawalRestrictions && (
          <div className="flex items-center space-x-1 text-yellow-400">
            <AlertCircle className="w-3 h-3" />
            <span>Withdrawal restrictions</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default AccountTypeInfo;
