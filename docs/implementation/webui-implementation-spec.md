---
title: "WebUI Implementation Spec (Archived)"
category: "implementation"
tags: ["webui", "htmx", "fastapi", "css", "archived"]
---

> ⚠️ **ARCHIVED:** This document is a historical implementation spec generated during the WebUI terminal redesign.
> The CSS, JS, and Python described here have been implemented and live in:
> - `src/web/css/fks-terminal.css` — terminal stylesheet
> - `src/web/js/` — JS modules
> - `src/ruby/src/services/data/api/shell.py` — FastAPI shell renderer
> - `src/web/html/` — HTML workspace pages
>
> **Do not use this doc as a current reference** — read the source directly.
> Kept here for historical context of the initial design decisions.

---

Let me ask a few things before building this out — the answers will change the layout significantly.Good context — I'll build this for desktop-first with everything I know from your codebase. Here's a fully interactive mockup of the layout system before any code:Click through the pages using the sidebar — that's the exact layout to build. Now the code to make it real.

The key insight from your `todo.md` is that the current `shell.py` has `_SHARED_CSS` as a 700-line inline string, and 11+ HTML pages each duplicate it. The fix is extracting everything to two static files and one `shell.py` that just renders a skeleton.

---

### `src/ruby/static/css/fks.css`

One file. All pages reference it. No more inline CSS strings.

```css
/* ── Reset & base ─────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg0: #0a0a0f;
  --bg1: #0f0f17;
  --bg2: #14141e;
  --bg3: #1a1a28;
  --border:  #1e2030;
  --border2: #252840;

  --text-primary:   #e2e4f0;
  --text-secondary: #7880a0;
  --text-muted:     #454868;

  --accent:  #5b6ef5;
  --accent2: #3d4fe0;

  --green:  #22c55e;
  --red:    #ef4444;
  --amber:  #f59e0b;
  --cyan:   #06b6d4;
  --purple: #a78bfa;
  --teal:   #2dd4bf;

  --sidebar-w:        56px;
  --sidebar-expanded: 200px;
  --topbar-h:         44px;
  --statusbar-h:      28px;
  --radius:           6px;
  --radius-lg:        10px;

  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--bg0);
}

body { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* ── Layout shell ─────────────────────────────────────── */
.fks-topbar {
  height: var(--topbar-h);
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 12px;
  flex-shrink: 0;
  z-index: 10;
}
.fks-main   { display: flex; flex: 1; overflow: hidden; }
.fks-content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.fks-statusbar {
  height: var(--statusbar-h);
  background: var(--bg1);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 16px;
  flex-shrink: 0;
  overflow: hidden;
}
.fks-page { flex: 1; overflow: auto; padding: 14px; }

/* ── Topbar atoms ─────────────────────────────────────── */
.tb-logo { font-size: 15px; font-weight: 700; color: var(--accent); letter-spacing: .5px; }
.tb-sep  { width: 1px; height: 20px; background: var(--border2); flex-shrink: 0; }
.tb-spacer { flex: 1; }

.tb-chip {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 10px;
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color .15s;
}
.tb-chip:hover { border-color: var(--accent); }

.tb-btn {
  padding: 4px 8px;
  background: transparent;
  border: 1px solid var(--border2);
  border-radius: 5px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 11px;
  transition: all .15s;
}
.tb-btn:hover { background: var(--bg3); color: var(--text-primary); border-color: var(--accent); }
.tb-btn.kill:hover { background: #1a0808; color: var(--red); border-color: var(--red); }
.tb-time { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; min-width: 60px; text-align: right; }

/* ── Sidebar ──────────────────────────────────────────── */
.fks-sidebar {
  width: var(--sidebar-w);
  background: var(--bg1);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width .2s ease;
  overflow: hidden;
  flex-shrink: 0;
  z-index: 9;
}
.fks-sidebar.expanded { width: var(--sidebar-expanded); }

.sb-toggle {
  height: 36px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0; transition: color .15s;
}
.sb-toggle:hover { color: var(--text-primary); }

.sb-items { flex: 1; padding: 6px 0; overflow: hidden; }
.sb-bottom { padding: 6px 0; border-top: 1px solid var(--border); }

.sb-item {
  display: flex; align-items: center; gap: 10px;
  height: 36px; padding: 0 16px;
  cursor: pointer;
  color: var(--text-secondary);
  border-left: 2px solid transparent;
  transition: all .12s;
  white-space: nowrap;
  text-decoration: none;
}
.sb-item:hover  { color: var(--text-primary); background: var(--bg2); }
.sb-item.active {
  color: var(--accent);
  background: rgba(91,110,245,.08);
  border-left-color: var(--accent);
}
.sb-icon { width: 16px; height: 16px; flex-shrink: 0; opacity: .7; }
.sb-item.active .sb-icon { opacity: 1; }

.sb-label {
  font-size: 12px; font-weight: 500;
  opacity: 0; transition: opacity .15s;
}
.fks-sidebar.expanded .sb-label { opacity: 1; }

.sb-badge {
  margin-left: auto;
  font-size: 9px;
  background: var(--red);
  color: white;
  border-radius: 8px;
  padding: 1px 5px;
  flex-shrink: 0;
}

/* ── Statusbar ─────────────────────────────────────────── */
.st-item { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--text-muted); white-space: nowrap; }
.st-item b { color: var(--text-secondary); font-weight: 500; }
.st-live  { color: var(--green) !important; }
.st-right { margin-left: auto; }

/* ── Live dot ─────────────────────────────────────────── */
.dot {
  width: 6px; height: 6px;
  border-radius: 50%; flex-shrink: 0; display: inline-block;
}
.dot-green  { background: var(--green); box-shadow: 0 0 4px var(--green); }
.dot-amber  { background: var(--amber); }
.dot-red    { background: var(--red); }
.dot-gray   { background: var(--text-muted); }

/* ── Page header ──────────────────────────────────────── */
.page-header {
  display: flex; align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}
.page-title    { font-size: 16px; font-weight: 600; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.page-actions  { display: flex; gap: 6px; }

/* ── Buttons ──────────────────────────────────────────── */
.btn {
  padding: 5px 12px;
  border-radius: var(--radius);
  font-size: 11px; font-weight: 500;
  cursor: pointer; border: none;
  transition: all .15s;
}
.btn-primary { background: var(--accent); color: white; }
.btn-primary:hover { background: var(--accent2); }
.btn-ghost {
  background: var(--bg2);
  border: 1px solid var(--border2);
  color: var(--text-secondary);
}
.btn-ghost:hover { color: var(--text-primary); border-color: var(--accent); }
.btn-danger { background: rgba(239,68,68,.12); color: var(--red); border: 1px solid rgba(239,68,68,.3); }
.btn-danger:hover { background: rgba(239,68,68,.2); }
.btn-success { background: rgba(34,197,94,.12); color: var(--green); border: 1px solid rgba(34,197,94,.3); }
.btn-success:hover { background: rgba(34,197,94,.2); }
.btn-sm { padding: 3px 8px; font-size: 10px; }
.btn-wide { width: 100%; text-align: center; padding: 8px 12px; }

/* ── Cards ────────────────────────────────────────────── */
.card {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px;
}
.card-header {
  display: flex; align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.card-title {
  font-size: 11px; font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: .5px;
}

/* ── Badges ───────────────────────────────────────────── */
.badge {
  font-size: 9px; padding: 2px 6px;
  border-radius: 4px; font-weight: 600;
  white-space: nowrap;
}
.badge-green  { background: rgba(34,197,94,.12);  color: var(--green); }
.badge-red    { background: rgba(239,68,68,.12);   color: var(--red); }
.badge-amber  { background: rgba(245,158,11,.12);  color: var(--amber); }
.badge-blue   { background: rgba(91,110,245,.12);  color: var(--accent); }
.badge-cyan   { background: rgba(6,182,212,.12);   color: var(--cyan); }
.badge-gray   { background: var(--bg3);            color: var(--text-secondary); }
.badge-purple { background: rgba(167,139,250,.12); color: var(--purple); }

/* ── Grid helpers ─────────────────────────────────────── */
.g2   { display: grid; grid-template-columns: 1fr 1fr;           gap: 10px; }
.g3   { display: grid; grid-template-columns: 1fr 1fr 1fr;       gap: 10px; }
.g4   { display: grid; grid-template-columns: repeat(4,1fr);     gap: 10px; }
.g7030{ display: grid; grid-template-columns: 70fr 30fr;         gap: 10px; }
.g6040{ display: grid; grid-template-columns: 60fr 40fr;         gap: 10px; }
.g3070{ display: grid; grid-template-columns: 30fr 70fr;         gap: 10px; }
.col  { display: flex; flex-direction: column; gap: 10px; }
.span2 { grid-column: span 2; }
.span3 { grid-column: span 3; }

/* ── Typography ───────────────────────────────────────── */
.stat-val {
  font-size: 22px; font-weight: 700;
  font-variant-numeric: tabular-nums; line-height: 1.1;
}
.stat-label  { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.stat-change { font-size: 11px; margin-top: 4px; }

.mono { font-family: 'SF Mono', 'Fira Code', monospace; font-variant-numeric: tabular-nums; }
.muted { color: var(--text-secondary); }
.dim   { color: var(--text-muted); }
.pos   { color: var(--green); }
.neg   { color: var(--red); }
.warn  { color: var(--amber); }
.info  { color: var(--cyan); }

/* ── Table primitives ─────────────────────────────────── */
.data-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid var(--border);
}
.data-row:last-child { border-bottom: none; }
.data-row-key { font-size: 11px; flex: 1; }
.data-row-val { font-size: 11px; font-weight: 500; font-variant-numeric: tabular-nums; }

/* ── Signal item ──────────────────────────────────────── */
.signal-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}
.signal-item:last-child { border-bottom: none; }

.sig-dir {
  width: 36px; height: 20px;
  border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; flex-shrink: 0;
}
.sig-long  { background: rgba(34,197,94,.15); color: var(--green); }
.sig-short { background: rgba(239,68,68,.15); color: var(--red); }
.sig-close { background: rgba(245,158,11,.15); color: var(--amber); }

/* ── Coverage / progress bars ─────────────────────────── */
.progress {
  height: 4px; background: var(--bg3);
  border-radius: 2px; overflow: hidden; margin-top: 4px;
}
.progress-fill { height: 100%; border-radius: 2px; transition: width .3s; }
.pf-green  { background: var(--green); }
.pf-amber  { background: var(--amber); }
.pf-red    { background: var(--red); }
.pf-accent { background: var(--accent); }

/* ── Tab bar ──────────────────────────────────────────── */
.tabs {
  display: flex; gap: 2px; margin-bottom: 12px;
  background: var(--bg2); border-radius: var(--radius); padding: 3px;
}
.tab {
  padding: 4px 12px; border-radius: 4px;
  font-size: 11px; font-weight: 500;
  cursor: pointer; color: var(--text-muted);
  transition: all .12s; white-space: nowrap;
  border: none; background: transparent;
}
.tab.active { background: var(--bg3); color: var(--text-primary); }
.tab:hover:not(.active) { color: var(--text-secondary); }

/* ── Form inputs ──────────────────────────────────────── */
.field { display: flex; flex-direction: column; gap: 3px; }
.field label { font-size: 10px; color: var(--text-muted); }
.input {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  padding: 6px 8px;
  font-size: 12px;
  color: var(--text-primary);
  outline: none;
  transition: border-color .15s;
  font-family: inherit;
}
.input:focus { border-color: var(--accent); }
.input.buy-border  { border-color: rgba(34,197,94,.4); }
.input.sell-border { border-color: rgba(239,68,68,.4); }

/* ── Toast ────────────────────────────────────────────── */
#toast-container {
  position: fixed; bottom: 16px; right: 16px;
  display: flex; flex-direction: column; gap: 6px;
  z-index: 999;
}
.toast {
  padding: 8px 14px;
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  font-size: 12px;
  animation: slideIn .2s ease;
  max-width: 280px;
}
.toast.success { border-color: rgba(34,197,94,.4); }
.toast.error   { border-color: rgba(239,68,68,.4); color: var(--red); }
.toast.warning { border-color: rgba(245,158,11,.4); color: var(--amber); }

@keyframes slideIn { from { opacity:0; transform:translateX(16px); } to { opacity:1; transform:none; } }

/* ── Chart placeholder ────────────────────────────────── */
.chart-wrap {
  background: var(--bg2);
  border-radius: var(--radius);
  overflow: hidden;
  position: relative;
  display: flex; align-items: center; justify-content: center;
}

/* ── HTMX indicators ──────────────────────────────────── */
.htmx-indicator { opacity: 0; transition: opacity .2s; }
.htmx-request .htmx-indicator { opacity: 1; }
.htmx-request.htmx-indicator  { opacity: 1; }

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

/* ── Responsive collapse ──────────────────────────────── */
@media (max-width: 1200px) {
  .g4 { grid-template-columns: 1fr 1fr; }
  .g7030, .g6040, .g3070 { grid-template-columns: 1fr; }
}
@media (max-width: 800px) {
  .g2, .g3 { grid-template-columns: 1fr; }
  .fks-sidebar { width: 0; border: none; }
}
```

---

### `src/ruby/static/js/fks.js`

One file. Handles everything: SSE, HTMX helpers, sidebar, clock, toasts, API wrappers.

```javascript
/* fks.js — shared runtime for all FKS dashboard pages */

// ── Sidebar ────────────────────────────────────────────────────────────────
const Sidebar = {
  el: null,
  expanded: false,

  init() {
    this.el = document.getElementById('fks-sidebar');
    const saved = localStorage.getItem('fks:sidebar');
    if (saved === 'expanded') this.expand();
  },

  toggle() {
    this.expanded ? this.collapse() : this.expand();
  },

  expand() {
    this.expanded = true;
    this.el?.classList.add('expanded');
    localStorage.setItem('fks:sidebar', 'expanded');
  },

  collapse() {
    this.expanded = false;
    this.el?.classList.remove('expanded');
    localStorage.setItem('fks:sidebar', 'collapsed');
  },
};

// ── Clock ──────────────────────────────────────────────────────────────────
const Clock = {
  el: null,
  start() {
    this.el = document.getElementById('fks-clock');
    if (!this.el) return;
    const tick = () => {
      const d = new Date();
      const pad = n => String(n).padStart(2, '0');
      this.el.textContent = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };
    tick();
    setInterval(tick, 1000);
  },
};

// ── Toast ──────────────────────────────────────────────────────────────────
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', durationMs = 3500) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    this.container.appendChild(el);
    setTimeout(() => el.remove(), durationMs);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg)   { this.show(msg, 'error', 5000); },
  warning(msg) { this.show(msg, 'warning'); },
};

// ── API helpers ────────────────────────────────────────────────────────────
const API = {
  _key: document.querySelector('meta[name=api-key]')?.content || '',

  headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this._key) h['X-API-Key'] = this._key;
    return h;
  },

  async get(path) {
    const r = await fetch(path, { headers: this.headers() });
    if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
    return r.json();
  },

  async post(path, body = {}) {
    const r = await fetch(path, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${path} → ${r.status}`);
    return r.json();
  },

  async patch(path, body = {}) {
    const r = await fetch(path, {
      method: 'PATCH',
      headers: this.headers(),
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`PATCH ${path} → ${r.status}`);
    return r.json();
  },
};

// ── SSE manager ────────────────────────────────────────────────────────────
// Manages a pool of named SSE connections with auto-reconnect.
// Usage:
//   SSE.connect('dashboard', '/sse/dashboard', data => handleUpdate(data));
//   SSE.disconnect('dashboard');
const SSE = {
  connections: {},
  backoffs: {},

  connect(name, url, onMessage, onError) {
    this.disconnect(name);
    const es = new EventSource(url);

    es.onmessage = e => {
      try { onMessage(JSON.parse(e.data)); }
      catch { onMessage(e.data); }
      this.backoffs[name] = 1000; // reset backoff on success
    };

    es.onerror = err => {
      onError?.(err);
      es.close();
      delete this.connections[name];
      const delay = this.backoffs[name] || 1000;
      this.backoffs[name] = Math.min(delay * 2, 30000); // cap at 30s
      setTimeout(() => this.connect(name, url, onMessage, onError), delay);
    };

    this.connections[name] = es;
    return es;
  },

  disconnect(name) {
    this.connections[name]?.close();
    delete this.connections[name];
    delete this.backoffs[name];
  },

  disconnectAll() {
    Object.keys(this.connections).forEach(k => this.disconnect(k));
  },
};

