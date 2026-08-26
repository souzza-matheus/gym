import { useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

export interface Alert {
  id: string;
  sessionId: string;
  studentId: string;
  exerciseType: string;
  errorType: string;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  severity: 'WARNING' | 'CRITICAL';
  description: string;
  score: number;
  phase: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface AnalysisFeedback {
  studentId: string;
  score: number;
  phase: string;
  frameSeq: number;
}

const WS_URL = import.meta.env.VITE_WS_URL ?? 'http://localhost:8085';

export function useAlerts(academyId: string, userId: string) {
  const socketRef = useRef<Socket | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, AnalysisFeedback>>({});
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // 'polling' como fallback de 'websocket' — redes de academia com proxy/
    // firewall restritivo às vezes bloqueiam upgrade para WS puro.
    const socket = io(`${WS_URL}/ws`, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      socket.emit('join_academy', { academyId, userId, role: 'TEACHER' });
    });

    socket.on('disconnect', () => setConnected(false));

    socket.on('alert', (alert: Omit<Alert, 'id' | 'acknowledged'>) => {
      const newAlert: Alert = {
        ...alert,
        id: `${alert.sessionId}-${alert.timestamp}`,
        acknowledged: false,
      };
      setAlerts(prev => [newAlert, ...prev].slice(0, 100)); // keep last 100
    });

    socket.on('analysis', (data: AnalysisFeedback) => {
      setAnalysis(prev => ({ ...prev, [data.studentId]: data }));
    });

    return () => { socket.disconnect(); };
  }, [academyId, userId]);

  const acknowledge = useCallback((alertId: string) => {
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
  }, []);

  return { alerts, analysis, connected, acknowledge };
}
