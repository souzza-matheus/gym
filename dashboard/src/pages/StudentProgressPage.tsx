import React, { useEffect, useState } from 'react';
import { getStoredToken, getStoredUser } from '../hooks/useAuth';

interface SessionSummary {
  id:           string;
  exerciseType: string;
  avgScore:     number;
  totalReps:    number;
  alertCount:   number;
  startedAt:    string;
  status:       string;
}

const EXERCISE_LABELS: Record<string, string> = {
  SQUAT:         'Agachamento',
  DEADLIFT:      'Levantamento Terra',
  LUNGE:         'Avanço',
  BENCH_PRESS:   'Supino',
  BENT_OVER_ROW: 'Remada Curvada',
};

function ScoreLine({ sessions }: { sessions: SessionSummary[] }) {
  if (sessions.length < 2) return null;
  const w = 480, h = 120, pad = 32;
  const scores = sessions.map(s => s.avgScore);
  const minS = Math.min(...scores, 0), maxS = Math.max(...scores, 100);
  const xStep = (w - pad * 2) / (sessions.length - 1);
  const yScale = (v: number) => h - pad - ((v - minS) / (maxS - minS || 1)) * (h - pad * 2);

  const points = sessions.map((s, i) => `${pad + i * xStep},${yScale(s.avgScore)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 120 }}>
      <polyline fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinejoin="round" points={points} />
      {sessions.map((s, i) => {
        const cx = pad + i * xStep;
        const cy = yScale(s.avgScore);
        const color = s.avgScore >= 80 ? '#22c55e' : s.avgScore >= 60 ? '#f59e0b' : '#ef4444';
        return (
          <g key={s.id}>
            <circle cx={cx} cy={cy} r="5" fill={color} />
            <text x={cx} y={cy - 9} textAnchor="middle" fontSize="10" fill="#374151">
              {Math.round(s.avgScore)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function usePdfDownload(studentId: string | undefined) {
  const [downloading, setDownloading] = useState(false);

  const download = async (month?: string) => {
    if (!studentId) return;
    const token = getStoredToken();
    setDownloading(true);
    try {
      const qs  = month ? `?month=${month}` : '';
      const res = await fetch(`/api/v1/analytics/student/${studentId}/report/pdf${qs}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Erro ao gerar PDF');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `gymvision-${studentId.slice(0, 8)}-${month ?? new Date().toISOString().slice(0, 7)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Não foi possível gerar o relatório PDF.');
    } finally {
      setDownloading(false);
    }
  };

  return { download, downloading };
}

export function StudentProgressPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [exercise, setExercise] = useState('ALL');
  const user = getStoredUser();
  const { download, downloading } = usePdfDownload(user?.id);

  useEffect(() => {
    const token = getStoredToken();
    setLoading(true);
    fetch('/api/v1/analytics/my/sessions', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(body => setSessions(body.data ?? body ?? []))
      .catch(() => setError('Erro ao carregar histórico.'))
      .finally(() => setLoading(false));
  }, []);

  const exercises = Array.from(new Set(sessions.map(s => s.exerciseType)));
  const filtered  = exercise === 'ALL' ? sessions : sessions.filter(s => s.exerciseType === exercise);
  const sorted    = [...filtered].sort((a, b) => new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime());

  const avgScore  = sorted.length ? sorted.reduce((s, x) => s + x.avgScore, 0) / sorted.length : 0;
  const totalReps = sorted.reduce((s, x) => s + x.totalReps, 0);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Progresso do Aluno</h2>
          <button
            onClick={() => download()}
            disabled={downloading || !user?.id}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg font-medium
              bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors"
          >
            {downloading ? (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            )}
            Relatório PDF
          </button>
        </div>

        {/* Filtro por exercício */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setExercise('ALL')}
            className={`text-sm px-3 py-1.5 rounded-full font-medium transition-colors
              ${exercise === 'ALL' ? 'bg-gray-800 text-white' : 'bg-white text-gray-600 hover:bg-gray-200'}`}
          >
            Todos
          </button>
          {exercises.map(ex => (
            <button
              key={ex}
              onClick={() => setExercise(ex)}
              className={`text-sm px-3 py-1.5 rounded-full font-medium transition-colors
                ${exercise === ex ? 'bg-gray-800 text-white' : 'bg-white text-gray-600 hover:bg-gray-200'}`}
            >
              {EXERCISE_LABELS[ex] ?? ex}
            </button>
          ))}
        </div>

        {/* Cards resumo */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Score médio', value: Math.round(avgScore), color: avgScore >= 80 ? 'text-green-600' : avgScore >= 60 ? 'text-yellow-600' : 'text-red-600' },
            { label: 'Sessões',     value: sorted.length,        color: 'text-blue-600' },
            { label: 'Reps totais', value: totalReps,             color: 'text-purple-600' },
          ].map(c => (
            <div key={c.label} className="bg-white rounded-xl p-4 shadow-sm text-center">
              <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
              <p className="text-xs text-gray-500 mt-1">{c.label}</p>
            </div>
          ))}
        </div>

        {/* Gráfico de evolução */}
        {sorted.length >= 2 && (
          <div className="bg-white rounded-xl shadow-sm p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Evolução do score</h3>
            <ScoreLine sessions={sorted} />
            <div className="flex justify-between text-xs text-gray-400 mt-1 px-1">
              <span>{new Date(sorted[0].startedAt).toLocaleDateString('pt-BR')}</span>
              <span>{new Date(sorted[sorted.length - 1].startedAt).toLocaleDateString('pt-BR')}</span>
            </div>
          </div>
        )}

        {/* Lista de sessões */}
        {loading && <p className="text-sm text-gray-500 text-center py-8">Carregando…</p>}
        {error   && <p className="text-sm text-red-600 text-center py-4">{error}</p>}
        {!loading && !error && (
          <div className="space-y-2">
            {[...sorted].reverse().map(s => (
              <div key={s.id} className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-4">
                <div className={`text-2xl font-bold w-12 text-center
                  ${s.avgScore >= 80 ? 'text-green-600' : s.avgScore >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {Math.round(s.avgScore)}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">
                    {EXERCISE_LABELS[s.exerciseType] ?? s.exerciseType}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(s.startedAt).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })}
                    {' · '}{s.totalReps} reps{s.alertCount > 0 ? ` · ${s.alertCount} alertas` : ''}
                  </p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium
                  ${s.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {s.status === 'COMPLETED' ? 'Concluída' : 'Ativa'}
                </span>
              </div>
            ))}
            {sorted.length === 0 && (
              <div className="bg-white rounded-xl p-8 text-center text-gray-400 shadow-sm">
                <p className="text-sm">Nenhuma sessão encontrada.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