// ── Live price updater ─────────────────────────────────────────────────────
// Subscribes to SSE and updates DOM elements with data-price="SYMBOL",
// data-chg="SYMBOL", data-pnl attributes.
const Prices = {
  init() {
    SSE.connect('prices', '/sse/prices', data => {
      if (!data?.symbol) return;
      document.querySelectorAll(`[data-price="${data.symbol}"]`).forEach(el => {
        el.textContent = Number(data.price).toLocaleString('en-US', {
          minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
      });
      document.querySelectorAll(`[data-chg="${data.symbol}"]`).forEach(el => {
        const pct = data.change_pct;
        el.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
        el.className = el.className.replace(/\b(pos|neg)\b/g, '') + (pct >= 0 ? ' pos' : ' neg');
      });
    });
  },
};

// ── Format helpers ─────────────────────────────────────────────────────────
const Fmt = {
  currency(val, places = 2) {
    const sign = val >= 0 ? '+' : '';
    return `${sign}$${Math.abs(val).toFixed(places)}`;
  },

  pct(val, places = 2) {
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(places)}%`;
  },

  price(val, places = 2) {
    return Number(val).toLocaleString('en-US', {
      minimumFractionDigits: places,
      maximumFractionDigits: places,
    });
  },

  relativeTime(isoStr) {
    const diff = (Date.now() - new Date(isoStr)) / 1000;
    if (diff < 60)   return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  },

  sentiment(compound) {
    if (compound >= 0.05)  return { label: 'positive', cls: 'badge-green' };
    if (compound <= -0.05) return { label: 'negative', cls: 'badge-red' };
    return { label: 'neutral', cls: 'badge-gray' };
  },
};

// ── HTMX hooks ─────────────────────────────────────────────────────────────
// After every HTMX swap, re-init any components inside the swapped element.
document.addEventListener('htmx:afterSwap', e => {
  // Re-attach tab click handlers inside swapped content
  e.target.querySelectorAll('.tab').forEach(attachTabHandler);
});

document.addEventListener('htmx:responseError', e => {
  const status = e.detail.xhr?.status;
  Toast.error(`Request failed (${status || 'network error'})`);
});

// ── Tab helpers ────────────────────────────────────────────────────────────
function attachTabHandler(tab) {
  tab.addEventListener('click', () => {
    const group = tab.closest('.tabs');
    const target = tab.dataset.tab;
    if (!group || !target) return;
    group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    // Show/hide panels in the same card
    const card = tab.closest('.card');
    card?.querySelectorAll('[data-panel]').forEach(p => {
      p.style.display = p.dataset.panel === target ? '' : 'none';
    });
  });
}

// ── Kill switch shortcut ───────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // Ctrl+Shift+K = kill switch confirmation
  if (e.ctrlKey && e.shiftKey && e.key === 'K') {
    if (confirm('Activate kill switch? This will cancel all open orders.')) {
      API.post('/api/kill-switch').then(() => Toast.warning('Kill switch activated'));
    }
  }
});

// ── Boot ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  Sidebar.init();
  Clock.start();
  Toast.init();

  // Only start price SSE on pages that need it
  if (document.querySelector('[data-price]')) Prices.init();

  // Wire up all static tabs
  document.querySelectorAll('.tab').forEach(attachTabHandler);
});

// Export for inline scripts in templates
window.FKS = { API, SSE, Toast, Fmt, Sidebar };
```

---

### `src/ruby/src/lib/services/data/api/shell.py` — rewritten

This replaces the current `shell.py` with one function that renders a lean HTML skeleton. No more 700-line inline CSS string.

```python
"""
shell.py — renders the HTML shell for every server-side page.

Usage in a route:
    from lib.services.data.api.shell import render_page

    @router.get("/dashboard")
    async def dashboard(request: Request):
        content = await build_dashboard_content(request)
        return HTMLResponse(render_page(
            title="Dashboard",
            content=content,
            active_nav="dashboard",
            request=request,
        ))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from markupsafe import Markup

# ── Nav items ─────────────────────────────────────────────────────────────

@dataclass
class NavItem:
    id:      str
    label:   str
    href:    str
    icon:    str           # raw SVG path data
    badge:   str = ""      # e.g. "3" for signal count — empty = hidden

NAV_ITEMS: list[NavItem] = [
    NavItem("dashboard", "Dashboard",    "/",             _icon_grid()),
    NavItem("analysis",  "Analysis",     "/analysis",     _icon_chart_line()),
    NavItem("trading",   "Trading",      "/trading",      _icon_clock()),
    NavItem("charts",    "Charts",       "/charts",       _icon_candle()),
    NavItem("news",      "News",         "/factory/news-page", _icon_doc()),
    NavItem("journal",   "Journal",      "/journal",      _icon_calendar()),
    NavItem("positions", "Positions",    "/positions",    _icon_user()),
    NavItem("trainer",   "Trainer",      "/trainer",      _icon_cpu()),
]

NAV_BOTTOM: list[NavItem] = [
    NavItem("settings",  "Settings",     "/settings",     _icon_gear()),
]


def render_page(
    title: str,
    content: str,
    active_nav: str = "",
    request=None,
    extra_head: str = "",
    extra_scripts: str = "",
    status_items: list[dict] | None = None,
    topbar_chips: str = "",
) -> str:
    """
    Returns a complete HTML document string.

    Args:
        title:          Browser tab title
        content:        The page body HTML (goes inside .fks-page)
        active_nav:     NavItem.id to highlight in sidebar
        request:        FastAPI Request — used to read app.state for live data
        extra_head:     Additional <head> content (inline styles, meta)
        extra_scripts:  Additional <script> tags at end of body
        status_items:   Override status bar items (default: fetched from app.state)
        topbar_chips:   Additional HTML for topbar right of the logo/separator
    """
    api_key = ""
    if request:
        api_key = getattr(request.app.state, "api_key", "")

    nav_html     = _render_nav(active_nav)
    status_html  = _render_statusbar(status_items or [])
    topbar_html  = _render_topbar(topbar_chips, api_key)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="api-key" content="{_escape(api_key)}">
  <title>{_escape(title)} · FKS</title>
  <link rel="stylesheet" href="/static/css/fks.css">
  <script src="/static/js/htmx.min.js" defer></script>
  <script src="/static/js/fks.js" defer></script>
  {extra_head}
</head>
<body>
  {topbar_html}
  <div class="fks-main">
    {nav_html}
    <div class="fks-content">
      {status_html}
      <div class="fks-page">
        {content}
      </div>
    </div>
  </div>
  <div id="toast-container"></div>
  {extra_scripts}
</body>
</html>"""


# ── Topbar ────────────────────────────────────────────────────────────────

def _render_topbar(extra_chips: str, api_key: str) -> str:
    return f"""
<header class="fks-topbar" id="fks-topbar">
  <span class="tb-logo">FKS</span>
  <div class="tb-sep"></div>

  <!-- Focus asset chip — updated via SSE in fks.js -->
  <div class="tb-chip" id="tb-focus-asset"
       hx-get="/api/focus-asset/chip"
       hx-trigger="every 5s"
       hx-swap="outerHTML">
    <span class="dot dot-green"></span>
    <span class="mono" id="tb-focus-sym">—</span>
    <span class="mono info" id="tb-focus-price">—</span>
  </div>

  <div class="tb-sep"></div>

  <!-- Day P&L chip -->
  <div class="tb-chip" id="tb-pnl"
       hx-get="/api/pnl/chip"
       hx-trigger="every 10s"
       hx-swap="outerHTML">
    <span class="dim" style="font-size:10px">P&L</span>
    <span class="mono" id="tb-pnl-val" style="font-size:13px;font-weight:600">—</span>
  </div>

  <div class="tb-sep"></div>

  <!-- Session status -->
  <div class="tb-chip" style="cursor:default" id="tb-session"
       hx-get="/api/session/chip"
       hx-trigger="every 30s"
       hx-swap="outerHTML">
    <span class="dot dot-green" id="tb-session-dot"></span>
    <span class="muted" style="font-size:11px" id="tb-session-label">Loading…</span>
  </div>

  {extra_chips}
  <div class="tb-spacer"></div>

  <button class="tb-btn" hx-get="/settings" hx-target="body" hx-push-url="true">Settings</button>
  <button class="tb-btn kill"
          hx-post="/api/kill-switch"
          hx-confirm="Activate kill switch? This cancels all open orders."
          hx-swap="none">Kill switch</button>
  <span class="tb-time" id="fks-clock">--:--:--</span>
</header>"""


# ── Sidebar ────────────────────────────────────────────────────────────────

def _render_nav(active_id: str) -> str:
    items_html   = "\n".join(_render_nav_item(n, active_id) for n in NAV_ITEMS)
    bottom_html  = "\n".join(_render_nav_item(n, active_id) for n in NAV_BOTTOM)

    return f"""
<nav class="fks-sidebar" id="fks-sidebar">
  <div class="sb-toggle" onclick="FKS.Sidebar.toggle()" title="Toggle sidebar">
    {_icon_menu()}
  </div>
  <div class="sb-items">
    {items_html}
  </div>
  <div class="sb-bottom">
    {bottom_html}
  </div>
</nav>"""


def _render_nav_item(item: NavItem, active_id: str) -> str:
    active  = "active" if item.id == active_id else ""
    badge   = f'<span class="sb-badge">{item.badge}</span>' if item.badge else ""
    return f"""
  <a class="sb-item {active}" href="{item.href}"
     hx-get="{item.href}" hx-target="#fks-page-area"
     hx-push-url="true" hx-swap="innerHTML">
    <svg class="sb-icon" viewBox="0 0 16 16" fill="none"
         stroke="currentColor" stroke-width="1.5">
      {item.icon}
    </svg>
    <span class="sb-label">{item.label}</span>
    {badge}
  </a>"""


# ── Status bar ────────────────────────────────────────────────────────────

def _render_statusbar(items: list[dict]) -> str:
    """
    items: [{"label": "Redis", "value": "ok", "color": "green"}, ...]
    Color values: "green" | "amber" | "red" | "muted"
    """
    color_map = {
        "green": "var(--green)",
        "amber": "var(--amber)",
        "red":   "var(--red)",
        "muted": "var(--text-muted)",
    }
    items_html = ""
    for item in items:
        color = color_map.get(item.get("color", "muted"), "var(--text-muted)")
        items_html += f"""
      <div class="st-item">
        {item.get("label", "")}
        <b style="color:{color}">{item.get("value", "")}</b>
      </div>"""

    return f"""
<div class="fks-statusbar" id="fks-statusbar"
     hx-get="/api/status/bar"
     hx-trigger="every 30s"
     hx-swap="innerHTML">
  {items_html}
</div>"""


# ── Escape helper ─────────────────────────────────────────────────────────

def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# ── SVG icon paths ────────────────────────────────────────────────────────
# These are just the inner SVG content — the <svg> wrapper is in _render_nav_item

def _icon_grid():
    return '<rect x="1" y="1" width="6" height="6" rx="1.5"/><rect x="9" y="1" width="6" height="6" rx="1.5"/><rect x="1" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="9" width="6" height="6" rx="1.5"/>'

def _icon_chart_line():
    return '<polyline points="1,12 5,7 8,9 12,4 15,6"/><circle cx="15" cy="6" r="1"/>'

def _icon_clock():
    return '<circle cx="8" cy="8" r="6"/><polyline points="8,5 8,8 10,10"/>'

def _icon_candle():
    return '<line x1="4" y1="2" x2="4" y2="14"/><rect x="2" y="4" width="4" height="6" rx="0.5"/><line x1="12" y1="2" x2="12" y2="14"/><rect x="10" y="6" width="4" height="5" rx="0.5"/>'

def _icon_doc():
    return '<rect x="1" y="2" width="14" height="12" rx="2"/><line x1="4" y1="6" x2="12" y2="6"/><line x1="4" y1="9" x2="10" y2="9"/>'

def _icon_calendar():
    return '<rect x="1" y="4" width="14" height="9" rx="1.5"/><line x1="1" y1="7" x2="15" y2="7"/><line x1="5" y1="4" x2="5" y2="2"/><line x1="11" y1="4" x2="11" y2="2"/>'

def _icon_user():
    return '<circle cx="8" cy="6" r="3"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6"/>'

def _icon_cpu():
    return '<rect x="3" y="3" width="10" height="10" rx="1.5"/><line x1="6" y1="1" x2="6" y2="3"/><line x1="10" y1="1" x2="10" y2="3"/><line x1="6" y1="13" x2="6" y2="15"/><line x1="10" y1="13" x2="10" y2="15"/><line x1="1" y1="6" x2="3" y2="6"/><line x1="1" y1="10" x2="3" y2="10"/><line x1="13" y1="6" x2="15" y2="6"/><line x1="13" y1="10" x2="15" y2="10"/>'

def _icon_gear():
    return '<circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.5 3.5l1.3 1.3M11.2 11.2l1.3 1.3M3.5 12.5l1.3-1.3M11.2 4.8l1.3-1.3"/>'

def _icon_menu():
    return '<svg class="sb-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="12" height="1.5" rx=".75"/><rect x="2" y="7.25" width="12" height="1.5" rx=".75"/><rect x="2" y="11.5" width="12" height="1.5" rx=".75"/></svg>'
```

---

### `src/ruby/src/lib/services/data/api/status.py` — feeds the statusbar

The statusbar auto-refreshes every 30s via HTMX. One endpoint serves all its data.

```python
"""
Status API — feeds the topbar status bar and health chips.
All endpoints return HTML fragments for HTMX swap.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["status"])


@router.get("/api/status/bar", response_class=HTMLResponse)
async def status_bar(request: Request):
    """
    Returns statusbar inner HTML. Polled every 30s by the shell.
    Reads from Redis — all factory/service workers write their status there.
    """
    redis = request.app.state.redis

    async def check(key: str, default: str = "unknown") -> str:
        v = await redis.get(key)
        return v if v else default

    live_feed    = await check("ruby:live:feed:status", "unknown")
    factory_proc = await check("ruby:factory:health",   "unknown")
    last_scan    = await check("ruby:gaps:last_scan")
    sig_count    = await check("ruby:signals:today:count", "0")
    win_rate     = await check("ruby:signals:win_rate",    "—")

    # Parse coverage counts
    registry  = request.app.state.asset_registry
    assets    = await registry.enabled_assets()
    ok = critical = 0
    for a in assets:
        for t in a.window_targets:
            raw = await redis.get(f"ruby:coverage:{a.symbol}:{t.interval.value}")
            if raw:
                d = json.loads(raw)
                if d.get("status") == "ok":
                    ok += 1
                elif d.get("status") in ("critical", "empty"):
                    critical += 1

    # Format last scan age
    scan_age = "—"
    if last_scan:
        try:
            dt  = datetime.fromisoformat(last_scan)
            age = (datetime.now(timezone.utc) - dt).seconds
            scan_age = f"{age // 60}m ago" if age < 3600 else f"{age // 3600}h ago"
        except Exception:
            scan_age = "—"

    def item(label: str, value: str, color: str = "muted") -> str:
        colors = {
            "green": "var(--green)", "amber": "var(--amber)",
            "red": "var(--red)",     "muted": "var(--text-secondary)",
        }
        c = colors.get(color, colors["muted"])
        return f'<div class="st-item">{label}&nbsp;<b style="color:{c}">{value}</b></div>'

    feed_color = "green" if live_feed == "connected" else "red"
    fact_color = "green" if factory_proc == "running" else "amber" if factory_proc == "starting" else "red"
    cov_color  = "red" if critical > 0 else "green"
    cov_label  = f"{ok} ok" if critical == 0 else f"{critical} critical"

    return HTMLResponse(
        item("Live", live_feed, feed_color) +
        item("Factory", factory_proc, fact_color) +
        item("Coverage", cov_label, cov_color) +
        item("Last scan", scan_age) +
        f'<div class="st-item st-right">Signals today&nbsp;<b>{sig_count}</b></div>' +
        item("Win rate", win_rate, "green" if win_rate != "—" else "muted")
    )


@router.get("/api/focus-asset/chip", response_class=HTMLResponse)
async def focus_asset_chip(request: Request):
    """Returns the focus asset topbar chip as an HTML fragment."""
    redis   = request.app.state.redis
    symbol  = await redis.get("ruby:focus:symbol") or "—"
    price   = await redis.get(f"ruby:price:{symbol}") or "—"
    chg_raw = await redis.get(f"ruby:chg:{symbol}")
    chg     = float(chg_raw) if chg_raw else 0.0
    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
    chg_cls = "pos" if chg >= 0 else "neg"
    dot_cls = "dot-green" if symbol != "—" else "dot-gray"

    return HTMLResponse(f"""
    <div class="tb-chip" id="tb-focus-asset"
         hx-get="/api/focus-asset/chip"
         hx-trigger="every 5s" hx-swap="outerHTML">
      <span class="dot {dot_cls}"></span>
      <span class="mono">{symbol}</span>
      <span class="mono info">{price}</span>
      <span class="mono {chg_cls}" style="font-size:11px">{chg_str}</span>
    </div>""")


@router.get("/api/pnl/chip", response_class=HTMLResponse)
async def pnl_chip(request: Request):
    """Returns the P&L topbar chip."""
    redis   = request.app.state.redis
    pnl_raw = await redis.get("ruby:pnl:day")
    pnl     = float(pnl_raw) if pnl_raw else 0.0
    sign    = "+" if pnl >= 0 else ""
    cls     = "pos" if pnl >= 0 else "neg"
    return HTMLResponse(f"""
    <div class="tb-chip" id="tb-pnl"
         hx-get="/api/pnl/chip"
         hx-trigger="every 10s" hx-swap="outerHTML">
      <span class="dim" style="font-size:10px">P&L</span>
      <span class="mono {cls}" style="font-size:13px;font-weight:600">{sign}${abs(pnl):.2f}</span>
    </div>""")
```

---

### How a page uses it

Every page route becomes simple. Here's the dashboard as an example:

```python
# lib/services/data/api/routes/dashboard.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from lib.services.data.api.shell import render_page
from lib.services.data.api.partials import (
    render_stat_cards,
    render_signal_list,
    render_asset_table,
    render_coverage_mini,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Each partial is a small async function that queries Redis/DB
    # and returns an HTML string
    stats    = await render_stat_cards(request)
    signals  = await render_signal_list(request, limit=8)
    assets   = await render_asset_table(request)
    coverage = await render_coverage_mini(request)

    content = f"""
    <div class="page-header">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle" id="dash-date"></p>
      </div>
      <div class="page-actions">
        <button class="btn btn-ghost"
                hx-get="/analysis"
                hx-target="body" hx-push-url="true">Morning analysis</button>
        <button class="btn btn-primary"
                hx-get="/trading"
                hx-target="body" hx-push-url="true">Trade</button>
      </div>
    </div>

    <!-- Stat cards — refreshed every 15s -->
    <div class="g4" id="stat-cards"
         hx-get="/partials/stat-cards"
         hx-trigger="every 15s"
         hx-swap="innerHTML"
         style="margin-bottom:10px">
      {stats}
    </div>

    <div class="g7030">
      <div class="col">
        <!-- Signals — refreshed by SSE push, fallback poll every 5s -->
        <div class="card" id="signal-card">
          <div class="card-header">
            <span class="card-title">Live signals</span>
            <span class="badge badge-green">● LIVE</span>
          </div>
          <div id="signal-list"
               hx-get="/partials/signals"
               hx-trigger="every 5s"
               hx-swap="innerHTML">
            {signals}
          </div>
        </div>

        <!-- Chart embed -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Chart</span>
            <span id="chart-label" class="badge badge-gray">—</span>
          </div>
          <div class="chart-wrap" style="height:160px">
            <iframe src="/charts/embed?symbol=MGC&interval=5m&theme=dark"
                    style="width:100%;height:100%;border:none;background:transparent"
                    loading="lazy"></iframe>
          </div>
        </div>
      </div>

      <div class="col">
        <!-- Asset prices -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Assets</span>
            <span class="badge badge-gray" id="asset-count">—</span>
          </div>
          <div id="asset-table"
               hx-get="/partials/assets"
               hx-trigger="every 5s"
               hx-swap="innerHTML">
            {assets}
          </div>
        </div>

        <!-- Data coverage mini -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Data coverage</span>
            <a class="badge badge-blue" href="/factory/coverage-page"
               hx-get="/factory/coverage-page"
               hx-target="body" hx-push-url="true">Details</a>
          </div>
          {coverage}
        </div>
      </div>
    </div>

    <script>
      // Fill in the local date/time client-side
      document.getElementById('dash-date').textContent =
        new Date().toLocaleDateString('en-US', {{
          weekday:'long', year:'numeric', month:'long', day:'numeric'
        }});
    </script>
    """

    return HTMLResponse(render_page(
        title="Dashboard",
        content=content,
        active_nav="dashboard",
        request=request,
    ))
```

---

### File layout summary

```
src/ruby/
├── static/
│   ├── css/
│   │   └── fks.css              ← single CSS file, replaces _SHARED_CSS
│   └── js/
│       ├── fks.js               ← sidebar, clock, SSE, API helpers, toasts
│       └── htmx.min.js          ← HTMX (copy from CDN once, serve locally)
└── src/lib/services/data/api/
    ├── shell.py                 ← render_page() — replaces old _build_page_shell()
    ├── status.py                ← /api/status/bar, /api/pnl/chip, /api/focus-asset/chip
    ├── partials.py              ← render_stat_cards(), render_signal_list(), etc.
    └── routes/
        ├── dashboard.py
        ├── trading.py
        ├── analysis.py
        ├── news.py
        └── settings.py
```

The pattern is the same for every page: call `render_page(title, content, active_nav, request)`. The shell, sidebar, statusbar, and topbar chips are identical across all pages and handled entirely by `shell.py` and `status.py`. Individual pages only own their content area.

Good — that changes everything from the sidebar pattern. Terminal layout means a persistent data strip at the top, a tab bar below it, and the full 1920px width used for split workspace panels. Let me build the exact thing first.Click the tabs — Trading, Analysis, News, Data, Settings all have distinct split-panel layouts. Now the code that makes this real, structured around the terminal pattern.

---

### `src/ruby/static/css/fks-terminal.css`

The terminal CSS system. Replaces `fks.css` for the full-width desktop layout.

```css
/* ═══════════════════════════════════════════════════════
   FKS Terminal — 1920px desktop trading terminal CSS
   ═══════════════════════════════════════════════════════ */

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  /* backgrounds — layered darks */
  --bg0: #07070d;   /* page / chart canvas */
  --bg1: #0c0c14;   /* panels, cards */
  --bg2: #11111c;   /* inner cells, inputs */
  --bg3: #16162a;   /* hover, active states */
  --bg4: #1c1c30;   /* selection highlight */

  /* borders */
  --b1: #1a1a2e;    /* structural dividers */
  --b2: #22223a;    /* card borders */
  --b3: #2a2a48;    /* focused borders */

  /* text */
  --t1: #dde0f5;    /* primary */
  --t2: #8890b8;    /* secondary / muted */
  --t3: #454870;    /* dimmed / labels */

  /* brand */
  --accent:     #5b6ef5;
  --accent-dim: rgba(91,110,245,.12);
  --accent-brd: rgba(91,110,245,.3);

  /* semantic */
  --green:      #16c784;
  --red:        #ea3943;
  --amber:      #f0a500;
  --cyan:       #00d4e8;
  --purple:     #9b8cff;
  --teal:       #2dd4bf;

  /* semantic dims */
  --green-dim:  rgba(22,199,132,.10);
  --green-brd:  rgba(22,199,132,.25);
  --red-dim:    rgba(234,57,67,.10);
  --red-brd:    rgba(234,57,67,.25);
  --amber-dim:  rgba(240,165,0,.10);
  --amber-brd:  rgba(240,165,0,.25);

  /* layout heights */
  --strip-h:    48px;
  --tabbar-h:   34px;
  --status-h:   24px;
  --radius:     3px;
  --radius-md:  5px;

  /* monospace everywhere — this is a terminal */
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--t1);
  background: var(--bg0);
}

body {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Utility classes ──────────────────────────────────── */
.pos   { color: var(--green); }
.neg   { color: var(--red); }
.warn  { color: var(--amber); }
.info  { color: var(--cyan); }
.muted { color: var(--t2); }
.dim   { color: var(--t3); }
.mono  { font-variant-numeric: tabular-nums; }
.upper { text-transform: uppercase; letter-spacing: .5px; }
.bold  { font-weight: 700; }

/* ── Persistent data strip ────────────────────────────── */
.fks-strip {
  height: var(--strip-h);
  background: var(--bg1);
  border-bottom: 1px solid var(--b2);
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
  z-index: 20;
}

.strip-logo {
  width: 64px;
  display: flex; align-items: center; justify-content: center;
  border-right: 1px solid var(--b2);
  font-size: 14px; font-weight: 700;
  color: var(--accent); letter-spacing: 1px;
  flex-shrink: 0;
  user-select: none;
}

.strip-cells {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Individual data cell in the strip */
.strip-cell {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 14px;
  border-right: 1px solid var(--b2);
  cursor: default;
  transition: background .12s;
  flex-shrink: 0;
  min-width: 0;
}
.strip-cell:hover          { background: var(--bg2); }
.strip-cell.clickable      { cursor: pointer; }
.strip-cell .lbl {
  font-size: 9px; color: var(--t3);
  letter-spacing: .5px;
  text-transform: uppercase;
  margin-bottom: 2px;
  white-space: nowrap;
}
.strip-cell .val {
  font-size: 13px; font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.strip-cell .sub {
  font-size: 9px; color: var(--t3);
  margin-top: 1px;
  white-space: nowrap;
}

/* Signals ticker — scrolling right side of strip */
.strip-ticker {
  flex: 1;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: 0 8px;
  position: relative;
  min-width: 0;
}
.strip-ticker::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0;
  width: 20px;
  background: linear-gradient(90deg, var(--bg1), transparent);
  z-index: 1;
}
.ticker-scroll {
  display: flex;
  gap: 16px;
  animation: ticker-slide 40s linear infinite;
  white-space: nowrap;
}
@keyframes ticker-slide {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
.tick {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: var(--radius);
  flex-shrink: 0;
}
.tick-l { background: var(--green-dim); border: 1px solid var(--green-brd); }
.tick-s { background: var(--red-dim);   border: 1px solid var(--red-brd); }
.tick .dir { font-weight: 700; font-size: 9px; }

/* Strip right — kill + clock */
.strip-right {
  display: flex; align-items: center; gap: 10px;
  padding: 0 14px;
  border-left: 1px solid var(--b2);
  flex-shrink: 0;
}
.kill-btn {
  padding: 4px 10px;
  font-size: 10px; font-weight: 700;
  font-family: inherit; letter-spacing: .5px;
  background: transparent;
  border: 1px solid var(--red-brd);
  color: var(--red);
  border-radius: var(--radius);
  cursor: pointer;
  transition: background .12s;
}
.kill-btn:hover { background: var(--red-dim); }
.fks-clock {
  font-size: 12px; color: var(--t2);
  font-variant-numeric: tabular-nums;
  min-width: 56px; text-align: right;
}

/* ── Tab bar ──────────────────────────────────────────── */
.fks-tabbar {
  height: var(--tabbar-h);
  background: var(--bg1);
  border-bottom: 2px solid var(--b2);
  display: flex;
  align-items: flex-end;
  flex-shrink: 0;
  padding: 0 4px;
  gap: 2px;
  z-index: 19;
}
.fks-tab {
  padding: 0 16px;
  height: 30px;
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 500;
  color: var(--t3);
  border-radius: var(--radius) var(--radius) 0 0;
  cursor: pointer;
  border: 1px solid transparent;
  border-bottom: none;
  transition: color .12s, background .12s;
  white-space: nowrap;
  letter-spacing: .2px;
  user-select: none;
  text-decoration: none;
}
.fks-tab:hover  { color: var(--t2); background: var(--bg2); }
.fks-tab.active {
  color: var(--t1);
  background: var(--bg0);
  border-color: var(--b2);
}
.fks-tab .tab-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}
.fks-tab .tab-badge {
  font-size: 8px;
  background: var(--red);
  color: white;
  border-radius: 8px;
  padding: 1px 4px;
}
.tabbar-spacer { flex: 1; }
.tabbar-actions {
  display: flex; align-items: center; gap: 4px;
  padding-bottom: 4px;
}
.icon-btn {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  color: var(--t3); cursor: pointer;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 13px;
  transition: all .12s;
}
.icon-btn:hover {
  color: var(--t2);
  background: var(--bg2);
  border-color: var(--b2);
}

/* ── Status strip ─────────────────────────────────────── */
.fks-statusbar {
  height: var(--status-h);
  background: var(--bg1);
  border-bottom: 1px solid var(--b1);
  display: flex; align-items: center;
  padding: 0 10px; gap: 14px;
  flex-shrink: 0;
  overflow: hidden;
}
.st-item {
  display: flex; align-items: center; gap: 4px;
  font-size: 9px; color: var(--t3);
  white-space: nowrap;
}
.st-item b { font-weight: 600; }
.st-sep  { width: 1px; height: 12px; background: var(--b2); flex-shrink: 0; }
.st-right { margin-left: auto; }
.live-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.live-dot.green { background: var(--green); box-shadow: 0 0 3px var(--green); }
.live-dot.amber { background: var(--amber); }
.live-dot.red   { background: var(--red); }
.live-dot.gray  { background: var(--t3); }

/* ── Workspace ────────────────────────────────────────── */
.fks-workspace {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Pages — only the active one is shown */
.fks-page {
  display: none;
  flex: 1;
  overflow: hidden;
}
.fks-page.active { display: flex; }

/* Panes within a page — horizontal split panels */
.pane {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}
.pane-border { border-right: 1px solid var(--b2); }

/* Preset widths — mix and match per page */
.p-15  { width: 15%; flex-shrink: 0; }
.p-20  { width: 20%; flex-shrink: 0; }
.p-25  { width: 25%; flex-shrink: 0; }
.p-30  { width: 30%; flex-shrink: 0; }
.p-35  { width: 35%; flex-shrink: 0; }
.p-40  { width: 40%; flex-shrink: 0; }
.p-50  { width: 50%; flex-shrink: 0; }
.p-60  { width: 60%; flex-shrink: 0; }
.p-grow { flex: 1; min-width: 0; }

/* ── Panel cards ──────────────────────────────────────── */
.panel {
  background: var(--bg1);
  border: 1px solid var(--b2);
  border-radius: var(--radius);
}
.panel.grow { flex: 1; display: flex; flex-direction: column; }

.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 10px;
  border-bottom: 1px solid var(--b1);
  font-size: 9px; color: var(--t3);
  letter-spacing: .5px; text-transform: uppercase;
  flex-shrink: 0;
}
.panel-head .live-label { color: var(--green); }
.panel-body { padding: 8px 10px; }
.panel-body.grow { flex: 1; overflow: auto; }

/* ── Data row ─────────────────────────────────────────── */
.drow {
  display: flex; align-items: center; gap: 6px;
  padding: 3px 0;
  border-bottom: 1px solid var(--b1);
}
.drow:last-child { border-bottom: none; }

/* ── Signal row ───────────────────────────────────────── */
.srow {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 0;
  border-bottom: 1px solid var(--b1);
}
.srow:last-child { border-bottom: none; }
.srow-dir {
  width: 34px; height: 16px;
  border-radius: 2px;
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; font-weight: 700; flex-shrink: 0;
}
.dir-l { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-brd); }
.dir-s { background: var(--red-dim);   color: var(--red);   border: 1px solid var(--red-brd); }
.dir-c { background: var(--amber-dim); color: var(--amber); border: 1px solid var(--amber-brd); }

/* ── Badge ────────────────────────────────────────────── */
.badge {
  font-size: 8px; padding: 1px 5px;
  border-radius: 2px; font-weight: 700;
  white-space: nowrap;
}
.badge-green  { background: var(--green-dim); color: var(--green); }
.badge-red    { background: var(--red-dim);   color: var(--red); }
.badge-amber  { background: var(--amber-dim); color: var(--amber); }
.badge-blue   { background: var(--accent-dim); color: var(--accent); }
.badge-gray   { background: var(--bg3); color: var(--t2); }

/* ── Buttons ──────────────────────────────────────────── */
.btn {
  padding: 5px 12px;
  border-radius: var(--radius);
  font-size: 10px; font-weight: 700;
  font-family: inherit; letter-spacing: .3px;
  cursor: pointer; border: none;
  transition: all .12s;
}
.btn-primary { background: var(--accent-dim); color: var(--accent); border: 1px solid var(--accent-brd); }
.btn-primary:hover { background: rgba(91,110,245,.2); }
.btn-ghost { background: transparent; color: var(--t2); border: 1px solid var(--b2); }
.btn-ghost:hover { color: var(--t1); border-color: var(--b3); background: var(--bg2); }
.btn-buy  { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-brd); }
.btn-sell { background: var(--red-dim);   color: var(--red);   border: 1px solid var(--red-brd); }
.btn-wide { width: 100%; text-align: center; padding: 8px; font-size: 11px; }

/* ── Form inputs ──────────────────────────────────────── */
.field-group { display: flex; flex-direction: column; gap: 2px; }
.field-label {
  font-size: 9px; color: var(--t3);
  text-transform: uppercase; letter-spacing: .3px;
}
.field-input {
  background: var(--bg2);
  border: 1px solid var(--b2);
  border-radius: var(--radius);
  padding: 5px 7px;
  font-size: 11px; color: var(--t1);
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  outline: none; width: 100%;
  transition: border-color .12s;
}
.field-input:focus       { border-color: var(--accent); }
.field-input.buy-border  { border-color: var(--green-brd); }
.field-input.sell-border { border-color: var(--red-brd); }

/* ── Progress / coverage bar ──────────────────────────── */
.prog-wrap { height: 3px; background: var(--bg3); border-radius: 2px; overflow: hidden; }
.prog-fill { height: 100%; border-radius: 2px; transition: width .3s; }
.pf-green { background: var(--green); }
.pf-amber { background: var(--amber); }
.pf-red   { background: var(--red); }

/* ── Inner tabs ───────────────────────────────────────── */
.inner-tabs {
  display: flex; gap: 0;
  border-bottom: 1px solid var(--b1);
  margin-bottom: 8px;
}
.inner-tab {
  padding: 4px 10px;
  font-size: 10px; color: var(--t3);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all .12s;
}
.inner-tab.active { color: var(--t1); border-bottom-color: var(--accent); }
.inner-tab:hover:not(.active) { color: var(--t2); }

/* ── Chart area ───────────────────────────────────────── */
.chart-area {
  background: var(--bg0);
  border-radius: var(--radius);
  flex: 1;
  position: relative;
  overflow: hidden;
}
.chart-label {
  position: absolute; top: 6px; left: 8px;
  font-size: 9px; color: var(--t3);
}
.chart-price {
  position: absolute; top: 6px; right: 8px;
  font-size: 11px; font-weight: 700;
  color: var(--cyan);
  font-variant-numeric: tabular-nums;
}

/* ── Stat cell ────────────────────────────────────────── */
.stat-cell {
  background: var(--bg2);
  border-radius: var(--radius);
  padding: 7px 8px;
}
.stat-lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: .4px; }
.stat-num { font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; margin-top: 2px; }
.stat-sub { font-size: 9px; color: var(--t3); margin-top: 1px; }

/* ── Toast notifications ──────────────────────────────── */
#fks-toasts {
  position: fixed; bottom: 16px; right: 16px;
  display: flex; flex-direction: column; gap: 6px;
  z-index: 999; pointer-events: none;
}
.toast {
  padding: 7px 12px;
  background: var(--bg2);
  border: 1px solid var(--b2);
  border-radius: var(--radius);
  font-size: 11px;
  max-width: 300px;
  pointer-events: auto;
  animation: toast-in .18s ease;
}
.toast.success { border-color: var(--green-brd); }
.toast.error   { border-color: var(--red-brd); color: var(--red); }
.toast.warning { border-color: var(--amber-brd); color: var(--amber); }
@keyframes toast-in {
  from { opacity: 0; transform: translateX(12px); }
  to   { opacity: 1; transform: none; }
}

/* ── HTMX loading ─────────────────────────────────────── */
.htmx-indicator { opacity: 0; transition: opacity .15s; }
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator { opacity: 1; }

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--b2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--b3); }

/* ── Responsive — collapse panes on narrow screens ─────── */
@media (max-width: 1400px) {
  .p-25 { width: 28%; }
  .p-20 { width: 24%; }
}
@media (max-width: 1024px) {
  .fks-page { flex-wrap: wrap; overflow: auto; }
  .pane { width: 100% !important; border-right: none !important; border-bottom: 1px solid var(--b2); }
}
```

---

### `src/ruby/static/js/fks-terminal.js`

```javascript
/* fks-terminal.js — terminal runtime */
'use strict';

// ── Clock ──────────────────────────────────────────────
const Clock = {
  start() {
    const el = document.getElementById('fks-clock');
    if (!el) return;
    const tick = () => {
      const d = new Date(), p = n => String(n).padStart(2,'0');
      el.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    };
    tick();
    setInterval(tick, 1000);
  }
};

// ── Tabs ───────────────────────────────────────────────
const Tabs = {
  init() {
    document.querySelectorAll('.fks-tab[data-page]').forEach(tab => {
      tab.addEventListener('click', () => this.activate(tab.dataset.page));
    });
    // Restore last active tab
    const saved = sessionStorage.getItem('fks:tab') || 'overview';
    this.activate(saved, false);
  },

  activate(pageId, save = true) {
    document.querySelectorAll('.fks-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.fks-page').forEach(p => p.classList.remove('active'));

    const tab  = document.querySelector(`.fks-tab[data-page="${pageId}"]`);
    const page = document.getElementById(`page-${pageId}`);

    tab?.classList.add('active');
    page?.classList.add('active');

    if (save) sessionStorage.setItem('fks:tab', pageId);
  }
};

// ── Inner tabs ─────────────────────────────────────────
// Usage: <div class="inner-tabs" data-group="orders">
//          <div class="inner-tab active" data-tab="open">Open</div>
//        </div>
//        <div data-panel="open">...</div>
const InnerTabs = {
  init() {
    document.addEventListener('click', e => {
      const tab = e.target.closest('.inner-tab');
      if (!tab) return;
      const group  = tab.closest('.inner-tabs');
      const target = tab.dataset.tab;
      if (!group || !target) return;
      group.querySelectorAll('.inner-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const card = tab.closest('.panel, .wcard') || tab.parentElement.parentElement;
      card.querySelectorAll('[data-panel]').forEach(p => {
        p.style.display = p.dataset.panel === target ? '' : 'none';
      });
    });
  }
};

// ── SSE ────────────────────────────────────────────────
const SSE = {
  _pool: {},
  _backoff: {},

  connect(name, url, onData, onError) {
    this.disconnect(name);
    const es = new EventSource(url);
    es.onmessage = e => {
      try { onData(JSON.parse(e.data)); } catch { onData(e.data); }
      this._backoff[name] = 1000;
    };
    es.onerror = err => {
      onError?.(err);
      es.close();
      delete this._pool[name];
      const d = this._backoff[name] || 1000;
      this._backoff[name] = Math.min(d * 2, 30000);
      setTimeout(() => this.connect(name, url, onData, onError), d);
    };
    this._pool[name] = es;
  },

  disconnect(name) {
    this._pool[name]?.close();
    delete this._pool[name];
  }
};

// ── Strip updater ──────────────────────────────────────
// Subscribes to SSE and updates strip cells by data-strip-* attributes.
//
// DOM usage:
//   <div class="strip-cell" data-strip-sym="MGC">
//     <div class="lbl">Focus</div>
//     <div class="val info" data-strip-price="MGC">—</div>
//     <div class="sub" data-strip-chg="MGC">—</div>
//   </div>
const Strip = {
  init() {
    SSE.connect('strip', '/sse/strip', data => {
      if (!data) return;
      // Price
      if (data.symbol && data.price) {
        document.querySelectorAll(`[data-strip-price="${data.symbol}"]`).forEach(el => {
          el.textContent = Fmt.price(data.price);
        });
      }
      // % change
      if (data.symbol && data.change_pct !== undefined) {
        document.querySelectorAll(`[data-strip-chg="${data.symbol}"]`).forEach(el => {
          el.textContent = Fmt.pct(data.change_pct);
          el.className   = el.className.replace(/\b(pos|neg)\b/g, '') +
                           (data.change_pct >= 0 ? ' pos' : ' neg');
        });
      }
      // P&L
      if (data.pnl !== undefined) {
        document.querySelectorAll('[data-strip-pnl]').forEach(el => {
          el.textContent = Fmt.currency(data.pnl);
          el.className   = el.className.replace(/\b(pos|neg)\b/g, '') +
                           (data.pnl >= 0 ? ' pos' : ' neg');
        });
      }
      // Signal count badge
      if (data.signal_count !== undefined) {
        document.querySelectorAll('[data-strip-signals]').forEach(el => {
          el.textContent = data.signal_count;
        });
        // Update trading tab badge
        const badge = document.querySelector('.fks-tab[data-page="trading"] .tab-badge');
        if (badge) badge.textContent = data.signal_count;
      }
    });
  }
};

// ── API ────────────────────────────────────────────────
const API = {
  _key: document.querySelector('meta[name=api-key]')?.content || '',

  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this._key) h['X-API-Key'] = this._key;
    return h;
  },

  async get(path)       { return this._req('GET',   path); },
  async post(path, body){ return this._req('POST',  path, body); },
  async patch(path, body){ return this._req('PATCH', path, body); },

  async _req(method, path, body) {
    const opts = { method, headers: this._headers() };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`);
    return r.json();
  }
};

