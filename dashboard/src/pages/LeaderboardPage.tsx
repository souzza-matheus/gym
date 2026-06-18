import React, { useEffect, useState } from 'react';
import { getStoredToken } from '../hooks/useAuth';

const ACADEMY_ID = import.meta.env.VITE_ACADEMY_ID ?? '00000000-0000-0000-0000-000000000001';

interface LeaderboardEntry {
  rank: number;
  student_id: string;
  avg_score: number;
  sessions: number;
  total_reps: number;
}

interface Achievement {
  key: string;
  name: string;
  description: string;
  icon: string;
}

interface GamificationData {
  student_id: string;
  points: number;
  level: number;
  next_level_points: number;
  streak_days: number;
  total_sessions: number;
  clean_sessions: number;
  total_reps: number;
  best_score: number;
  achievements: Achievement[];
}

function medalColor(rank: number): string {
  if (rank === 1) return 'text-yellow-500';
  if (rank === 2) return 'text-gray-400';
  if (rank === 3) return 'text-amber-600';
  return 'text-gray-500';
}

function medalEmoji(rank: number): string {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

export function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [gamification, setGamification] = useState<GamificationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const token = getStoredToken();

  useEffect(() => {
    setLoading(true);
    const headers = { Authorization: `Bearer ${token}` };

    Promise.all([
      fetch(`/api/v1/analytics/academy/${ACADEMY_ID}/leaderboard?limit=10`, { headers })
        .then(r => r.json()),
    ])
      .then(([lbBody]) => {
        setLeaderboard(lbBody.leaderboard ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError('Erro ao carregar dados de ranking.');
        setLoading(false);
      });
  }, [token]);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center gap-3">
          <span className="text-3xl">🏆</span>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Ranking da Academia</h2>
            <p className="text-sm text-gray-500">Top alunos por score médio</p>
          </div>
        </div>

        {loading && (
          <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400 text-sm">
            Carregando…
          </div>
        )}

        {error && (
          <div className="bg-red-50 rounded-xl p-4 text-red-600 text-sm">{error}</div>
        )}

        {/* Leaderboard */}
        {!loading && !error && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            {leaderboard.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                Nenhuma sessão registrada ainda. Treine para aparecer no ranking!
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="text-left text-xs font-semibold text-gray-500 px-4 py-3 w-12">Pos.</th>
                    <th className="text-left text-xs font-semibold text-gray-500 px-4 py-3">Aluno</th>
                    <th className="text-right text-xs font-semibold text-gray-500 px-4 py-3">Score</th>
                    <th className="text-right text-xs font-semibold text-gray-500 px-4 py-3 hidden sm:table-cell">Sessões</th>
                    <th className="text-right text-xs font-semibold text-gray-500 px-4 py-3 hidden sm:table-cell">Reps</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {leaderboard.map(entry => (
                    <tr key={entry.student_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <span className={`text-base font-bold ${medalColor(entry.rank)}`}>
                          {medalEmoji(entry.rank)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-bold text-gray-600 flex-shrink-0">
                            {entry.student_id.slice(0, 2).toUpperCase()}
                          </div>
                          <span className="text-sm text-gray-700 font-medium">
                            {entry.student_id.slice(0, 8)}…
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ScoreBadge score={entry.avg_score} />
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-gray-500 hidden sm:table-cell">
                        {entry.sessions}
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-gray-500 hidden sm:table-cell">
                        {entry.total_reps}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Gamification info box */}
        <div className="bg-white rounded-xl shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Como funciona a pontuação?</h3>
          <div className="space-y-2 text-sm text-gray-600">
            <p>• Cada sessão contribui com <strong>avg_score pontos</strong> para o total acumulado.</p>
            <p>• A cada <strong>500 pontos</strong> você sobe de nível.</p>
            <p>• Treine dias seguidos para manter o <strong>streak</strong> 🔥</p>
            <p>• Sessões sem alertas HIGH/MEDIUM desbloqueiam conquistas especiais.</p>
          </div>
        </div>

        {/* Achievements reference */}
        <div className="bg-white rounded-xl shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Conquistas disponíveis</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {ACHIEVEMENT_CATALOG.map(a => (
              <div key={a.key} className="bg-gray-50 rounded-lg p-3 text-center">
                <div className="text-2xl mb-1">{a.icon}</div>
                <p className="text-xs font-semibold text-gray-800">{a.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">{a.description}</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80 ? 'bg-green-100 text-green-700' :
    score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700';
  return (
    <span className={`inline-flex items-center justify-center px-2.5 py-0.5 rounded-full text-sm font-bold ${color}`}>
      {Math.round(score)}
    </span>
  );
}

const ACHIEVEMENT_CATALOG = [
  { key: 'first_session',  name: 'Primeira Sessão',  description: 'Complete 1 sessão',              icon: '🏃' },
  { key: 'ten_sessions',   name: '10 Sessões',        description: 'Complete 10 sessões',            icon: '🔥' },
  { key: 'fifty_sessions', name: '50 Sessões',        description: 'Complete 50 sessões',            icon: '💪' },
  { key: 'clean_form',     name: 'Técnica Perfeita',  description: 'Sessão sem alertas',             icon: '✅' },
  { key: 'clean_streak',   name: 'Mestre da Forma',   description: '5 sessões limpas',               icon: '🏆' },
  { key: 'rep_100',        name: '100 Repetições',    description: 'Acumule 100 reps',               icon: '💯' },
  { key: 'rep_1000',       name: '1.000 Reps',        description: 'Acumule 1.000 reps',             icon: '🚀' },
  { key: 'streak_3',       name: 'Sequência de 3',    description: '3 dias seguidos',                icon: '📅' },
  { key: 'streak_7',       name: 'Semana Completa',   description: '7 dias seguidos',                icon: '🗓️' },
  { key: 'perfect_score',  name: 'Score Perfeito',    description: 'Score 100 em uma sessão',        icon: '⭐' },
  { key: 'level_5',        name: 'Nível 5',           description: 'Atinja 2.500 pontos',            icon: '🥈' },
  { key: 'level_10',       name: 'Nível 10',          description: 'Atinja 5.000 pontos',            icon: '🥇' },
];
