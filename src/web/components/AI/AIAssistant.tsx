import React, { useEffect, useMemo, useRef, useState } from 'react';

import { aiHealth, aiPullModel, chat, chatStream } from '../../services/aiClient';

import type { ChatMessage } from '../../services/aiClient';

const DEFAULT_MODEL = 'gpt-oss:20b';

const bubble = 'px-3 py-2 rounded-lg border text-sm max-w-[80%] whitespace-pre-wrap';

const AIAssistant: React.FC = () => {
  const [model, setModel] = useState<string>(DEFAULT_MODEL);
  const [systemPrompt, setSystemPrompt] = useState<string>('You are a concise trading assistant.');
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<ChatMessage[]>(() => [
    { role: 'system', content: 'You are a concise trading assistant.' },
  ]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; error?: string } | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [hasToken, setHasToken] = useState<boolean>(false);
  const [stream, setStream] = useState<boolean>(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let active = true;
    aiHealth().then((h) => active && setHealth(h));
    if (typeof window !== 'undefined') {
      setHasToken(!!localStorage.getItem('fks_api_token'));
    }
    return () => { active = false; };
  }, []);

  useEffect(() => {
    // keep scroll at bottom on new messages
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [msgs]);

  const canSend = useMemo(() => input.trim().length > 0 && !busy, [input, busy]);

  async function onSend() {
    if (!canSend) return;
    const next: ChatMessage[] = [
      { role: 'system', content: systemPrompt || 'You are a concise trading assistant.' },
      ...msgs.filter((m) => m.role !== 'system'),
      { role: 'user', content: input.trim() },
    ];
    setMsgs(next);
    setInput('');
    setBusy(true);
    try {
      if (stream) {
        let acc = '';
        setMsgs([...next, { role: 'assistant', content: '' }]);
        abortRef.current?.abort();
        abortRef.current = new AbortController();
        await chatStream(next, { model, signal: abortRef.current.signal }, (t) => {
          acc += t;
          setMsgs((prev) => {
            const cp = [...prev];
            // find last assistant msg and update content
            for (let i = cp.length - 1; i >= 0; i--) {
              if (cp[i].role === 'assistant') { cp[i] = { ...cp[i], content: acc }; break; }
            }
            return cp;
          });
        });
      } else {
        const content = await chat(next, { model });
        setMsgs([...next, { role: 'assistant', content }]);
      }
    } catch (e: any) {
      setMsgs([...next, { role: 'assistant', content: `Error: ${e?.message || String(e)}` }]);
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  async function onPull() {
    setBusy(true);
    try {
      await aiPullModel(model);
      const h = await aiHealth();
      setHealth(h);
    } catch (e) {
      // ignore
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[70vh]">
      <div className="max-w-5xl mx-auto">
        <div className="mb-4 flex items-center gap-2">
          <h1 className="text-3xl font-bold text-white">AI Assistant</h1>
          <span className={`text-xs px-2 py-0.5 rounded border ${health?.ok ? 'text-green-300 border-green-500/40 bg-green-500/10' : 'text-red-300 border-red-500/40 bg-red-500/10'}`}>
            {health?.ok ? 'Ollama: OK' : 'Ollama: Unavailable'}
          </span>
        </div>

        <div className="glass-card p-4 space-y-4">
          {!hasToken && (
            <div className="px-3 py-2 rounded border border-yellow-500/40 bg-yellow-500/10 text-yellow-200 text-sm">
              No API token found. Set one in Settings to enable chat. In dev, your server may accept empty tokens.
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Model</label>
              <input value={model} onChange={(e)=> setModel(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
            </div>
            <div className="flex items-end gap-2">
              <button onClick={onPull} disabled={busy} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white disabled:opacity-50">Pull/Ensure Model</button>
              <a href="/docs" className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-white border border-gray-700">Docs</a>
              <label className="text-sm text-gray-300 flex items-center gap-2">
                <input type="checkbox" checked={stream} onChange={(e)=> setStream(e.target.checked)} className="w-4 h-4"/>
                Stream
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">System Prompt</label>
            <textarea value={systemPrompt} onChange={(e)=> setSystemPrompt(e.target.value)} rows={2} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
          </div>

          <div ref={scrollerRef} className="h-[40vh] overflow-y-auto rounded border border-gray-700 bg-black/30 p-3 space-y-2">
            {msgs.filter(m=>m.role!=='system').length === 0 && (
              <div className="text-gray-400 text-sm">Start chatting with the model. Your token and API base can be set in Settings.</div>
            )}
            {msgs.filter(m => m.role !== 'system').map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`${bubble} ${m.role === 'user' ? 'bg-blue-500/20 border-blue-500/30 text-blue-100' : 'bg-gray-800/60 border-gray-700 text-gray-100'}`}>{m.content}</div>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e)=> setInput(e.target.value)}
              onKeyDown={(e)=> { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
              placeholder="Ask anything trading-related..."
              className="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
            />
            <button onClick={onSend} disabled={!canSend} className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-white disabled:opacity-50">Send</button>
            {busy && stream && (
              <button
                onClick={() => { abortRef.current?.abort(); }}
                className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded text-white"
              >Stop</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIAssistant;