// ── Toasts ─────────────────────────────────────────────
const Toast = {
  _container: null,

  init() {
    this._container = document.getElementById('fks-toasts');
    if (!this._container) {
      this._container = Object.assign(document.createElement('div'), { id: 'fks-toasts' });
      document.body.appendChild(this._container);
    }
  },

  show(msg, type = '', ms = 3500) {
    const el = Object.assign(document.createElement('div'), {
      className: `toast ${type}`,
      textContent: msg
    });
    this._container.appendChild(el);
    setTimeout(() => el.remove(), ms);
  },

  success(m) { this.show(m, 'success'); },
  error(m)   { this.show(m, 'error', 5000); },
  warning(m) { this.show(m, 'warning'); },
};

// ── Format ─────────────────────────────────────────────
const Fmt = {
  price(v, dp = 2) {
    return Number(v).toLocaleString('en-US', {
      minimumFractionDigits: dp, maximumFractionDigits: dp
    });
  },
  currency(v, dp = 2) {
    return (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(dp);
  },
  pct(v, dp = 2) {
    return (v >= 0 ? '+' : '') + v.toFixed(dp) + '%';
  },
  relTime(iso) {
    const s = (Date.now() - new Date(iso)) / 1000;
    if (s < 60)   return `${Math.floor(s)}s`;
    if (s < 3600) return `${Math.floor(s/60)}m`;
    return `${Math.floor(s/3600)}h`;
  },
  sentiment(compound) {
    if (compound >=  0.05) return { label: 'POS', cls: 'badge-green' };
    if (compound <= -0.05) return { label: 'NEG', cls: 'badge-red' };
    return { label: 'NEU', cls: 'badge-gray' };
  }
};

// ── Keyboard shortcuts ─────────────────────────────────
const Keys = {
  init() {
    document.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT') return;
      // Number keys 1-8 switch tabs
      const tabMap = { '1':'overview','2':'trading','3':'analysis',
                       '4':'charts','5':'news','6':'data','7':'journal','8':'settings' };
      if (tabMap[e.key]) { Tabs.activate(tabMap[e.key]); return; }
      // Ctrl+Shift+K = kill switch
      if (e.ctrlKey && e.shiftKey && e.key === 'K') {
        if (confirm('Activate kill switch?')) {
          API.post('/api/kill-switch').then(() => Toast.warning('Kill switch activated'));
        }
      }
    });
  }
};

