import React from 'react';
import { Alert } from '../hooks/useAlerts';

const RISK_COLORS: Record<string, string> = {
  HIGH:   'border-red-500 bg-red-50',
  MEDIUM: 'border-yellow-500 bg-yellow-50',
  LOW:    'border-green-500 bg-green-50',
};

const RISK_BADGE: Record<string, string> = {
  HIGH:   'bg-red-500 text-white',
  MEDIUM: 'bg-yellow-500 text-white',
  LOW:    'bg-green-500 text-white',
};

interface Props {
  alert: Alert;
  onAck: (id: string) => void;
}

export function AlertCard({ alert, onAck }: Props) {
  const colors = RISK_COLORS[alert.riskLevel] ?? RISK_COLORS.LOW;
  const badge  = RISK_BADGE[alert.riskLevel] ?? RISK_BADGE.LOW;

  return (
    <div className={`border-l-4 rounded-lg p-4 mb-3 shadow-sm ${colors} ${alert.acknowledged ? 'opacity-50' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge}`}>
              {alert.riskLevel}
            </span>
            <span className="text-xs text-gray-500 font-mono">{alert.exerciseType}</span>
            <span className="text-xs text-gray-400">{new Date(alert.timestamp).toLocaleTimeString()}</span>
          </div>
          <p className="text-sm font-medium text-gray-800">{alert.description}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            Score: <strong>{alert.score}</strong> · Fase: {alert.phase}
          </p>
        </div>
        {!alert.acknowledged && (
          <button
            onClick={() => onAck(alert.id)}
            className="text-xs bg-white border border-gray-300 hover:bg-gray-50 rounded px-2 py-1 whitespace-nowrap"
          >
            ✓ Ciente
          </button>
        )}
      </div>
    </div>
  );
}
