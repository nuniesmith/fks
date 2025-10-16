import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import SectionHeader from '@layout/SectionHeader';
import PageContainer from '@layout/PageContainer';

import { useNotifications } from '../Notifications';

type SentMessage = {
  id: string;
  content: string;
  username?: string;
  timestamp: number;
  status: 'sending' | 'sent' | 'error';
  error?: string;
};

const STORAGE_KEY = 'fks.discord.webhookUrl';

const isLikelyDiscordWebhook = (url: string) =>
  /^https:\/\/discord\.com\/api\/webhooks\/[0-9]+\/[A-Za-z0-9_-]+$/.test(url.trim());

const DiscordChat: React.FC = () => {
  const { addNotification } = useNotifications?.() || { addNotification: (_: any) => {} } as any;
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [username, setUsername] = useState<string>('FKS App');
  const [message, setMessage] = useState<string>('');
  const [messages, setMessages] = useState<SentMessage[]>([]);
  const [saving, setSaving] = useState(false);
  const [validation, setValidation] = useState<string>('');
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) || '';
    if (saved) setWebhookUrl(saved);
  }, []);

  const saveWebhook = useCallback(() => {
    setSaving(true);
    try {
      if (!isLikelyDiscordWebhook(webhookUrl)) {
        setValidation('That does not look like a valid Discord webhook URL.');
        return;
      }
      localStorage.setItem(STORAGE_KEY, webhookUrl.trim());
      setValidation('Saved webhook URL locally.');
      try {
        addNotification?.({ type: 'success', title: 'Discord', message: 'Saved webhook URL', duration: 2500 } as any);
      } catch {}
    } finally {
      setSaving(false);
    }
  }, [webhookUrl]);

  const canSend = useMemo(() => webhookUrl && isLikelyDiscordWebhook(webhookUrl) && message.trim().length > 0, [webhookUrl, message]);

  const sendMessage = useCallback(async () => {
    if (!canSend) return;
    const tempId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const newMsg: SentMessage = {
      id: tempId,
      content: message,
      username: username?.trim() || undefined,
      timestamp: Date.now(),
      status: 'sending'
    };
    setMessages(prev => [newMsg, ...prev]);
    setMessage('');

    try {
      // First try direct webhook post
      const direct = await fetch(webhookUrl.trim(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newMsg.content, username: newMsg.username })
      });
  if (!direct.ok) {
        const text = await direct.text();
        throw new Error(text || `HTTP ${direct.status}`);
      }
      setMessages(prev => prev.map(m => (m.id === tempId ? { ...m, status: 'sent' } : m)));
  try { addNotification?.({ type: 'success', title: 'Discord', message: 'Message sent', duration: 2500 } as any); } catch {}
    } catch (err: any) {
      // On CORS or other failures, try backend proxy
      try {
        const base = (import.meta as any).env?.VITE_API_BASE || '/api';
        const proxy = await fetch(String(base).replace(/\/$/, '') + '/utils/discord-proxy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ webhook_url: webhookUrl.trim(), content: newMsg.content, username: newMsg.username })
        });
        const json = await proxy.json().catch(() => null);
  if (!proxy.ok || !json?.ok) {
          const msg = json?.error || json?.body || `Proxy HTTP ${proxy.status}`;
          throw new Error(msg);
        }
        setMessages(prev => prev.map(m => (m.id === tempId ? { ...m, status: 'sent' } : m)));
  try { addNotification?.({ type: 'success', title: 'Discord', message: 'Message sent via proxy', duration: 2500 } as any); } catch {}
      } catch (e2: any) {
        setMessages(prev => prev.map(m => (m.id === tempId ? { ...m, status: 'error', error: e2?.message || err?.message || 'Failed to send' } : m)));
  try { addNotification?.({ type: 'warning', title: 'Discord error', message: e2?.message || err?.message || 'Failed to send', duration: 5000 } as any); } catch {}
      }
    }
  }, [canSend, webhookUrl, message, username]);

  useEffect(() => {
    if (listRef.current) {
      // no-op; messages are in reverse order (newest first)
    }
  }, [messages.length]);

  return (
  <PageContainer maxWidth="5xl">
  <SectionHeader icon={<span className="text-3xl">💬</span>} title="Discord Chat" headingLevel={1 as any} titleClassName="text-3xl font-bold text-white" className="mb-6" />

        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-1 glass-card p-5">
            <h2 className="text-white font-semibold mb-3">Setup</h2>
            <ol className="list-decimal list-inside text-white/80 text-sm space-y-2">
              <li>Open your Discord Server → Settings → Integrations → Webhooks.</li>
              <li>Create a new Webhook for the channel you want to post to.</li>
              <li>Copy the Webhook URL and paste it below. It’s stored only in your browser.</li>
            </ol>
            <div className="mt-4">
              <label className="block text-white/80 text-sm mb-1">Discord Webhook URL</label>
              <input
                className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="https://discord.com/api/webhooks/..."
                value={webhookUrl}
                onChange={e => setWebhookUrl(e.target.value)}
                spellCheck={false}
              />
              <div className="flex items-center gap-2 mt-2">
                <button onClick={saveWebhook} disabled={saving} className="btn-primary px-3 py-1.5 text-sm">
                  {saving ? 'Saving…' : 'Save'}
                </button>
                {validation && <span className="text-white/60 text-xs">{validation}</span>}
              </div>
            </div>
            <div className="mt-4">
              <label className="block text-white/80 text-sm mb-1">Display Name (optional)</label>
              <input
                className="w-full bg-white/5 border border-white/10 rounded px-3 py-2 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="FKS App"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <button
                className={`btn-secondary px-3 py-1.5 text-sm ${!webhookUrl || !isLikelyDiscordWebhook(webhookUrl) ? 'opacity-50 cursor-not-allowed' : ''}`}
                disabled={!webhookUrl || !isLikelyDiscordWebhook(webhookUrl)}
                onClick={async () => {
                  try {
                    const base = (import.meta as any).env?.VITE_API_BASE || '/api';
                    const proxy = await fetch(String(base).replace(/\/$/, '') + '/utils/discord-proxy', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ webhook_url: webhookUrl.trim(), content: '[FKS] Test webhook OK', username: username?.trim() || 'FKS App' })
                    });
                    const json = await proxy.json().catch(() => null);
                    if (!proxy.ok || !json?.ok) {
                      const msg = json?.error || json?.body || `Proxy HTTP ${proxy.status}`;
                      throw new Error(msg);
                    }
                    setValidation('Test message sent via proxy.');
                    try { addNotification?.({ type: 'success', title: 'Discord', message: 'Webhook test sent', duration: 2500 } as any); } catch {}
                  } catch (e: any) {
                    const msg = e?.message || 'Failed to send test message';
                    setValidation(msg);
                    try { addNotification?.({ type: 'warning', title: 'Discord test failed', message: msg, duration: 5000 } as any); } catch {}
                  }
                }}
              >
                Test Webhook
              </button>
            </div>
            <div className="mt-4 text-xs text-white/60">
              Tip: Webhook posts only send messages. For reading live Discord messages, you'll need a backend proxy or a bot using the Discord Gateway.
            </div>
          </div>

          <div className="md:col-span-2 flex flex-col gap-4">
            <div className="glass-card p-4">
              <div className="flex items-start gap-3">
                <textarea
                  className="flex-1 bg-white/5 border border-white/10 rounded px-3 py-2 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-indigo-500 min-h-[72px]"
                  placeholder="Type a message to send to your Discord channel…"
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                />
                <button disabled={!canSend} onClick={sendMessage} className={`btn-primary h-[42px] mt-1 ${!canSend ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  Send
                </button>
              </div>
              <div className="text-xs text-white/60 mt-2">
                Supports @here/@everyone mentions. Embeds/attachments require a backend proxy.
              </div>
            </div>

            <div ref={listRef} className="glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-white/90 font-semibold">Recent (local session)</h3>
                <button className="text-xs text-white/60 hover:text-white/80" onClick={() => setMessages([])}>Clear</button>
              </div>
              {messages.length === 0 ? (
                <div className="text-white/60 text-sm">No messages yet. Your sent messages will appear here.</div>
              ) : (
                <ul className="space-y-3">
                  {messages.map(m => (
                    <li key={m.id} className="border border-white/10 rounded p-3">
                      <div className="flex items-center gap-2 text-xs text-white/60 mb-1">
                        <span>{new Date(m.timestamp).toLocaleString()}</span>
                        <span>•</span>
                        <span>{m.username || 'FKS App'}</span>
                        <span>•</span>
                        <span className={m.status === 'error' ? 'text-red-400' : m.status === 'sent' ? 'text-green-400' : 'text-white/60'}>
                          {m.status}
                        </span>
                      </div>
                      <div className="whitespace-pre-wrap text-white/90 text-sm">{m.content}</div>
                      {m.error && <div className="text-xs text-red-400 mt-1">{m.error}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
  </PageContainer>
  );
};

export default DiscordChat;