// ── Boot ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  Clock.start();
  Tabs.init();
  InnerTabs.init();
  Toast.init();
  Strip.init();
  Keys.init();
});

// Expose globally for inline scripts in templates
window.FKS = { API, SSE, Tabs, Toast, Fmt };
```

---

### `src/ruby/src/lib/services/data/api/shell.py` — terminal version

This replaces the previous `shell.py` entirely. The terminal shell has no sidebar.

```python
"""
Terminal shell — renders the full-page trading terminal layout.

Every page route calls render_terminal() with its workspace HTML.
The shell owns: persistent strip, tab bar, status strip.
The page owns: its pane layout inside .fks-workspace.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TabDef:
    id:       str
    label:    str
    dot:      str = ""    # CSS color for dot indicator, e.g. "var(--cyan)"
    badge_id: str = ""    # DOM id for dynamic badge number


TABS: list[TabDef] = [
    TabDef("overview",  "Overview",  "var(--cyan)"),
    TabDef("trading",   "Trading",   "var(--green)", badge_id="tab-signal-badge"),
    TabDef("analysis",  "Analysis",  "var(--purple)"),
    TabDef("charts",    "Charts"),
    TabDef("news",      "News"),
    TabDef("data",      "Data"),
    TabDef("journal",   "Journal"),
    TabDef("settings",  "Settings"),
]


def render_terminal(
    workspace: str,
    active_tab: str = "overview",
    request=None,
    extra_head: str = "",
    extra_scripts: str = "",
    page_title: str = "FKS Terminal",
) -> str:
    """
    Returns a complete HTML document for the terminal layout.

    Args:
        workspace:   The full inner HTML — all .fks-page divs.
                     Each page must have id="page-{tab_id}" and class="fks-page".
        active_tab:  Which tab to activate on load (also set by JS from sessionStorage).
        request:     FastAPI Request — reads app.state for API key etc.
        extra_head:  Additional <head> elements.
        extra_scripts: Additional <script> blocks before </body>.
    """
    api_key = ""
    if request:
        api_key = getattr(request.app.state, "api_key", "")

    strip_html   = _render_strip()
    tabbar_html  = _render_tabbar(active_tab)
    status_html  = _render_status()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="api-key" content="{_esc(api_key)}">
  <title>{_esc(page_title)}</title>
  <link rel="stylesheet" href="/static/css/fks-terminal.css">
  <script src="/static/js/htmx.min.js" defer></script>
  <script src="/static/js/fks-terminal.js" defer></script>
  {extra_head}
</head>
<body>
  {strip_html}
  {tabbar_html}
  {status_html}
  <div class="fks-workspace">
    {workspace}
  </div>
  <div id="fks-toasts"></div>
  {extra_scripts}
</body>
</html>"""


# ── Persistent data strip ──────────────────────────────────────────────────

