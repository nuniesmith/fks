import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Clock, Target, Check, AlertTriangle } from 'lucide-react';
import React, { useState } from 'react';

export interface CalendarEvent {
  id: string; title: string; description: string; date: Date; startTime: string; endTime: string;
  category: 'foundation' | 'development' | 'testing' | 'integration' | 'polish';
  status: 'pending' | 'in-progress' | 'completed' | 'blocked';
  priority: 'low' | 'medium' | 'high';
  deliverables?: string[];
}

export interface CalendarProps { events?: CalendarEvent[]; onEventClick?: (e: CalendarEvent)=>void; onDateClick?: (d: Date)=>void; }

const DEFAULT_EVENTS: CalendarEvent[] = [
  { id: 'd1', title: 'Project Setup', description: 'Repo + Tailwind + FastAPI scaffold', date: new Date(2025,6,27), startTime:'09:00', endTime:'17:00', category:'foundation', status:'pending', priority:'high', deliverables:['Scaffold','CI pipeline'] },
  { id: 'd2', title: 'Navigation', description: 'Sidebar + theme switch', date: new Date(2025,6,28), startTime:'09:00', endTime:'17:00', category:'foundation', status:'pending', priority:'high', deliverables:['Sidebar','Theme toggle'] },
  { id: 'd3', title: 'Home Enhancements', description: 'Realtime widgets', date: new Date(2025,6,29), startTime:'09:00', endTime:'17:00', category:'foundation', status:'pending', priority:'medium' }
];

const CATEGORY_STYLES: Record<string,string> = {
  foundation:'bg-blue-500/20 text-blue-400 border-blue-500/30',
  development:'bg-green-500/20 text-green-400 border-green-500/30',
  testing:'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  integration:'bg-purple-500/20 text-purple-400 border-purple-500/30',
  polish:'bg-pink-500/20 text-pink-400 border-pink-500/30'
};

const STATUS_ICON: Record<CalendarEvent['status'], React.ReactElement> = {
  pending:<Clock className="w-3 h-3" />, 'in-progress':<Target className="w-3 h-3 text-yellow-400" />, completed:<Check className="w-3 h-3 text-green-400" />, blocked:<AlertTriangle className="w-3 h-3 text-red-400" />
};

const Calendar: React.FC<CalendarProps> = ({ events = [], onEventClick, onDateClick }) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const allEvents = [...DEFAULT_EVENTS, ...events];
  const month = currentDate.getMonth();
  const year = currentDate.getFullYear();
  const daysInMonth = new Date(year, month+1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const todayStr = new Date().toDateString();

  const eventsFor = (d: Date) => allEvents.filter(e => e.date.toDateString() === d.toDateString());
  const changeMonth = (dir:'prev'|'next') => setCurrentDate(p=>{const n=new Date(p);n.setMonth(p.getMonth()+(dir==='next'?1:-1));return n;});

  const cells: React.ReactElement[] = [];
  for (let i=0;i<firstDay;i++) cells.push(<div key={`blank-${i}`} className="p-2"/>);
  for (let d=1; d<=daysInMonth; d++) {
    const date = new Date(year, month, d);
    const list = eventsFor(date);
    const isSel = selectedDate?.toDateString() === date.toDateString();
    const isToday = date.toDateString() === todayStr;
    cells.push(
      <div key={d} onClick={()=>{ setSelectedDate(date); onDateClick?.(date); }}
           className={`p-2 border border-gray-700 min-h-[78px] cursor-pointer hover:bg-gray-700/40 transition ${isSel?'bg-blue-600/30 border-blue-500':''} ${isToday?'ring-2 ring-blue-400/40':''}`}>
        <div className="text-xs font-semibold text-white mb-1">{d}</div>
        <div className="space-y-1">
          {list.slice(0,2).map(ev => (
            <div key={ev.id} onClick={e=>{e.stopPropagation(); onEventClick?.(ev);}}
                 className={`text-[10px] px-1 py-0.5 rounded border truncate ${CATEGORY_STYLES[ev.category]}`}
                 title={ev.title}>
              <span className="inline-flex items-center gap-1">{STATUS_ICON[ev.status]}<span className="truncate max-w-[70px]">{ev.title}</span></span>
            </div>
          ))}
          {list.length>2 && <div className="text-[10px] text-gray-400">+{list.length-2} more</div>}
        </div>
      </div>
    );
  }

  const selectedPanel = selectedDate && (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="text-sm font-semibold text-white mb-2">{selectedDate.toLocaleDateString('en-US',{weekday:'long', month:'short', day:'numeric', year:'numeric'})}</h3>
      {eventsFor(selectedDate).length === 0 ? <p className="text-xs text-gray-400">No events.</p> : (
        <div className="space-y-2">
          {eventsFor(selectedDate).map(ev => (
            <div key={ev.id} className="bg-gray-700/40 rounded p-2">
              <div className="flex items-start justify-between mb-1">
                <span className="text-xs font-medium text-white truncate">{ev.title}</span>
                <span className={`text-[9px] px-1 py-0.5 rounded ${CATEGORY_STYLES[ev.category]}`}>{ev.category}</span>
              </div>
              <div className="text-[10px] text-gray-400 mb-1">{ev.startTime} - {ev.endTime}</div>
              <p className="text-[10px] text-gray-300 mb-1 line-clamp-3">{ev.description}</p>
              {ev.deliverables && (
                <ul className="pl-3 list-disc space-y-0.5 text-[10px] text-gray-300">
                  {ev.deliverables.map((d,i)=>(<li key={i}>{d}</li>))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2"><CalendarIcon className="w-5 h-5"/> <span>FKS Development Calendar</span></h2>
        <div className="flex items-center gap-3">
          <button onClick={()=>changeMonth('prev')} className="p-2 bg-gray-700 hover:bg-gray-600 rounded transition"><ChevronLeft className="w-4 h-4"/></button>
          <h3 className="text-sm font-semibold text-white min-w-[140px] text-center">{currentDate.toLocaleDateString('en-US',{month:'long',year:'numeric'})}</h3>
          <button onClick={()=>changeMonth('next')} className="p-2 bg-gray-700 hover:bg-gray-600 rounded transition"><ChevronRight className="w-4 h-4"/></button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="grid grid-cols-7 mb-2">
              {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=> <div key={d} className="p-2 text-center text-[11px] font-medium text-gray-400">{d}</div>)}
            </div>
            <div className="grid grid-cols-7 gap-0">{cells}</div>
          </div>
        </div>
        <div className="space-y-4">
          {selectedPanel}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h4 className="text-sm font-semibold text-white mb-2">Categories</h4>
            <div className="space-y-1">
              {Object.entries(CATEGORY_STYLES).map(([c,cls]) => (
                <div key={c} className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded border ${cls}`}></div>
                  <span className="text-[11px] text-gray-300 capitalize">{c}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Calendar;
