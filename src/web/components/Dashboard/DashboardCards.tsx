import { TrendingUp, TrendingDown, DollarSign, BarChart3, Target } from 'lucide-react';
import React from 'react';

interface DashboardData {
  pnl: {
    value: number;
    change: number;
    percentage: number;
  };
  volume: {
    value: number;
    change: number;
    percentage: number;
  };
  win_rate: {
    value: number;
    change: number;
    percentage: number;
  };
  trades_today: number;
  active_positions: number;
  last_updated: string;
}

interface DashboardCardsProps {
  data: DashboardData;
  className?: string;
}

// Card wrapper component
const Card: React.FC<{ children: React.ReactNode; className?: string }> = ({ 
  children, 
  className = '' 
}) => (
  <div className={`bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg p-6 ${className}`}>
    {children}
  </div>
);

// Individual card components
const PnLCard: React.FC<{ data: DashboardData['pnl'] }> = ({ data }) => (
  <Card>
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-sm font-medium text-gray-400">Today's P&L</h3>
      <DollarSign className="w-4 h-4 text-gray-400" />
    </div>
    <div className="space-y-2">
      <div className="text-2xl font-bold text-white">
        ${data.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
      </div>
      <div className={`flex items-center text-sm ${
        data.change >= 0 ? 'text-green-400' : 'text-red-400'
      }`}>
        {data.change >= 0 ? (
          <TrendingUp className="w-4 h-4 mr-1" />
        ) : (
          <TrendingDown className="w-4 h-4 mr-1" />
        )}
        {data.change >= 0 ? '+' : ''}${data.change.toFixed(2)} ({data.percentage.toFixed(1)}%)
      </div>
    </div>
  </Card>
);

const VolumeCard: React.FC<{ data: DashboardData['volume'] }> = ({ data }) => (
  <Card>
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-sm font-medium text-gray-400">Volume Traded</h3>
      <BarChart3 className="w-4 h-4 text-gray-400" />
    </div>
    <div className="space-y-2">
      <div className="text-2xl font-bold text-white">
        ${(data.value / 1000000).toFixed(2)}M
      </div>
      <div className={`flex items-center text-sm ${
        data.change >= 0 ? 'text-green-400' : 'text-red-400'
      }`}>
        {data.change >= 0 ? (
          <TrendingUp className="w-4 h-4 mr-1" />
        ) : (
          <TrendingDown className="w-4 h-4 mr-1" />
        )}
        {data.change >= 0 ? '+' : ''}${(data.change / 1000).toFixed(0)}K ({data.percentage.toFixed(1)}%)
      </div>
    </div>
  </Card>
);

const WinRateCard: React.FC<{ data: DashboardData['win_rate'] }> = ({ data }) => (
  <Card>
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-sm font-medium text-gray-400">Win Rate</h3>
      <Target className="w-4 h-4 text-gray-400" />
    </div>
    <div className="space-y-2">
      <div className="text-2xl font-bold text-white">
        {data.value.toFixed(1)}%
      </div>
      <div className={`flex items-center text-sm ${
        data.change >= 0 ? 'text-green-400' : 'text-red-400'
      }`}>
        {data.change >= 0 ? (
          <TrendingUp className="w-4 h-4 mr-1" />
        ) : (
          <TrendingDown className="w-4 h-4 mr-1" />
        )}
        {data.change >= 0 ? '+' : ''}{data.change.toFixed(1)}% ({data.percentage.toFixed(1)}%)
      </div>
    </div>
  </Card>
);

const TradeStatsCard: React.FC<{ trades: number; positions: number }> = ({ trades, positions }) => (
  <Card>
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-medium text-gray-400">Trades Today</h3>
        </div>
        <div className="text-xl font-bold text-white">{trades}</div>
      </div>
      <div className="border-t border-gray-700 pt-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-medium text-gray-400">Active Positions</h3>
        </div>
        <div className="text-xl font-bold text-white">{positions}</div>
      </div>
    </div>
  </Card>
);

const DashboardCards: React.FC<DashboardCardsProps> = ({ data, className = '' }) => {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 ${className}`}>
      <PnLCard data={data.pnl} />
      <VolumeCard data={data.volume} />
      <WinRateCard data={data.win_rate} />
      <TradeStatsCard trades={data.trades_today} positions={data.active_positions} />
    </div>
  );
};

export default DashboardCards;