def _render_strip() -> str:
    return """
<div class="fks-strip" id="fks-strip">
  <div class="strip-logo">FKS</div>
  <div class="strip-cells">

    <!-- Focus asset — HTMX refreshes the inner content every 3s -->
    <div class="strip-cell clickable"
         title="Click to change focus asset"
         hx-get="/api/strip/focus"
         hx-trigger="every 3s"
         hx-swap="outerHTML"
         id="strip-focus">
      <div class="lbl" id="strip-focus-label">Focus</div>
      <div class="val info mono" id="strip-focus-price"
           data-strip-price="MGC">—</div>
      <div class="sub" id="strip-focus-chg"
           data-strip-chg="MGC">—</div>
    </div>

    <!-- Day P&L -->
    <div class="strip-cell"
         hx-get="/api/strip/pnl"
         hx-trigger="every 5s"
         hx-swap="outerHTML"
         id="strip-pnl">
      <div class="lbl">Day P&L</div>
      <div class="val mono" id="strip-pnl-val" data-strip-pnl>—</div>
      <div class="sub dim">Open: <span id="strip-open-pnl">$0.00</span></div>
    </div>

    <!-- Drawdown -->
    <div class="strip-cell"
         hx-get="/api/strip/risk"
         hx-trigger="every 10s"
         hx-swap="outerHTML"
         id="strip-risk">
      <div class="lbl">DD used</div>
      <div class="val warn mono" id="strip-dd">—</div>
      <div class="sub dim" id="strip-dd-limit">of limit</div>
    </div>

    <!-- Session -->
    <div class="strip-cell"
         hx-get="/api/strip/session"
         hx-trigger="every 30s"
         hx-swap="outerHTML"
         id="strip-session">
      <div class="lbl">Session</div>
      <div class="val" id="strip-session-name" style="font-size:11px">—</div>
      <div class="sub dim" id="strip-session-close">—</div>
    </div>

    <!-- Regime -->
    <div class="strip-cell"
         hx-get="/api/strip/regime"
         hx-trigger="every 15s"
         hx-swap="outerHTML"
         id="strip-regime">
      <div class="lbl">Regime</div>
      <div class="val warn mono" id="strip-regime-val" style="font-size:11px">—</div>
      <div class="sub dim" id="strip-regime-conf">—</div>
    </div>

    <!-- Win rate -->
    <div class="strip-cell"
         hx-get="/api/strip/performance"
         hx-trigger="every 30s"
         hx-swap="outerHTML"
         id="strip-perf">
      <div class="lbl">Win rate</div>
      <div class="val pos mono" id="strip-winrate">—</div>
      <div class="sub dim"><span id="strip-sig-count" data-strip-signals>0</span> signals</div>
    </div>

    <!-- Scrolling signals ticker -->
    <div class="strip-ticker">
      <div class="ticker-scroll" id="fks-ticker"
           hx-get="/api/strip/ticker"
           hx-trigger="every 10s"
           hx-swap="innerHTML">
        <span class="dim" style="font-size:9px">Loading signals…</span>
      </div>
    </div>

  </div>
  <div class="strip-right">
    <button class="kill-btn"
            hx-post="/api/kill-switch"
            hx-confirm="Activate kill switch? This will cancel all open orders and disable execution."
            hx-swap="none">KILL</button>
    <span class="fks-clock" id="fks-clock">--:--:--</span>
  </div>
</div>"""


# ── Tab bar ────────────────────────────────────────────────────────────────

def _render_tabbar(active_id: str) -> str:
    tabs_html = ""
    for tab in TABS:
        active = "active" if tab.id == active_id else ""
        dot    = f'<span class="tab-dot" style="background:{tab.dot}"></span>' if tab.dot else ""
        badge  = f'<span class="tab-badge" id="{tab.badge_id}">0</span>' if tab.badge_id else ""
        tabs_html += f"""
    <div class="fks-tab {active}" data-page="{tab.id}">{dot}{_esc(tab.label)}{badge}</div>"""

    return f"""
<nav class="fks-tabbar" id="fks-tabbar">
  {tabs_html}
  <div class="tabbar-spacer"></div>
  <div class="tabbar-actions">
    <div class="icon-btn" title="Split view" onclick="FKS.Toast.show('Split view coming soon')">⊞</div>
    <div class="icon-btn" title="Keyboard shortcuts" onclick="FKS.Toast.show('1-8: switch tabs  Ctrl+Shift+K: kill switch')">?</div>
  </div>
</nav>"""


# ── Status strip ───────────────────────────────────────────────────────────

def _render_status() -> str:
    """
    Status strip content is refreshed every 30s via HTMX.
    The inner content is served by GET /api/status/strip.
    """
    return """
<div class="fks-statusbar"
     id="fks-statusbar"
     hx-get="/api/status/strip"
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
  <div class="st-item dim">Loading…</div>
</div>"""


# ── Escape ────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
```

---

### `src/ruby/src/lib/services/data/api/strip.py` — all strip endpoints

Every cell in the persistent strip is its own HTMX fragment endpoint. They refresh independently so a slow API call for regime detection doesn't block the P&L from updating.

```python
"""
Strip endpoints — each cell in the persistent data strip is
a separate HTMX partial that refreshes at its own cadence.

All return HTML fragments, not JSON.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/strip", tags=["strip"])


@router.get("/focus", response_class=HTMLResponse)
async def strip_focus(request: Request):
    redis  = request.app.state.redis
    symbol = (await redis.get("ruby:focus:symbol")) or "—"
    price  = (await redis.get(f"ruby:price:{symbol}")) or "—"
    chg_r  = await redis.get(f"ruby:chg_pct:{symbol}")
    chg    = float(chg_r) if chg_r else 0.0
    chg_s  = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
    chg_c  = "pos" if chg >= 0 else "neg"

    return HTMLResponse(f"""
<div class="strip-cell clickable"
     hx-get="/api/strip/focus" hx-trigger="every 3s" hx-swap="outerHTML"
     id="strip-focus">
  <div class="lbl">Focus · {symbol}</div>
  <div class="val info mono" data-strip-price="{symbol}">{price}</div>
  <div class="sub {chg_c}" data-strip-chg="{symbol}">{chg_s}</div>
</div>""")


@router.get("/pnl", response_class=HTMLResponse)
async def strip_pnl(request: Request):
    redis    = request.app.state.redis
    day_r    = await redis.get("ruby:pnl:day")
    open_r   = await redis.get("ruby:pnl:open")
    day_pnl  = float(day_r)  if day_r  else 0.0
    open_pnl = float(open_r) if open_r else 0.0
    d_sign   = "+" if day_pnl  >= 0 else ""
    o_sign   = "+" if open_pnl >= 0 else ""
    d_cls    = "pos" if day_pnl >= 0 else "neg"

    return HTMLResponse(f"""
<div class="strip-cell"
     hx-get="/api/strip/pnl" hx-trigger="every 5s" hx-swap="outerHTML"
     id="strip-pnl">
  <div class="lbl">Day P&L</div>
  <div class="val {d_cls} mono" data-strip-pnl>{d_sign}${abs(day_pnl):.2f}</div>
  <div class="sub dim">Open: <span>{o_sign}${abs(open_pnl):.2f}</span></div>
</div>""")


@router.get("/risk", response_class=HTMLResponse)
async def strip_risk(request: Request):
    redis   = request.app.state.redis
    pnl_r   = await redis.get("ruby:pnl:day")
    limit_r = await redis.get("ruby:risk:daily_limit")
    pnl     = float(pnl_r)   if pnl_r   else 0.0
    limit   = float(limit_r) if limit_r else 1400.0
    used    = (abs(pnl) / limit * 100) if pnl < 0 else 0.0
    cls     = "pos" if used < 50 else "warn" if used < 80 else "neg"

    return HTMLResponse(f"""
<div class="strip-cell"
     hx-get="/api/strip/risk" hx-trigger="every 10s" hx-swap="outerHTML"
     id="strip-risk">
  <div class="lbl">DD used</div>
  <div class="val {cls} mono">{used:.1f}%</div>
  <div class="sub dim">of ${limit:,.0f}</div>
</div>""")


@router.get("/session", response_class=HTMLResponse)
async def strip_session(request: Request):
    redis   = request.app.state.redis
    name_r  = await redis.get("ruby:session:name")
    close_r = await redis.get("ruby:session:closes")
    name    = name_r  or "—"
    closes  = close_r or "—"

    return HTMLResponse(f"""
<div class="strip-cell"
     hx-get="/api/strip/session" hx-trigger="every 30s" hx-swap="outerHTML"
     id="strip-session">
  <div class="lbl">Session</div>
  <div class="val mono" style="font-size:11px">{name}</div>
  <div class="sub dim">{closes}</div>
</div>""")


@router.get("/regime", response_class=HTMLResponse)
async def strip_regime(request: Request):
    redis  = request.app.state.redis
    sym_r  = await redis.get("ruby:focus:symbol")
    sym    = sym_r or "—"
    reg_r  = await redis.get(f"ruby:regime:{sym}:label")
    conf_r = await redis.get(f"ruby:regime:{sym}:confidence")
    regime = reg_r  or "UNKNOWN"
    conf   = f"{float(conf_r)*100:.0f}%" if conf_r else "—"
    cls    = "warn" if regime == "TRENDING" else "info" if regime == "RANGING" else "neg"

    return HTMLResponse(f"""
<div class="strip-cell"
     hx-get="/api/strip/regime" hx-trigger="every 15s" hx-swap="outerHTML"
     id="strip-regime">
  <div class="lbl">Regime · {sym}</div>
  <div class="val {cls} mono" style="font-size:11px">{regime}</div>
  <div class="sub dim">HMM {conf}</div>
</div>""")


@router.get("/performance", response_class=HTMLResponse)
async def strip_performance(request: Request):
    redis  = request.app.state.redis
    wr_r   = await redis.get("ruby:signals:win_rate")
    cnt_r  = await redis.get("ruby:signals:today:count")
    wr     = float(wr_r)  if wr_r  else 0.0
    cnt    = int(cnt_r)   if cnt_r else 0

    return HTMLResponse(f"""
<div class="strip-cell"
     hx-get="/api/strip/performance" hx-trigger="every 30s" hx-swap="outerHTML"
     id="strip-perf">
  <div class="lbl">Win rate</div>
  <div class="val pos mono">{wr:.1f}%</div>
  <div class="sub dim"><span data-strip-signals>{cnt}</span> signals today</div>
</div>""")


@router.get("/ticker", response_class=HTMLResponse)
async def strip_ticker(request: Request):
    """
    Returns the scrolling signal ticker inner HTML.
    Reads the last N signals from Redis.
    """
    redis    = request.app.state.redis
    raw      = await redis.lrange("ruby:signals:recent", 0, 19)  # last 20
    if not raw:
        return HTMLResponse('<span class="dim" style="font-size:9px">No signals yet</span>')

    items = []
    for r in raw:
        try:
            s = json.loads(r)
            direction = s.get("direction", "").upper()
            symbol    = s.get("symbol", "")
            price     = s.get("price", "")
            conf      = s.get("confidence", 0)
            cls       = "tick-l" if direction == "LONG" else "tick-s"
            dir_lbl   = "L" if direction == "LONG" else "S"
            items.append(
                f'<span class="tick {cls}">'
                f'<span class="dir">{dir_lbl}</span>'
                f'<span>{symbol} {price}</span>'
                f'<span class="dim">CNN {conf:.0f}%</span>'
                f'</span>'
            )
        except Exception:
            continue

    # Duplicate for seamless CSS scroll loop
    inner = "".join(items)
    return HTMLResponse(inner + inner)


@router.get("/strip", tags=["status"])
async def status_strip_html(request: Request):
    """Status bar inner HTML — polled every 30s."""
    redis = request.app.state.redis

    async def rget(k, d="—"):
        v = await redis.get(k)
        return v if v else d

    live   = await rget("ruby:live:feed:status", "unknown")
    factory = await rget("ruby:factory:health", "unknown")
    redis_s = await rget("ruby:health:redis", "ok")
    janus  = await rget("ruby:janus:status", "unknown")
    model  = await rget("ruby:model:version", "—")

    # Coverage
    registry = request.app.state.asset_registry
    try:
        assets  = await registry.enabled_assets()
        ok = critical = 0
        for a in assets:
            for t in a.window_targets:
                raw = await redis.get(f"ruby:coverage:{a.symbol}:{t.interval.value}")
                if raw:
                    d = json.loads(raw)
                    if d.get("status") == "ok": ok += 1
                    elif d.get("status") in ("critical","empty"): critical += 1
    except Exception:
        ok = critical = -1

    def st(label, val, color="var(--t2)"):
        return f'<div class="st-item">{label}&nbsp;<b style="color:{color}">{val}</b></div>'

    live_color    = "var(--green)" if live == "connected" else "var(--red)"
    factory_color = "var(--green)" if factory == "running" else "var(--amber)"
    cov_label     = f"{ok} ok" if critical == 0 else f"{critical} critical"
    cov_color     = "var(--green)" if critical == 0 else "var(--red)"
    janus_color   = "var(--green)" if janus == "connected" else "var(--t3)"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return HTMLResponse(
        f'<div class="st-item"><span class="live-dot green"></span>&nbsp;'
        f'<b class="pos">LIVE</b>&nbsp;{live}</div>'
        f'<div class="st-sep"></div>'
        + st("Factory", factory, factory_color)
        + st("Coverage", cov_label, cov_color)
        + st("Redis", redis_s, "var(--green)")
        + st("Janus", janus, janus_color)
        + st("CNN", model, "var(--t2)")
        + f'<div class="st-item st-right"><span class="dim">Build</span>&nbsp;<b class="dim">{now}</b></div>'
    )
```

---

### How a workspace page is structured

Each route builds its split panes and calls `render_terminal()`. Here's the overview page as a template:

```python
# lib/services/data/api/routes/overview.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from lib.services.data.api.shell import render_terminal
from lib.services.data.api import partials

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.get("/overview", response_class=HTMLResponse)
async def overview(request: Request):
    # Each partial is an async function → HTML string
    market  = await partials.market_table(request)
    stats   = await partials.stat_cells(request)
    signals = await partials.signal_list(request, limit=6)
    news    = await partials.news_mini(request, limit=3)
    coverage = await partials.coverage_mini(request)

    workspace = f"""

<!-- OVERVIEW -->
<div class="fks-page active" id="page-overview">
  <div class="pane p-25 pane-border">
    <div class="panel">
      <div class="panel-head">Market <span class="live-label">● LIVE</span></div>
      <div class="panel-body"
           hx-get="/partials/market-table"
           hx-trigger="every 3s"
           hx-swap="innerHTML">{market}</div>
    </div>
    <div class="panel">
      <div class="panel-head">Stats</div>
      <div class="panel-body">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px"
             hx-get="/partials/stat-cells"
             hx-trigger="every 10s"
             hx-swap="innerHTML">{stats}</div>
      </div>
    </div>
  </div>

  <div class="pane p-50 pane-border">
    <div class="panel grow">
      <div class="panel-head">
        <span id="chart-label">MGC · 5m</span>
        <span class="live-label" id="chart-live-price">● —</span>
      </div>
      <div class="panel-body grow">
        <div class="chart-area" style="height:100%;min-height:200px">
          <iframe src="/charts/embed?symbol=MGC&interval=5m&theme=terminal"
                  style="width:100%;height:100%;border:none"
                  loading="lazy" id="main-chart-frame"></iframe>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head">Signals <span class="live-label">● LIVE</span></div>
      <div class="panel-body"
           id="signal-list"
           hx-get="/partials/signals"
           hx-trigger="every 4s"
           hx-swap="innerHTML">{signals}</div>
    </div>
  </div>

  <div class="pane p-grow">
    <div class="panel">
      <div class="panel-head">News · matched assets</div>
      <div class="panel-body"
           hx-get="/partials/news-mini"
           hx-trigger="every 60s"
           hx-swap="innerHTML">{news}</div>
    </div>
    <div class="panel">
      <div class="panel-head">Data coverage</div>
      <div class="panel-body"
           hx-get="/partials/coverage-mini"
           hx-trigger="every 120s"
           hx-swap="innerHTML">{coverage}</div>
    </div>
  </div>
