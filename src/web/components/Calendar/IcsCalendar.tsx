import React, { useEffect, useState } from 'react';
import { Calendar as RBCalendar, dayjsLocalizer } from 'react-big-calendar';
import { dayjs } from '../../shared/time/dayjs';

import 'react-big-calendar/lib/css/react-big-calendar.css';
import { parseICS } from '../../utils/ics';

import type { IcsEvent } from '../../utils/ics';

// Use dayjs (lightweight) instead of moment for calendar localization
const localizer = dayjsLocalizer(dayjs);

const IcsCalendar: React.FC<{ path?: string }> = ({ path = '/fks_trading_plan_revised.ics' }) => {
  const [events, setEvents] = useState<IcsEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError('');
      const candidates = [path, '/fks_trading_plan.ics'];
      let text: string | null = null;
      for (const p of candidates) {
        try {
          const resp = await fetch(p, { cache: 'no-store' });
          if (resp.ok) { text = await resp.text(); break; }
        } catch (_) { /* ignore */ }
      }
      if (!cancelled) {
        if (text) {
          const parsed = parseICS(text);
          if (parsed.length) setEvents(parsed);
          else setError('No events found in ICS');
        } else {
          setError('Unable to load ICS');
        }
        setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [path]);

  if (loading) return <div className="text-white/70">Loading calendar…</div>;
  if (error) return <div className="text-yellow-300">{error}</div>;

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700" style={{ height: 600 }}>
      <RBCalendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        tooltipAccessor={(e: any) => e.description || e.title}
        style={{ height: '100%' }}
      />
    </div>
  );
};

export default IcsCalendar;
