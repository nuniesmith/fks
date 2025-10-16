import React from 'react';

import {
  YAHOO_ASSET_CLASS_DEFINITIONS,
  YAHOO_NEWS_CATEGORIES,
  YAHOO_RESEARCH_PAGES,
} from '../../constants';

const Market: React.FC = () => {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white">Market</h1>
          <p className="text-white/70">Market breadth, sector rotation, volatility, and regime detection.</p>
        </div>

        {/* Yahoo Finance Catalog */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Asset Classes & Categories */}
          <div className="glass-card p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Yahoo Finance Assets</h2>
            <div className="space-y-4">
              {YAHOO_ASSET_CLASS_DEFINITIONS.map((asset) => (
                <div key={asset.class} className="border border-white/10 rounded-md p-4 bg-white/5">
                  <div className="text-white font-medium mb-2">{asset.label}</div>
                  <ul className="list-disc list-inside text-white/80 text-sm grid grid-cols-1 gap-1">
                    {asset.categories.map((cat) => (
                      <li key={cat.key}>
                        <span className="text-white/90">{cat.label}</span>
                        {'note' in cat && (cat as any).note && <span className="text-white/50"> — {(cat as any).note}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          {/* News Categories */}
          <div className="glass-card p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Yahoo News Categories</h2>
            <ul className="text-white/90 space-y-2">
              {YAHOO_NEWS_CATEGORIES.map((n) => (
                <li key={n.key} className="flex items-center justify-between border border-white/10 rounded-md px-3 py-2 bg-white/5">
                  <span>{n.label}</span>
                  <span className="text-xs text-white/50">{n.key}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Research/Tools */}
          <div className="glass-card p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Yahoo Research & Tools</h2>
            <ul className="text-white/90 space-y-2">
              {YAHOO_RESEARCH_PAGES.map((r) => (
                <li key={r.key} className="flex items-center justify-between border border-white/10 rounded-md px-3 py-2 bg-white/5">
                  <span>{r.label}</span>
                  <span className="text-xs text-white/50">{r.key}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Market;