</div>


<!-- All other pages are loaded lazily via HTMX when tab is clicked -->
<div class="fks-page" id="page-trading"
     hx-get="/workspaces/trading"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-analysis"
     hx-get="/workspaces/analysis"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-charts"
     hx-get="/workspaces/charts"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-news"
     hx-get="/workspaces/news"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-data"
     hx-get="/workspaces/data"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-journal"
     hx-get="/workspaces/journal"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>

<div class="fks-page" id="page-settings"
     hx-get="/workspaces/settings"
     hx-trigger="intersect once"
     hx-swap="innerHTML"></div>
"""

    return HTMLResponse(render_terminal(
        workspace=workspace,
        active_tab="overview",
        request=request,
    ))
```

The `hx-trigger="intersect once"` on the non-active pages means they're lazy-loaded the first time you click their tab — no wasted server calls on page load. The overview hydrates fully on load since it's the default, everything else loads on demand.

---

### The final file map

```
src/ruby/
├── static/
│   ├── css/
│   │   └── fks-terminal.css        ← single CSS file
│   └── js/
│       ├── fks-terminal.js         ← tabs, SSE, toasts, keyboard shortcuts
│       └── htmx.min.js             ← HTMX (pin to 1.9.x, serve locally)
└── src/lib/services/data/api/
    ├── shell.py                    ← render_terminal() — strip + tabbar + status
    ├── strip.py                    ← /api/strip/* cell endpoints
    ├── status.py                   ← /api/status/strip
    ├── partials.py                 ← market_table(), signals(), coverage_mini() etc.
    └── routes/
        ├── overview.py             ← GET / — renders full terminal shell
        ├── workspaces/
        │   ├── trading.py          ← GET /workspaces/trading → pane HTML only
        │   ├── analysis.py
        │   ├── charts.py
        │   ├── news.py
        │   ├── data.py
        │   ├── journal.py
        │   └── settings.py
        └── partials/
            ├── market.py           ← GET /partials/market-table
            ├── signals.py          ← GET /partials/signals
            ├── coverage.py         ← GET /partials/coverage-mini
            └── news.py             ← GET /partials/news-mini
```

The key architectural rule: only `overview.py` calls `render_terminal()`. Every other workspace route returns a bare HTML fragment — just the panes, no shell. HTMX swaps that fragment into the already-rendered `.fks-page` div when you click the tab. This means the persistent strip never re-renders, never flickers, and the clock never resets.

Let me diagram the integration architecture first, then build it.Now the interactive monitoring workspace — click "Add panel", change metric types, see how Grafana embeds work alongside native PromQL charts.Now the full implementation. Five files that wire everything together cleanly.

---

### `src/ruby/src/lib/services/data/api/monitoring.py` — the Prometheus/Alertmanager proxy

This is the most important piece. The browser never talks to Prometheus or Alertmanager directly — everything goes through this proxy, which adds Redis caching, enrichment, and auth.

```python
"""
Monitoring proxy — sits between the terminal UI and the
Prometheus/Alertmanager/Grafana stack.

Why proxy instead of direct browser access:
  - Avoids CORS entirely (same origin as the data service)
  - Adds a 15s Redis cache so 20 panel refreshes don't hammer Prometheus
  - Enriches alerts with FKS-specific context (which symbol, which worker)
  - Lets us gate access behind the same API key as everything else
  - Grafana panel URLs include the session token — we generate those server-side

Redis cache keys:
  fks:prom:cache:{sha256(query+time_args)}  → JSON, TTL 15s
  fks:panels:layout                          → JSON list of panel configs
  fks:panels:slot:{n}                        → JSON single panel config
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["monitoring"])

# Internal service URLs (container-to-container, not going through nginx)
PROMETHEUS_URL   = os.getenv("PROMETHEUS_URL",   "http://prometheus:9090")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")
GRAFANA_URL      = os.getenv("GRAFANA_URL",       "http://grafana:3000")
CACHE_TTL        = int(os.getenv("METRICS_CACHE_TTL", "15"))   # seconds
PANEL_TTL        = int(os.getenv("PANEL_CACHE_TTL",   "300"))  # 5 min for panel layout


# ── Dependencies ──────────────────────────────────────────────────────────

def get_redis(request: Request):
    return request.app.state.redis


# ── Prometheus proxy ──────────────────────────────────────────────────────

@router.get("/query")
async def prometheus_query(
    q:    str = Query(..., description="PromQL expression"),
    time: str | None = None,
    redis=Depends(get_redis),
):
    """
    Instant PromQL query with Redis cache.
    Equivalent to Prometheus /api/v1/query.

    Usage from JS:
        const r = await fetch('/api/metrics/query?q=process_cpu_seconds_total');
        const { data } = await r.json();
    """
    cache_key = _cache_key("instant", q, time or "now")
    cached    = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    params: dict = {"query": q}
    if time:
        params["time"] = time

    result = await _prom_get("/api/v1/query", params)
    await redis.setex(cache_key, CACHE_TTL, json.dumps(result))
    return JSONResponse(result)


@router.get("/query_range")
async def prometheus_query_range(
    q:     str = Query(..., description="PromQL expression"),
    start: str | None = None,
    end:   str | None = None,
    step:  str = "60s",
    redis=Depends(get_redis),
):
    """
    Range PromQL query with Redis cache.
    Defaults: last 1 hour, 60s step.

    Usage from JS for a sparkline:
        const r = await fetch(
          '/api/metrics/query_range?q=rate(redis_commands_total[5m])&step=60s'
        );
        const { data } = await r.json();
        // data.result[0].values = [[timestamp, value], ...]
    """
    now       = datetime.now(timezone.utc).timestamp()
    end_ts    = end   or str(now)
    start_ts  = start or str(now - 3600)
    cache_key = _cache_key("range", q, start_ts, end_ts, step)

    cached = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    result = await _prom_get("/api/v1/query_range", {
        "query": q, "start": start_ts, "end": end_ts, "step": step,
    })
    await redis.setex(cache_key, CACHE_TTL, json.dumps(result))
    return JSONResponse(result)


@router.get("/targets")
async def prometheus_targets(redis=Depends(get_redis)):
    """
    Prometheus scrape target status.
    Returns all targets with their health, last scrape, duration.
    """
    cache_key = "fks:prom:cache:targets"
    cached    = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    result = await _prom_get("/api/v1/targets")
    # Flatten and enrich for the terminal
    enriched = _enrich_targets(result.get("data", {}).get("activeTargets", []))
    out      = {"targets": enriched, "total": len(enriched)}

    await redis.setex(cache_key, CACHE_TTL, json.dumps(out))
    return JSONResponse(out)


@router.get("/rules")
async def prometheus_rules(redis=Depends(get_redis)):
    """Alert rules from Prometheus — grouped by rule group."""
    cache_key = "fks:prom:cache:rules"
    cached    = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    result = await _prom_get("/api/v1/rules")
    await redis.setex(cache_key, 60, json.dumps(result))   # 60s for rules
    return JSONResponse(result)


@router.get("/series")
async def prometheus_series(
    match: str = Query(..., description="Series selector e.g. {job='fks-factory'}"),
    redis=Depends(get_redis),
):
    """Discover available metric series matching a selector."""
    cache_key = _cache_key("series", match)
    cached    = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    result = await _prom_get("/api/v1/series", {"match[]": match})
    await redis.setex(cache_key, 60, json.dumps(result))
    return JSONResponse(result)


@router.get("/label_values")
async def prometheus_label_values(
    label: str = Query(..., description="Label name e.g. __name__"),
    match: str | None = None,
):
    """Autocomplete for the PromQL query builder."""
    params: dict = {}
    if match:
        params["match[]"] = match
    return JSONResponse(await _prom_get(f"/api/v1/label/{label}/values", params))


# ── Alertmanager proxy ────────────────────────────────────────────────────

@router.get("/alerts")
async def alertmanager_alerts(
    active:   bool = True,
    silenced: bool = False,
    inhibited: bool = False,
    redis=Depends(get_redis),
):
    """
    Active alerts from Alertmanager, enriched with FKS context.

    Enrichment adds:
      - fks_context: which FKS component this alert belongs to
      - severity_rank: numeric rank for sorting (0=critical, 1=warning, 2=info)
      - age_seconds: how long this alert has been firing
    """
    cache_key = f"fks:prom:cache:alerts:{active}:{silenced}:{inhibited}"
    cached    = await redis.get(cache_key)
    if cached:
        return JSONResponse(json.loads(cached))

    params = {
        "active":    str(active).lower(),
        "silenced":  str(silenced).lower(),
        "inhibited": str(inhibited).lower(),
    }
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{ALERTMANAGER_URL}/api/v2/alerts", params=params)
            alerts = r.json() if r.status_code == 200 else []
        except Exception as e:
            log.warning("Alertmanager unreachable: %s", e)
            alerts = []

    enriched = [_enrich_alert(a) for a in alerts]
    enriched.sort(key=lambda a: a.get("severity_rank", 99))
    out = {"alerts": enriched, "count": len(enriched), "firing": sum(1 for a in enriched if a.get("state") == "firing")}

    await redis.setex(cache_key, CACHE_TTL, json.dumps(out))
    return JSONResponse(out)


@router.post("/alerts/{fingerprint}/silence")
async def silence_alert(fingerprint: str, duration_hours: int = 4, redis=Depends(get_redis)):
    """Create a silence in Alertmanager for a specific alert."""
    now = datetime.now(timezone.utc)
    end = now.replace(hour=now.hour + duration_hours)  # simplified
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(
                f"{ALERTMANAGER_URL}/api/v2/silences",
                json={
                    "matchers": [{"name": "fingerprint", "value": fingerprint, "isRegex": False}],
                    "startsAt":  now.isoformat(),
                    "endsAt":    end.isoformat(),
                    "createdBy": "fks-terminal",
                    "comment":   f"Silenced via FKS terminal for {duration_hours}h",
                }
            )
            return JSONResponse({"status": "silenced", "id": r.json().get("silenceID")})
        except Exception as e:
            raise HTTPException(503, f"Alertmanager error: {e}")


# ── Panel slot system ─────────────────────────────────────────────────────
#
# Panel layout is persisted in Redis so it survives page reloads and
# service restarts. The terminal reads the layout on load and renders
# each panel from its config.

DEFAULT_PANELS = [
    {
        "id":    "prom-stats",
        "type":  "stat-row",
        "title": "System overview",
        "queries": [
            {"label": "CPU",          "q": "rate(process_cpu_seconds_total{job='data-service'}[1m])*100", "unit": "%",  "warn": 70, "crit": 90},
            {"label": "Memory",       "q": "process_resident_memory_bytes{job='data-service'}/1024/1024",  "unit": "MB", "warn": 2048, "crit": 3500},
            {"label": "Redis ops/s",  "q": "instantaneous_ops_per_sec",                                   "unit": "",   "warn": None, "crit": None},
            {"label": "PG conns",     "q": "pg_stat_activity_count{datname='ruby_db'}",                   "unit": "",   "warn": 80, "crit": 95},
        ],
    },
    {
        "id":    "factory-gaps",
        "type":  "sparkline",
        "title": "Factory gap count",
        "query": "sum(fks_factory_gap_count)",
        "step":  "60s",
        "color": "var(--red)",
    },
    {
        "id":    "fill-lag",
        "type":  "sparkline",
        "title": "Backfill fill lag",
        "query": "max(fks_factory_fill_lag_seconds)",
        "step":  "60s",
        "color": "var(--amber)",
    },
    {
        "id":    "grafana-janus",
        "type":  "grafana",
        "title": "Janus · signals quality",
        "dashboard_uid": "fks-janus",
        "panel_id": 4,
        "theme": "dark",
    },
    {
        "id":    "alert-feed",
        "type":  "alert-feed",
        "title": "Active alerts",
    },
    {
        "id":    "targets",
        "type":  "targets",
        "title": "Scrape targets",
    },
]


@router.get("/panels/layout")
async def get_panel_layout(redis=Depends(get_redis)):
    """Returns the user's current panel layout."""
    raw = await redis.get("fks:panels:layout")
    if raw:
        return JSONResponse(json.loads(raw))
    # First run — seed with defaults
    await redis.setex("fks:panels:layout", PANEL_TTL, json.dumps(DEFAULT_PANELS))
    return JSONResponse(DEFAULT_PANELS)


@router.post("/panels/layout")
async def save_panel_layout(request: Request, redis=Depends(get_redis)):
    """Save a new panel layout (full replace)."""
    panels = await request.json()
    await redis.setex("fks:panels:layout", PANEL_TTL, json.dumps(panels))
    return JSONResponse({"status": "saved", "count": len(panels)})


@router.post("/panels/add")
async def add_panel(request: Request, redis=Depends(get_redis)):
    """Add a single panel to the current layout."""
    panel  = await request.json()
    raw    = await redis.get("fks:panels:layout")
    panels = json.loads(raw) if raw else list(DEFAULT_PANELS)
    panels.append(panel)
    await redis.setex("fks:panels:layout", PANEL_TTL, json.dumps(panels))
    return JSONResponse({"status": "added", "id": panel.get("id")})


@router.delete("/panels/{panel_id}")
async def remove_panel(panel_id: str, redis=Depends(get_redis)):
    """Remove a panel from the layout by id."""
    raw    = await redis.get("fks:panels:layout")
    panels = json.loads(raw) if raw else []
    panels = [p for p in panels if p.get("id") != panel_id]
    await redis.setex("fks:panels:layout", PANEL_TTL, json.dumps(panels))
    return JSONResponse({"status": "removed"})


# ── Grafana panel URL helper ──────────────────────────────────────────────

@router.get("/grafana/panel-url")
async def grafana_panel_url(
    dashboard_uid: str,
    panel_id:      int,
    theme:         str  = "dark",
    time_from:     str  = "now-1h",
    time_to:       str  = "now",
    refresh:       str  = "30s",
):
    """
    Returns the embed URL for a Grafana panel iframe.

    Grafana must be configured with:
      GF_AUTH_ANONYMOUS_ENABLED=true
      GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      GF_SECURITY_ALLOW_EMBEDDING=true

    Or use Grafana service accounts + the Authorization header.
    The URL is returned to the client who embeds it as iframe src.
    """
    url = (
        f"{GRAFANA_URL}/d-solo/{dashboard_uid}/"
        f"?orgId=1"
        f"&panelId={panel_id}"
        f"&theme={theme}"
        f"&from={time_from}"
        f"&to={time_to}"
        f"&refresh={refresh}"
        f"&kiosk"
    )
    # Rewrite to the public-facing nginx path (not internal grafana port)
    public_url = url.replace(GRAFANA_URL, "/grafana")
    return JSONResponse({"url": public_url, "internal_url": url})


# ── HTMX partials ─────────────────────────────────────────────────────────

@router.get("/partials/stat-row", response_class=HTMLResponse)
async def partial_stat_row(redis=Depends(get_redis)):
    """
    Renders the 4-stat overview row as HTML.
    Polled every 15s via hx-trigger on the monitoring workspace.
    """
    queries = [
        ("CPU",         "rate(process_cpu_seconds_total{job='data-service'}[1m])*100", "%",  70,   90),
        ("Memory MB",   "process_resident_memory_bytes{job='data-service'}/1024/1024",  "MB", 2048, 3584),
        ("Redis ops/s", "instantaneous_ops_per_sec",                                   "",   None, None),
        ("PG conns",    "pg_stat_activity_count",                                       "",   80,   95),
    ]
    cells = []
    for label, q, unit, warn, crit in queries:
        val = await _query_scalar(q, redis)
        if val is None:
            display, cls = "—", "dim"
        else:
            display = f"{val:.1f}{unit}" if isinstance(val, float) else f"{val}{unit}"
            cls = "neg" if crit and val >= crit else "warn" if warn and val >= warn else "pos"
        cells.append(f"""
        <div class="stat-box">
          <div class="stat-lbl">{label}</div>
          <div class="stat-num {cls}">{display}</div>
          <div class="stat-sub">{q[:40]}…</div>
        </div>""")

    return HTMLResponse(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">'
        + "".join(cells) +
        "</div>"
    )


