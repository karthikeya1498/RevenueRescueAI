import { useCallback, useEffect, useRef, useState } from 'react';

export type RecoveryEvent = {
  version: number;
  id: string;
  occurred_at: string;
  event: {
    type: string;
    title: string;
    message: string;
    account?: string;
    amount?: number;
    severity: 'success' | 'warning' | 'info' | 'system';
    icon: 'check' | 'activity' | 'spark' | 'shield';
  };
};

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline';

const socketUrl = () => {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  if (configured) return configured;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.hostname}:8000/ws/recovery`;
};

function parseEvent(data: string): RecoveryEvent | null {
  try {
    const parsed = JSON.parse(data) as RecoveryEvent;
    if (!parsed?.event?.type || !parsed.event.title || !parsed.event.message) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function useRecoverySocket(enabled: boolean) {
  const [status, setStatus] = useState<ConnectionStatus>('offline');
  const [events, setEvents] = useState<RecoveryEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<RecoveryEvent | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<number | undefined>(undefined);

  const connect = useCallback(() => {
    if (!enabled || socketRef.current?.readyState === WebSocket.OPEN) return;
    setStatus(retryRef.current ? 'reconnecting' : 'connecting');
    const socket = new WebSocket(socketUrl());
    socketRef.current = socket;
    socket.onopen = () => { retryRef.current = 0; setStatus('connected'); };
    socket.onmessage = (message) => {
      const event = parseEvent(message.data);
      if (!event || event.event.type.startsWith('connection.')) return;
      setLastEvent(event);
      setEvents((current) => [event, ...current].slice(0, 12));
    };
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      socketRef.current = null;
      if (!enabled) return;
      setStatus('reconnecting');
      const delay = Math.min(1000 * 2 ** retryRef.current, 12000);
      retryRef.current += 1;
      timerRef.current = window.setTimeout(connect, delay);
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    connect();
    const heartbeat = window.setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send('ping');
    }, 8000);
    return () => {
      window.clearInterval(heartbeat);
      if (timerRef.current) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
      socketRef.current = null;
      setStatus('offline');
    };
  }, [connect, enabled]);

  const dismissEvent = useCallback(() => setLastEvent(null), []);
  const clearEvents = useCallback(() => setEvents([]), []);
  return { status, events, lastEvent, dismissEvent, clearEvents };
}
