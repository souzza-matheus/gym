import React from 'react';
import { Alert } from '../hooks/useAlerts';

// Severidade exibida ao usuário: 2 níveis (Aviso/Grave), independentes do
// RiskLevel interno (LOW/MEDIUM/HIGH, que só dirige o score). Grave recebe
// destaque visual forte (vermelho, ícone pulsante, fonte maior na descrição)
// porque representa risco de lesão (ex.: joelho colapsando, lombar
// arredondada) — não apenas "erro grande", mas erro perigoso.
const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'border-red-600 bg-red-50',
  WARNING:  'border-yellow-500 bg-yellow-50',
};

const SEVERITY_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  WARNING:  'bg-yellow-500 text-white',
};

const SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: 'Grave',
  WARNING:  'Aviso',
};

interface Props {
  alert: Alert;
  onAck: (id: string) => void;
}

export function AlertCard({ alert, onAck }: Props) {
  const severity = alert.severity ?? 'WARNING';
  const isCritical = severity === 'CRITICAL';
  const colors = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.WARNING;
  const badge  = SEVERITY_BADGE[severity] ?? SEVERITY_BADGE.WARNING;

  return (
    <div className={`border-l-4 rounded-lg p-4 mb-3 shadow-sm ${colors} ${alert.acknowledged ? 'opacity-50' : ''} ${isCritical ? 'ring-2 ring-red-300' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            {isCritical && <span className="animate-pulse text-red-600 text-lg" aria-hidden="true">⚠</span>}
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge}`}>
              {SEVERITY_LABEL[severity] ?? severity}
            </span>
            <span className="text-xs text-gray-500 font-mono">{alert.exerciseType}</span>
            <span className="text-xs text-gray-400">{new Date(alert.timestamp).toLocaleTimeString()}</span>
          </div>
          <p className={isCritical ? 'text-base font-bold text-red-700' : 'text-sm font-medium text-gray-800'}>
            {alert.description}
          </p>
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