@router.get("/partials/alert-feed", response_class=HTMLResponse)
async def partial_alert_feed(redis=Depends(get_redis)):
    """
    Renders the Alertmanager alert list as HTML.
    Used by hx-trigger="every 30s" in the monitoring workspace.
    """
    cache_key = "fks:prom:cache:alerts:True:False:False"
    cached    = await redis.get(cache_key)
    if cached:
        data   = json.loads(cached)
        alerts = data.get("alerts", [])
    else:
        alerts = []

    if not alerts:
        return HTMLResponse(
            '<div class="dim" style="text-align:center;padding:12px;font-size:10px">'
            '● All clear — no active alerts</div>'
        )

    sev_cls = {"critical": "sev-crit", "warning": "sev-warn", "info": "sev-info"}
    rows    = []
    for a in alerts[:8]:   # cap at 8 in the sidebar
        sev  = a.get("severity", "info")
        cls  = sev_cls.get(sev, "sev-info")
        name = a.get("name", "Unknown")
        desc = a.get("description", a.get("summary", ""))
        age  = _format_age(a.get("age_seconds", 0))
        rows.append(f"""
        <div class="alert-item">
          <div class="asev {cls}">{sev[:4].upper()}</div>
          <div class="a-body">
            <div class="a-name">{name}</div>
            <div class="a-desc">{desc[:120]}</div>
            <div class="a-meta">{a.get("fks_context","")} · {age}</div>
          </div>
        </div>""")

    return HTMLResponse("".join(rows))


@router.get("/partials/targets-table", response_class=HTMLResponse)
async def partial_targets_table(redis=Depends(get_redis)):
    """Renders the Prometheus scrape targets as an HTML table."""
    cached = await redis.get("fks:prom:cache:targets")
    targets = json.loads(cached).get("targets", []) if cached else []

    rows = []
    for t in targets:
        state = t.get("health", "unknown")
        cls   = "pos" if state == "up" else "neg"
        rows.append(
            f"<tr>"
            f"<td>{t.get('instance','')}</td>"
            f"<td>{t.get('job','')}</td>"
            f"<td class='{cls}'>● {state.upper()}</td>"
            f"<td class='dim'>{t.get('last_scrape','')}</td>"
            f"<td class='dim'>{t.get('scrape_duration','')}</td>"
            f"</tr>"
        )

    return HTMLResponse(
        "<table class='dtable'>"
        "<thead><tr><th>Target</th><th>Job</th><th>State</th><th>Last scrape</th><th>Duration</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


@router.get("/partials/sparkline/{panel_id}", response_class=HTMLResponse)
async def partial_sparkline(
    panel_id: str,
    q:        str,
    title:    str = "",
    step:     str = "60s",
    color:    str = "var(--cyan)",
    redis=Depends(get_redis),
):
    """
    Renders a single sparkline panel as HTML + inline SVG.
    Called by hx-trigger="every 15s" on each dynamic panel.

    The SVG is generated server-side from Prometheus data.
    Chart.js is used for more complex charts in the workspace JS.
    """
    now     = datetime.now(timezone.utc).timestamp()
    start   = str(now - 3600)
    result  = await _prom_get("/api/v1/query_range", {
        "query": q, "start": start, "end": str(now), "step": step,
    })

    values = []
    try:
        values = result["data"]["result"][0]["values"]
    except (KeyError, IndexError):
        pass

    if not values:
        return HTMLResponse(f'<div class="dim" style="text-align:center;font-size:10px;padding:16px">No data for: {q}</div>')

    # Normalize to SVG coordinates
    floats = [float(v[1]) for v in values if v[1] != "NaN"]
    if not floats:
        return HTMLResponse('<div class="dim" style="text-align:center;font-size:10px;padding:16px">No valid data points</div>')

    mn, mx = min(floats), max(floats)
    rng    = mx - mn or 1
    W, H   = 300, 60

    pts = []
    for i, val in enumerate(floats):
        x = i / max(len(floats)-1, 1) * W
        y = H - ((val - mn) / rng * (H - 8)) - 4
        pts.append(f"{x:.1f},{y:.1f}")

    latest = floats[-1]
    pts_str = " ".join(pts)
    poly_close = f"{pts[-1].split(',')[0]},{H} 0,{H}"

    return HTMLResponse(f"""
    <div class="chart-wrap" style="height:80px;position:relative;overflow:hidden">
      <div class="chart-lbl" style="position:absolute;top:5px;left:8px;font-size:9px;color:var(--t3)">{title or q[:40]}</div>
      <div style="position:absolute;top:5px;right:8px;font-size:10px;font-weight:700;font-variant-numeric:tabular-nums;color:{color}">{latest:.2f}</div>
      <svg width="100%" height="80" viewBox="0 0 {W} {H}" preserveAspectRatio="none">
        <polyline points="{pts_str}" fill="none" stroke="{color}" stroke-width="1.5" opacity=".9"/>
        <polygon points="{pts_str} {poly_close}" fill="{color}" opacity=".07"/>
      </svg>
    </div>""")


# ── Internal helpers ──────────────────────────────────────────────────────

async def _prom_get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            r = await client.get(f"{PROMETHEUS_URL}{path}", params=params or {})
            if r.status_code != 200:
                log.warning("Prometheus %s → %d", path, r.status_code)
                return {"status": "error", "data": {}}
            return r.json()
        except Exception as e:
            log.warning("Prometheus unreachable: %s", e)
            return {"status": "error", "error": str(e), "data": {}}


async def _query_scalar(query: str, redis) -> float | None:
    """Run an instant query and return the first scalar result."""
    cache_key = _cache_key("scalar", query)
    cached    = await redis.get(cache_key)
    if cached:
        try:
            return float(json.loads(cached))
        except Exception:
            return None

    result = await _prom_get("/api/v1/query", {"query": query})
    try:
        val = float(result["data"]["result"][0]["value"][1])
        await redis.setex(cache_key, CACHE_TTL, json.dumps(val))
        return val
    except (KeyError, IndexError, ValueError):
        return None


def _cache_key(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return "fks:prom:cache:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _enrich_targets(targets: list[dict]) -> list[dict]:
    """Flatten Prometheus target objects into a simpler format."""
    out = []
    for t in targets:
        labels = t.get("labels", {})
        last   = t.get("lastScrape", "")
        dur_s  = t.get("lastScrapeDuration", 0)
        out.append({
            "instance":        labels.get("instance", t.get("scrapeUrl", "")),
            "job":             labels.get("job", ""),
            "health":          t.get("health", "unknown"),
            "last_scrape":     _format_scrape_age(last),
            "scrape_duration": f"{dur_s*1000:.0f}ms" if dur_s else "—",
            "labels":          {k: v for k, v in labels.items() if k not in ("instance","job")},
        })
    return out


def _enrich_alert(alert: dict) -> dict:
    """Add FKS-specific context to an Alertmanager alert object."""
    labels  = alert.get("labels", {})
    annots  = alert.get("annotations", {})
    name    = labels.get("alertname", "Unknown")
    sev     = labels.get("severity", "info")
    sev_rank = {"critical": 0, "warning": 1, "info": 2}.get(sev, 3)
    starts  = alert.get("startsAt", "")

    # Compute age
    age_secs = 0
    try:
        start_dt  = datetime.fromisoformat(starts.replace("Z", "+00:00"))
        age_secs  = (datetime.now(timezone.utc) - start_dt).seconds
    except Exception:
        pass

    # FKS context: figure out which component owns this alert
    fks_context = ""
    if "factory" in name.lower() or "coverage" in name.lower() or "fill" in name.lower():
        fks_context = "DataFactory"
    elif "redis" in name.lower():
        fks_context = "Redis"
    elif "postgres" in name.lower() or "pg_" in name.lower():
        fks_context = "Postgres"
    elif "janus" in name.lower():
        fks_context = "Janus"
    elif "questdb" in name.lower():
        fks_context = "QuestDB"

    return {
        "name":          name,
        "severity":      sev,
        "severity_rank": sev_rank,
        "state":         alert.get("status", {}).get("state", "firing"),
        "summary":       annots.get("summary", ""),
        "description":   annots.get("description", annots.get("summary", "")),
        "fingerprint":   alert.get("fingerprint", ""),
        "fks_context":   fks_context,
        "age_seconds":   age_secs,
        "starts_at":     starts,
        "labels":        labels,
    }


def _format_age(seconds: int) -> str:
    if seconds < 60:   return f"{seconds}s"
    if seconds < 3600: return f"{seconds//60}m ago"
    return f"{seconds//3600}h ago"


def _format_scrape_age(iso: str) -> str:
    try:
        dt  = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).seconds
        return _format_age(age)
    except Exception:
        return "—"
```

---

### `src/ruby/static/js/fks-monitoring.js`

Loaded only on the monitoring workspace. Handles dynamic panel rendering, Chart.js integration, and the panel picker.

```javascript
/* fks-monitoring.js — monitoring workspace runtime
   Loaded only when the Monitoring tab is active.
   Depends on: fks-terminal.js (for FKS.API, FKS.Toast), Chart.js */

'use strict';

// ── Panel registry — what types the picker can add ─────────────────────
const PANEL_TYPES = [
  { type: 'sparkline',  icon: '📈', name: 'Sparkline',      desc: 'Time-series from any PromQL query' },
  { type: 'gauge',      icon: '⊙',  name: 'Gauge',          desc: 'Arc gauge for utilisation metrics' },
  { type: 'stat',       icon: '🔢', name: 'Stat',           desc: 'Single instant-query value' },
  { type: 'grafana',    icon: '⬡',  name: 'Grafana panel',  desc: 'Embed a Grafana panel by dashboard UID' },
  { type: 'alert-feed', icon: '⚠',  name: 'Alert feed',     desc: 'Live Alertmanager alerts' },
  { type: 'table',      icon: '⊞',  name: 'Targets table',  desc: 'Prometheus scrape targets' },
];

// Preset PromQL queries for the query builder chips
const PRESET_QUERIES = [
  { label: 'CPU %',            q: "rate(process_cpu_seconds_total{job='data-service'}[1m])*100" },
  { label: 'Memory MB',        q: "process_resident_memory_bytes{job='data-service'}/1024/1024" },
  { label: 'Redis ops/s',      q: "instantaneous_ops_per_sec" },
  { label: 'PG connections',   q: "pg_stat_activity_count" },
  { label: 'Gap count',        q: "sum(fks_factory_gap_count)" },
  { label: 'Fill lag (s)',      q: "max(fks_factory_fill_lag_seconds)" },
  { label: 'Cache age (s)',     q: "max(fks_factory_redis_cache_age_seconds)" },
  { label: 'Chunk failures',   q: "sum(fks_factory_chunk_failures_total)" },
  { label: 'Divergence',       q: "sum(fks_factory_reconcile_divergence)" },
  { label: 'Signal latency ms',q: "fks_signal_latency_ms" },
  { label: 'Janus signals/min',q: "rate(janus_signals_total[1m])*60" },
  { label: 'QuestDB rows/s',   q: "rate(questdb_committed_rows_total[1m])" },
];

// Active Chart.js instances — keyed by canvas id
const _charts = {};

// ── Initialise monitoring workspace ────────────────────────────────────
const Monitoring = {
  async init() {
    await this.loadLayout();
    this.startRefreshLoop();
    this.wireQueryBuilder();
  },

  // Load panel layout from server and render all panels
  async loadLayout() {
    const container = document.getElementById('dyn-panels');
    if (!container) return;
    try {
      const panels = await FKS.API.get('/api/metrics/panels/layout');
      container.innerHTML = '';
      panels.forEach(p => this.renderPanel(p, container));
    } catch (e) {
      FKS.Toast.error('Failed to load panel layout');
    }
  },

  // Render a single panel into the container
  renderPanel(config, container) {
    const id  = config.id || `panel-${Date.now()}`;
    const div = document.createElement('div');
    div.className = 'panel';
    div.id        = `panel-wrap-${id}`;
    div.dataset.panelId = id;

    div.innerHTML = `
      <div class="ph">
        ${config.title || 'Panel'}
        <div class="ph-actions">
          ${this._panelActions(config)}
          <button class="ph-btn del" onclick="Monitoring.removePanel('${id}')">✕</button>
        </div>
      </div>
      <div class="pb" id="panel-body-${id}">
        <div class="dim" style="font-size:9px;padding:8px 0;text-align:center">Loading…</div>
      </div>`;

    container.appendChild(div);
    this.loadPanelData(config);
  },

  // Fetch data and populate panel body
  async loadPanelData(config) {
    const body = document.getElementById(`panel-body-${config.id}`);
    if (!body) return;

    try {
      switch (config.type) {
        case 'sparkline':
          await this._renderSparkline(body, config);
          break;
        case 'gauge':
          await this._renderGauges(body, config);
          break;
        case 'stat':
          await this._renderStat(body, config);
          break;
        case 'grafana':
          this._renderGrafanaEmbed(body, config);
          break;
        case 'alert-feed':
          await this._renderAlertFeed(body);
          break;
        case 'stat-row':
          // Use HTMX partial — let the server render it
          body.setAttribute('hx-get', '/api/metrics/partials/stat-row');
          body.setAttribute('hx-trigger', 'load, every 15s');
          htmx.process(body);
          break;
      }
    } catch (e) {
      body.innerHTML = `<div class="neg" style="font-size:9px;padding:8px">${e.message}</div>`;
    }
  },

  // ── Panel renderers ──────────────────────────────────────────────────

  async _renderSparkline(body, config) {
    const step = config.step || '60s';
    const now  = Date.now() / 1000;
    const from = now - 3600;

    const data = await FKS.API.get(
      `/api/metrics/query_range?q=${encodeURIComponent(config.query)}&start=${from}&end=${now}&step=${step}`
    );

    const values = data?.data?.result?.[0]?.values || [];
    if (!values.length) {
      body.innerHTML = '<div class="dim" style="text-align:center;padding:16px;font-size:9px">No data</div>';
      return;
    }

    const canvasId = `canvas-${config.id}`;
    body.innerHTML = `<canvas id="${canvasId}" height="70"></canvas>`;
    const canvas   = document.getElementById(canvasId);

    if (_charts[canvasId]) _charts[canvasId].destroy();

    const labels = values.map(v => new Date(v[0] * 1000).toLocaleTimeString());
    const points = values.map(v => parseFloat(v[1]));
    const color  = config.color || 'rgb(0,212,232)';

    _charts[canvasId] = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: points,
          borderColor: color,
          backgroundColor: color.replace('rgb', 'rgba').replace(')', ',.07)'),
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          tension: 0.3,
        }]
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
        scales: {
          x: { display: false },
          y: {
            display: true,
            grid: { color: 'rgba(26,26,46,.8)', lineWidth: 0.5 },
            ticks: { color: '#454870', font: { size: 8, family: 'SF Mono, monospace' }, maxTicksLimit: 4 },
          }
        }
      }
    });

    // Latest value overlay
    const latest = points[points.length - 1];
    const valDiv = document.createElement('div');
    valDiv.style.cssText = 'position:absolute;top:5px;right:8px;font-size:10px;font-weight:700;font-variant-numeric:tabular-nums';
    valDiv.style.color   = color;
    valDiv.textContent   = latest?.toFixed(2) ?? '—';
    body.style.position  = 'relative';
    body.appendChild(valDiv);
  },

  async _renderGauges(body, config) {
    const queries = config.queries || [];
    const results = await Promise.all(queries.map(async q => {
      const data = await FKS.API.get(`/api/metrics/query?q=${encodeURIComponent(q.query || q.q)}`);
      const val  = parseFloat(data?.data?.result?.[0]?.value?.[1] ?? 0);
      return { ...q, val };
    }));

    const gauges = results.map(({ label, val, max = 100, unit = '%', warn, crit }) => {
      const pct = Math.min(val / max * 100, 100);
      const arc = pct * 0.88;    // 0.88 = 80deg arc in dash units
      const clr = crit && val >= crit ? 'var(--red)' : warn && val >= warn ? 'var(--amber)' : 'var(--green)';
      return `
      <div style="display:flex;flex-direction:column;align-items:center;gap:3px">
        <svg width="60" height="38" viewBox="0 0 64 40">
          <path d="M8 36 A28 28 0 0 1 56 36" fill="none" stroke="var(--bg3)" stroke-width="6" stroke-linecap="round"/>
          <path d="M8 36 A28 28 0 0 1 56 36" fill="none" stroke="${clr}" stroke-width="6"
                stroke-linecap="round" stroke-dasharray="${arc} ${88-arc}" opacity=".9"/>
          <text x="32" y="37" text-anchor="middle" font-size="8" font-weight="700"
                fill="${clr}" font-family="SF Mono,monospace">${val.toFixed(1)}${unit}</text>
        </svg>
        <div style="font-size:9px;color:var(--t3)">${label}</div>
      </div>`;
    });

    body.innerHTML = `<div style="display:grid;grid-template-columns:repeat(${Math.min(gauges.length,4)},1fr);gap:8px">${gauges.join('')}</div>`;
  },

  async _renderStat(body, config) {
    const data = await FKS.API.get(`/api/metrics/query?q=${encodeURIComponent(config.query)}`);
    const val  = parseFloat(data?.data?.result?.[0]?.value?.[1] ?? 0);
    const unit = config.unit || '';
    const warn = config.warn;
    const crit = config.crit;
    const cls  = crit && val >= crit ? 'neg' : warn && val >= warn ? 'warn' : 'pos';
    body.innerHTML = `
      <div class="stat-box" style="text-align:center;padding:12px">
        <div class="stat-lbl">${config.title || config.query}</div>
        <div class="stat-num ${cls}" style="font-size:28px">${val.toFixed(2)}${unit}</div>
        <div class="stat-sub">${new Date().toLocaleTimeString()}</div>
      </div>`;
  },

  async _renderGrafanaEmbed(body, config) {
    const data = await FKS.API.get(
      `/api/metrics/grafana/panel-url?dashboard_uid=${config.dashboard_uid}&panel_id=${config.panel_id}&theme=${config.theme||'dark'}`
    );
    body.innerHTML = `
      <iframe
        src="${data.url}"
        style="width:100%;height:120px;border:none;background:var(--bg0);border-radius:3px"
        loading="lazy"
        title="${config.title}">
      </iframe>`;
  },

  async _renderAlertFeed(body) {
    body.setAttribute('hx-get', '/api/metrics/partials/alert-feed');
    body.setAttribute('hx-trigger', 'load, every 30s');
    body.setAttribute('hx-swap', 'innerHTML');
    htmx.process(body);
  },

  // ── Panel actions ─────────────────────────────────────────────────────

  _panelActions(config) {
    if (config.type === 'sparkline') {
      return `<button class="ph-btn" onclick="Monitoring.editQuery('${config.id}')">PromQL</button>`;
    }
    if (config.type === 'grafana') {
      return `<button class="ph-btn" onclick="window.open('/grafana/d/${config.dashboard_uid}','_blank')">Open →</button>`;
    }
    return '';
  },

  // ── Panel management ──────────────────────────────────────────────────

  async removePanel(id) {
    if (!confirm('Remove this panel?')) return;
    await FKS.API._req('DELETE', `/api/metrics/panels/${id}`);
    document.getElementById(`panel-wrap-${id}`)?.remove();
    FKS.Toast.success('Panel removed');
  },

  async addPanel(config) {
    // Generate a unique id
    config.id = config.type + '-' + Date.now().toString(36);
    await FKS.API.post('/api/metrics/panels/add', config);
    const container = document.getElementById('dyn-panels');
    this.renderPanel(config, container);
    FKS.Toast.success(`Added: ${config.title || config.type}`);
  },

  // Open the panel picker modal and handle selection
  openPicker() {
    const overlay = document.getElementById('panel-picker');
    if (!overlay) return this._buildPicker();
    overlay.style.display = 'flex';
  },

  _buildPicker() {
    const overlay = document.createElement('div');
    overlay.id    = 'panel-picker';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(7,7,13,.85);display:flex;align-items:center;justify-content:center;z-index:100';
    overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };

    const grid = PANEL_TYPES.map(p => `
      <div class="picker-item" onclick="Monitoring._pickPanel('${p.type}');document.getElementById('panel-picker').remove()">
        <div style="font-size:20px;margin-bottom:4px">${p.icon}</div>
        <div style="font-size:10px;font-weight:700;color:var(--t1)">${p.name}</div>
        <div style="font-size:9px;color:var(--t3);margin-top:2px;line-height:1.3">${p.desc}</div>
      </div>`).join('');

    overlay.innerHTML = `
      <div style="background:var(--bg1);border:1px solid var(--b2);border-radius:5px;width:500px;max-height:420px;overflow:hidden;display:flex;flex-direction:column">
        <div style="padding:10px 14px;border-bottom:1px solid var(--b2);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:space-between">
          Add monitoring panel
          <span style="cursor:pointer;color:var(--t3);font-size:16px" onclick="document.getElementById('panel-picker').remove()">✕</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;overflow:auto">${grid}</div>
      </div>`;
    document.body.appendChild(overlay);
  },

  // After picking a type, prompt for details
  _pickPanel(type) {
    if (type === 'sparkline') {
      const q = prompt('PromQL query:', 'rate(redis_commands_total[5m])');
      if (!q) return;
      const title = prompt('Panel title:', q.slice(0, 30));
      this.addPanel({ type, query: q, title: title || q.slice(0,30), step: '60s', color: 'var(--cyan)' });
    } else if (type === 'grafana') {
      const uid     = prompt('Grafana dashboard UID:', 'fks-janus');
      const panelId = parseInt(prompt('Panel ID:', '4'));
      const title   = prompt('Title:', 'Grafana panel');
      if (uid && panelId) this.addPanel({ type, dashboard_uid: uid, panel_id: panelId, title, theme: 'dark' });
    } else if (type === 'stat') {
      const q     = prompt('PromQL query:', 'sum(fks_factory_gap_count)');
      const title = prompt('Title:', 'Metric');
      const unit  = prompt('Unit (leave empty for none):', '');
      if (q) this.addPanel({ type, query: q, title, unit });
    } else if (type === 'gauge') {
      const q     = prompt('PromQL query:', 'process_resident_memory_bytes/1024/1024/4096*100');
      const title = prompt('Title:', 'Gauge');
      if (q) this.addPanel({ type, queries: [{ label: title, q, max: 100, unit: '%' }], title });
    } else {
      this.addPanel({ type, title: PANEL_TYPES.find(p => p.type === type)?.name || type });
    }
  },

  editQuery(panelId) {
    const q = prompt('PromQL query:');
    if (!q) return;
    // Update server-side layout and re-render
    FKS.API.get('/api/metrics/panels/layout').then(panels => {
      const panel = panels.find(p => p.id === panelId);
      if (panel) {
        panel.query = q;
        FKS.API.post('/api/metrics/panels/layout', panels).then(() => {
          const body = document.getElementById(`panel-body-${panelId}`);
          if (body) this.loadPanelData(panel);
        });
      }
    });
  },

  // ── Query builder for the custom PromQL panel ─────────────────────────
  wireQueryBuilder() {
    const input = document.getElementById('pql-query-input');
    const chips = document.getElementById('pql-chips');
    if (!chips) return;

    // Render preset chips
    chips.innerHTML = PRESET_QUERIES.map(p =>
      `<div class="mchip" data-query="${p.q}" onclick="Monitoring.setQuery(this,'${p.q.replace(/'/g,"\\'")}')">
        ${p.label}
      </div>`
    ).join('');
  },

  setQuery(el, q) {
    document.querySelectorAll('.mchip').forEach(c => c.classList.remove('active'));
    el?.classList.add('active');
    const input = document.getElementById('pql-query-input');
    if (input) input.value = q;
    this.runQuery(q);
  },

  async runQuery(q) {
    q = q || document.getElementById('pql-query-input')?.value;
    if (!q) return;

    const resultDiv = document.getElementById('pql-result-area');
    if (!resultDiv) return;
    resultDiv.innerHTML = '<div class="dim" style="font-size:9px;padding:8px">Running…</div>';

    try {
      const data = await FKS.API.get(
        `/api/metrics/query_range?q=${encodeURIComponent(q)}&step=60s`
      );
      const results = data?.data?.result || [];

      if (!results.length) {
        resultDiv.innerHTML = '<div class="dim" style="font-size:9px;padding:8px;text-align:center">No data returned</div>';
        return;
      }

      // Render as sparkline using Chart.js
      const canvasId = 'pql-canvas';
      resultDiv.innerHTML = `<canvas id="${canvasId}" height="80"></canvas>`;
      const canvas  = document.getElementById(canvasId);
      if (_charts[canvasId]) _charts[canvasId].destroy();

      const datasets = results.map((series, i) => {
        const colors = ['#00d4e8','#16c784','#9b8cff','#f0a500','#ea3943'];
        const color  = colors[i % colors.length];
        const name   = Object.entries(series.metric).map(([k,v]) => `${k}="${v}"`).join(', ') || q.slice(0,20);
        return {
          label:           name,
          data:            series.values.map(v => ({ x: v[0]*1000, y: parseFloat(v[1]) })),
          borderColor:     color,
          backgroundColor: color + '12',
          borderWidth: 1.5, pointRadius: 0, fill: true, tension: 0.3,
        };
      });

      _charts[canvasId] = new Chart(canvas, {
        type: 'line',
        data: { datasets },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: datasets.length > 1,
              labels: { color: '#8890b8', font: { size: 8, family: 'SF Mono,monospace' } },
            },
          },
          scales: {
            x: { type: 'time', display: false },
            y: {
              grid: { color: 'rgba(26,26,46,.8)', lineWidth: 0.5 },
              ticks: { color: '#454870', font: { size: 8, family: 'SF Mono,monospace' }, maxTicksLimit: 4 },
            }
          }
        }
      });
    } catch (e) {
      resultDiv.innerHTML = `<div class="neg" style="font-size:9px;padding:8px">${e.message}</div>`;
    }
  },

  // ── Auto-refresh loop ────────────────────────────────────────────────
  startRefreshLoop() {
    setInterval(() => {
      // HTMX-managed panels refresh themselves — only refresh Chart.js panels here
      document.querySelectorAll('[data-panel-id]').forEach(wrap => {
        const id     = wrap.dataset.panelId;
        const canvas = wrap.querySelector('canvas');
        if (canvas && _charts[canvas.id]) {
          // Chart exists — reload data (find config from layout)
          FKS.API.get('/api/metrics/panels/layout').then(panels => {
            const config = panels.find(p => p.id === id);
            if (config && (config.type === 'sparkline' || config.type === 'gauge')) {
              const body = document.getElementById(`panel-body-${id}`);
              if (body) this.loadPanelData(config);
            }
          });
        }
      });
    }, 15_000);
  },
};

