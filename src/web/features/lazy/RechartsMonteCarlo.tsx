import React from 'react';
import { ComposedChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, Area } from 'recharts';
import type { MonteCarloChartRow } from '../../components/Trading/MonteCarloPathsChart';

interface Props { rows: MonteCarloChartRow[]; sampleCount: number; }

const MonteCarloRechartsBundle: React.FC<Props> = ({ rows, sampleCount }) => (
  <ResponsiveContainer>
    <ComposedChart data={rows} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
      <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
      <XAxis dataKey="step" stroke="#94a3b8" fontSize={12} />
      <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${Math.round(v/1000)}k`} />
      <Tooltip contentStyle={{ background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }} labelFormatter={(s) => `Step ${s}`} formatter={(val: any, name) => [typeof val === 'number' ? `$${val.toFixed(2)}` : val, name]} />
      <Legend wrapperStyle={{ fontSize: 10 }} />
      <Area type="monotone" dataKey="bandLow" stackId="band" stroke="none" fill="transparent" />
      <Area type="monotone" dataKey="bandDiff" stackId="band" stroke="none" fill="rgba(59,130,246,0.15)" />
      <Line type="monotone" dataKey="p50" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} name="Median" />
      <Line type="monotone" dataKey="p5" stroke="#f87171" strokeWidth={1} dot={false} isAnimationActive={false} name="P5" />
      <Line type="monotone" dataKey="p95" stroke="#34d399" strokeWidth={1} dot={false} isAnimationActive={false} name="P95" />
      {Array.from({ length: sampleCount }).map((_, idx) => (
        <Line key={idx} type="monotone" dataKey={`p${idx}`} stroke={`hsl(${(idx * 40) % 360} 70% 60%)`} strokeWidth={1} dot={false} opacity={0.6} isAnimationActive={false} name={`Path ${idx+1}`} />
      ))}
    </ComposedChart>
  </ResponsiveContainer>
);

export default MonteCarloRechartsBundle;
