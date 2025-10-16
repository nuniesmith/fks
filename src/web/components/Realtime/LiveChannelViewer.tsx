import { Send, Play, Pause, Trash2, Radio } from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useRealtime } from '../../hooks/useRealtime';

interface LiveChannelViewerProps {
  initialChannel?: string;
  maxMessages?: number;
  autoSubscribe?: boolean;
}

const LiveChannelViewer: React.FC<LiveChannelViewerProps> = ({ initialChannel = 'heartbeat', maxMessages = 100, autoSubscribe = true }) => {
  const { status, subscribe, unsubscribe, send } = useRealtime();
  const [channel, setChannel] = useState(initialChannel);
  const [activeChannel, setActiveChannel] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const unsubRef = useRef<null | (() => void)>(null);
  const [msgRate, setMsgRate] = useState(0);
  const countRef = useRef(0);
  const endRef = useRef<HTMLDivElement | null>(null);

  const onMsg = useCallback((m: any) => {
    setMessages((prev) => {
      const next = [...prev, m];
      if (next.length > maxMessages) next.shift();
      return next;
    });
  countRef.current += 1;
  }, [maxMessages]);

  const isSubscribed = useMemo(() => !!activeChannel, [activeChannel]);

  const handleSubscribe = useCallback(() => {
    if (!channel.trim()) return;
    if (unsubRef.current) unsubRef.current();
    unsubRef.current = subscribe(channel.trim(), onMsg);
    setActiveChannel(channel.trim());
  }, [channel, onMsg, subscribe]);

  const handleUnsubscribe = useCallback(() => {
    if (activeChannel) unsubscribe(activeChannel);
    if (unsubRef.current) unsubRef.current();
    unsubRef.current = null;
    setActiveChannel(null);
  }, [activeChannel, unsubscribe]);

  const clearMessages = useCallback(() => setMessages([]), []);

  useEffect(() => {
    // auto-subscribe on mount when configured
    if (autoSubscribe && initialChannel) {
      const off = subscribe(initialChannel, onMsg);
      setActiveChannel(initialChannel);
      unsubRef.current = off;
    }
    return () => {
      if (unsubRef.current) unsubRef.current();
    };
  }, [autoSubscribe, initialChannel, onMsg, subscribe]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setMsgRate(countRef.current);
      countRef.current = 0;
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <div className="flex items-center gap-3">
          <Radio className={`w-4 h-4 ${status === 'open' ? 'text-green-400' : status === 'connecting' ? 'text-yellow-400' : 'text-red-400'}`} />
          <span className="text-sm text-gray-300">WS: {status}</span>
          <span className="text-xs text-gray-400">{isSubscribed ? `rate: ${msgRate}/s` : 'idle'}</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="px-2 py-1 rounded bg-gray-900 border border-gray-700 text-sm text-white"
            placeholder="channel (e.g. ticks:AAPL)"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          />
          {!isSubscribed ? (
            <button
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-green-600 hover:bg-green-700 text-white text-sm disabled:opacity-50"
              onClick={handleSubscribe}
              disabled={status !== 'open' || !channel.trim()}
              title="Subscribe"
            >
              <Play className="w-4 h-4" /> Subscribe
            </button>
          ) : (
            <button
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-yellow-600 hover:bg-yellow-700 text-white text-sm"
              onClick={handleUnsubscribe}
              title="Unsubscribe"
            >
              <Pause className="w-4 h-4" /> Unsubscribe
            </button>
          )}
          <button
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm"
            onClick={() => send({ type: 'ping', ts: Date.now() })}
            disabled={status !== 'open'}
            title="Send ping"
          >
            <Send className="w-4 h-4" /> Ping
          </button>
          <button
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm"
            onClick={clearMessages}
            title="Clear"
          >
            <Trash2 className="w-4 h-4" /> Clear
          </button>
        </div>
      </div>
      <div className="max-h-64 overflow-auto p-3 font-mono text-xs text-gray-200">
        {messages.length === 0 ? (
          <div className="text-gray-400">No messages yet. Subscribe to a channel.</div>
        ) : (
          messages.map((m, i) => (
            <pre key={i} className="whitespace-pre-wrap break-words">
{JSON.stringify(m, null, 2)}
            </pre>
          ))
        )}
        <div ref={endRef} />
      </div>
      {activeChannel && (
        <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-700">
          Subscribed to <span className="text-gray-200">{activeChannel}</span> · Showing last {Math.min(messages.length, maxMessages)} messages
        </div>
      )}
    </div>
  );
};

export default LiveChannelViewer;