// Boot on load
document.addEventListener('DOMContentLoaded', () => Monitoring.init());

// Expose for inline onclick handlers
window.Monitoring = Monitoring;
```

---

### Grafana configuration additions

In `docker-compose.yml`, add these environment vars to the `grafana` service so panels can be embedded in iframes:

```yaml
grafana:
  environment:
    - GF_SECURITY_ALLOW_EMBEDDING=true
    - GF_AUTH_ANONYMOUS_ENABLED=true
    - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    # Restrict anonymous to read-only — no editing from embedded panels
    - GF_USERS_DEFAULT_THEME=dark
    - GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/fks-overview.json
    # Already in your compose:
    - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:?GRAFANA_PASSWORD required}
    - GF_SERVER_ROOT_URL=http://localhost/grafana/
    - GF_SERVER_SERVE_FROM_SUB_PATH=true
```

---

### Prometheus scrape config additions

Add these jobs to `infrastructure/config/prometheus/prometheus.yml`. The factory metrics endpoint from session 1 and the `fks:panels` endpoint for panel health are the new ones:

```yaml
scrape_configs:
  # ── Existing jobs (keep these) ─────────────────────────────
  - job_name: 'data-service'
    static_configs:
      - targets: ['fks_ruby:8000']

  - job_name: 'fks-janus'
    static_configs:
      - targets: ['fks_janus:8080']

  # ── New: factory metrics ───────────────────────────────────
  - job_name: 'fks-factory'
    static_configs:
      - targets: ['fks_ruby:8000']
    metrics_path: /factory/metrics      # the endpoint from monitoring.py
    scrape_interval: 60s                # factory metrics change slowly

  # ── New: janus optimizer ──────────────────────────────────
  - job_name: 'fks-optimizer'
    static_configs:
      - targets: ['fks_janus:9092']
    scrape_interval: 30s

  # ── Existing exporters (keep these) ───────────────────────
  - job_name: 'postgres'
    static_configs:
      - targets: ['fks_postgres_exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['fks_redis_exporter:9121']

  - job_name: 'questdb'
    static_configs:
      - targets: ['fks_questdb_exporter:9191']
    metrics_path: /metrics

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

---

### Alertmanager Discord routing

Your `alertmanager.yml` currently routes to `DISCORD_WEBHOOK_GENERAL`. Add severity-based routing so critical alerts get their own channel and factory alerts don't spam:

```yaml
# infrastructure/config/alertmanager/alertmanager.yml

global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'job']
  group_wait:      30s
  group_interval:  5m
  repeat_interval: 4h
  receiver: discord-general

  routes:
    # Critical alerts — immediate, no grouping delay
    - match:
        severity: critical
      receiver: discord-critical
      group_wait: 10s
      repeat_interval: 1h

    # Factory / data pipeline alerts — lower priority, batch them
    - match_re:
        alertname: '(DataCoverage|BackfillFailed|GapDetected|ProviderDown).*'
      receiver: discord-factory
      group_wait: 2m
      group_interval: 10m
      repeat_interval: 6h

    # Silence weekends for non-critical
    - match:
        severity: warning
      mute_time_intervals:
        - weekends

receivers:
  - name: discord-general
    webhook_configs:
      - url: http://fks_alertmanager_discord_bridge:9094/webhook
        send_resolved: true

  - name: discord-critical
    webhook_configs:
      - url: http://fks_alertmanager_discord_bridge:9094/webhook
        send_resolved: true
        # Your bridge can route to a different Discord channel based on a header
        http_config:
          headers:
            X-Discord-Channel: critical

  - name: discord-factory
    webhook_configs:
      - url: http://fks_alertmanager_discord_bridge:9094/webhook
        send_resolved: true
        http_config:
          headers:
            X-Discord-Channel: factory

mute_time_intervals:
  - name: weekends
    time_intervals:
      - weekdays: ['saturday', 'sunday']
```

---

### How it all connects in the terminal

Register the new router and add the monitoring tab in `main.py`:

```python
# In your existing main.py / routes setup

from lib.services.data.api.monitoring import router as monitoring_router

app.include_router(monitoring_router)

# Also expose Chart.js from CDN via a static redirect
# so fks-monitoring.js can import it without going to unpkg from the terminal
```

In `shell.py`, add the Monitoring tab to `TABS`:

```python
TabDef("monitoring", "Monitoring", "var(--purple)"),
```

And in the monitoring workspace HTML, load `fks-monitoring.js` and `Chart.js` only for that page:

```python
# workspaces/monitoring.py

extra_scripts = """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script src="/static/js/fks-monitoring.js" defer></script>
"""
```

The key design principle across all of this: Prometheus is never hit directly by the browser. Every query goes through `/api/metrics/*`, gets cached in Redis for 15 seconds, and comes back enriched. This means 20 panels refreshing every 15 seconds = 1 actual Prometheus query per metric per 15-second window, not 20. The panel layout lives in Redis so a user's customized monitoring view survives across sessions and container restarts.
