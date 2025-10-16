// Minimal, dependency-free ICS parser for browser use
// Supports DTSTART/DTEND with optional TZID, Zulu time, folded lines, SUMMARY, DESCRIPTION

export interface IcsEvent {
  title: string;
  start: Date;
  end: Date;
  description?: string;
  location?: string;
}

function unfoldLines(text: string): string[] {
  const raw = text.split(/\r?\n/);
  const lines: string[] = [];
  for (const line of raw) {
    if ((line.startsWith(' ') || line.startsWith('\t')) && lines.length) {
      lines[lines.length - 1] += line.trimStart();
    } else {
      lines.push(line);
    }
  }
  return lines;
}

function parseDate(val: string, tzid?: string): Date {
  const hasZ = /Z$/.test(val);
  const base = val.replace('Z', '');
  // YYYYMMDDTHHmmss
  const year = parseInt(base.slice(0, 4), 10);
  const month = parseInt(base.slice(4, 6), 10) - 1;
  const day = parseInt(base.slice(6, 8), 10);
  const hour = parseInt(base.slice(9, 11) || '0', 10);
  const min = parseInt(base.slice(11, 13) || '0', 10);
  const sec = parseInt(base.slice(13, 15) || '0', 10);
  if (hasZ) {
    // UTC
    return new Date(Date.UTC(year, month, day, hour, min, sec));
  }
  // Best-effort: treat as local time or apply fixed offset if tzid is America/New_York
  if (tzid && /America\/New_York/.test(tzid)) {
    // Approx: Eastern time. Let browser handle DST by constructing as local
    return new Date(year, month, day, hour, min, sec);
  }
  return new Date(year, month, day, hour, min, sec);
}

export function parseICS(text: string): IcsEvent[] {
  const lines = unfoldLines(text);
  const events: IcsEvent[] = [];
  let inEvent = false;
  let cur: Partial<IcsEvent> & { _tzStart?: string; _tzEnd?: string } = {};

  for (const l of lines) {
    if (l === 'BEGIN:VEVENT') {
      inEvent = true;
      cur = {};
      continue;
    }
    if (l === 'END:VEVENT') {
      if (cur.title && cur.start && cur.end) {
        events.push({
          title: cur.title,
          start: cur.start,
          end: cur.end,
          description: cur.description,
          location: cur.location,
        });
      }
      inEvent = false;
      cur = {};
      continue;
    }
    if (!inEvent) continue;

    if (l.startsWith('SUMMARY:')) cur.title = l.substring(8).trim();
    else if (l.startsWith('DESCRIPTION:')) cur.description = l.substring(12).replace(/\\n/g, '\n').trim();
    else if (l.startsWith('LOCATION:')) cur.location = l.substring(9).trim();
    else if (l.startsWith('DTSTART')) {
      const [left, valueRaw] = l.split(':');
      const tzMatch = left.match(/TZID=([^;:]+)/);
      const tzid = tzMatch ? tzMatch[1] : undefined;
      cur.start = parseDate((valueRaw || '').trim(), tzid);
    } else if (l.startsWith('DTEND')) {
      const [left, valueRaw] = l.split(':');
      const tzMatch = left.match(/TZID=([^;:]+)/);
      const tzid = tzMatch ? tzMatch[1] : undefined;
      cur.end = parseDate((valueRaw || '').trim(), tzid);
    }
  }
  return events;
}
