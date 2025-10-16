import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

interface PiePoint { name: string; value: number; }
interface Props { data: PiePoint[]; palette: string[]; }

const RechartsPieInner: React.FC<Props> = ({ data, palette }) => (
  <ResponsiveContainer width="100%" height="100%">
    <PieChart>
      <Pie data={data} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} stroke="none">
        {data.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}
      </Pie>
      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: '0.75rem' }} />
    </PieChart>
  </ResponsiveContainer>
);

export default RechartsPieInner;
