import React, { useEffect, useState } from 'react';
import { useAlerts } from '../hooks/useAlerts';
import { AlertCard } from '../components/AlertCard';
import { ErrorHeatmap } from '../components/ErrorHeatmap';
import { usePushNotification } from '../hooks/usePushNotification';

const ACADEMY_ID = import.meta.env.VITE_ACADEMY_ID ?? '00000000-0000-0000-0000-000000000001';
const USER_ID    = import.meta.env.VITE_USER_ID    ?? 'professor';

export function TeacherDashboard() {
  const { alerts, analysis, connected, acknowledge } = useAlerts(ACADEMY_ID, USER_ID);
  const { supported: pushSupported, permission, register: registerPush, notify } = usePushNotification();
  const [filter, setFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM'>('ALL');

  // Dispara push notification quando chega alerta HIGH com aba em background
  useEffect(() => {
    const latest = alerts[0];
    if (!latest || latest.acknowledged) return;
    if (latest.riskLevel === 'HIGH') {
      notify(
        'GymVision — Alerta HIGH',
        latest.description,
        `${latest.sessionId}-${latest.errorType}`,
      );
    }
  }, [alerts[0]?.id]);

  const filtered = alerts.filter(a =>
    filter === 'ALL' ? true : a.riskLevel === filter
  );

  const unread = alerts.filter(a => !a.acknowledged).length;

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      {/* Header */}
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">GymVision</h1>
            <p className="text-sm text-gray-500">Dashboard do Professor</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`flex items-center gap-1.5 text-sm font-medium ${connected ? 'text-green-600' : 'text-red-500'}`}>
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {connected ? 'Ao vivo' : 'Desconectado'}
            </span>
            {pushSupported && permission !== 'granted' && (
              <button
                onClick={registerPush}
                className="text-xs text-blue-600 border border-blue-200 rounded-lg px-2 py-1 hover:bg-blue-50"
              >
                Ativar notificações
              </button>
            )}
            {unread > 0 && (
              <span className="bg-red-500 text-white text-xs font-bold px-2 py-1 rounded-full">
                {unread} novo{unread > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Score cards — alunos ativos */}
        {Object.keys(analysis).length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {Object.entries(analysis).map(([studentId, data]) => (
              <div key={studentId} className="bg-white rounded-xl p-3 shadow-sm text-center">
                <p className="text-xs text-gray-400 truncate">{studentId.slice(0, 8)}…</p>
                <p className={`text-3xl font-bold mt-1 ${data.score >= 80 ? 'text-green-500' : data.score >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {Math.round(data.score)}
                </p>
                <p className="text-xs text-gray-500">{data.phase}</p>
              </div>
            ))}
          </div>
        )}

        {/* Filter */}
        <div className="flex gap-2 mb-4">
          {(['ALL', 'HIGH', 'MEDIUM'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-sm px-3 py-1.5 rounded-full font-medium transition-colors
                ${filter === f ? 'bg-gray-800 text-white' : 'bg-white text-gray-600 hover:bg-gray-200'}`}
            >
              {f === 'ALL' ? 'Todos' : f}
              {f === 'HIGH' && <span className="ml-1 text-red-400">●</span>}
              {f === 'MEDIUM' && <span className="ml-1 text-yellow-400">●</span>}
            </button>
          ))}
        </div>

        {/* Mapa de calor de erros */}
        {alerts.length > 0 && (
          <div className="mb-4">
            <ErrorHeatmap alerts={alerts} />
          </div>
        )}

        {/* Alert list */}
        <div>
          {filtered.length === 0 ? (
            <div className="bg-white rounded-xl p-8 text-center text-gray-400 shadow-sm">
              <p className="text-4xl mb-2">✅</p>
              <p className="text-sm">Nenhum alerta. Todos estão treinando corretamente!</p>
            </div>
          ) : (
            filtered.map(alert => (
              <AlertCard key={alert.id} alert={alert} onAck={acknowledge} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
