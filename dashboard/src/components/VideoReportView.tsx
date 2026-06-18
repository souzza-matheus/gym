import React from 'react';
import { ScoreTimelinePoint, VideoAnalysisReport } from '../hooks/useVideoAnalysis';

const RISK_BADGE: Record<string, string> = {
  HIGH:   'bg-red-500 text-white',
  MEDIUM: 'bg-yellow-500 text-white',
  LOW:    'bg-green-500 text-white',
};

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-500';
  if (score >= 60) return 'text-yellow-500';
  return 'text-red-500';
}

function formatMs(ms: number): string {
  const totalSeconds = ms / 1000;
  const mins = Math.floor(totalSeconds / 60);
  const secs = (totalSeconds % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, '0')}`;
}

interface Props {
  report: VideoAnalysisReport;
}

export function VideoReportView({ report }: Props) {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Resumo — {report.exercise_type}</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center mb-4">
          <Stat label="Duração" value={formatMs(report.video_duration_ms)} />
          <Stat label="Frames analisados" value={`${report.total_frames_analyzed} (${report.frames_with_landmarks} c/ pose)`} />
          <Stat label="Repetições" value={report.total_reps} />
          <Stat
            label="Alertas disparados"
            value={report.total_alerts_fired}
            colorClass={report.total_alerts_fired > 0 ? 'text-red-500' : 'text-gray-800'}
          />
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <Stat label="Score médio" value={Math.round(report.avg_score)} colorClass={scoreColor(report.avg_score)} big />
          <Stat label="Score mínimo" value={Math.round(report.min_score)} colorClass={scoreColor(report.min_score)} big />
          <Stat label="Score máximo" value={Math.round(report.max_score)} colorClass={scoreColor(report.max_score)} big />
        </div>
      </div>

      {report.score_timeline.length > 1 && (
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Score ao longo do vídeo</h3>
          <ScoreTimelineChart points={report.score_timeline} />
        </div>
      )}

      {report.reps.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Repetições detectadas ({report.total_reps})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase">
                  <th className="py-1 pr-3">#</th>
                  <th className="py-1 pr-3">Duração</th>
                  <th className="py-1 pr-3">Score médio</th>
                  <th className="py-1 pr-3">Ângulo mín. joelho</th>
                  <th className="py-1 pr-3">Risco</th>
                  <th className="py-1 pr-3">Erros</th>
                </tr>
              </thead>
              <tbody>
                {report.reps.map(rep => (
                  <tr key={rep.rep_number} className="border-t border-gray-100">
                    <td className="py-1.5 pr-3 font-medium">{rep.rep_number}</td>
                    <td className="py-1.5 pr-3">{(rep.duration_ms / 1000).toFixed(1)}s</td>
                    <td className={`py-1.5 pr-3 font-semibold ${scoreColor(rep.avg_score)}`}>{Math.round(rep.avg_score)}</td>
                    <td className="py-1.5 pr-3">{rep.min_knee_angle != null ? `${rep.min_knee_angle}°` : '—'}</td>
                    <td className="py-1.5 pr-3">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${RISK_BADGE[rep.risk_level] ?? RISK_BADGE.LOW}`}>
                        {rep.risk_level}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-gray-500">{rep.errors.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {report.top_errors.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Erros mais frequentes</h3>
          <ul className="space-y-2">
            {report.top_errors.map(err => (
              <li key={err.error_type} className="flex items-center justify-between text-sm">
                <span className="text-gray-700">{err.error_type}</span>
                <span className="text-gray-400">{err.count}× ({err.pct_frames}% dos frames)</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.professor_alerts.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Alertas enviados ao professor</h3>
          <ul className="space-y-2">
            {report.professor_alerts.map((alert, i) => (
              <li key={i} className="border-l-4 border-yellow-400 bg-yellow-50 rounded-lg p-3 text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${RISK_BADGE[alert.risk_level] ?? RISK_BADGE.LOW}`}>
                    {alert.risk_level}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{alert.timestamp_label}</span>
                </div>
                <p className="text-gray-700">{alert.description}</p>
                <p className="text-xs text-gray-500 mt-0.5">Score: {alert.score} · Fase: {alert.phase}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.critical_frames.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Frames críticos (até 20)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase">
                  <th className="py-1 pr-3">Tempo</th>
                  <th className="py-1 pr-3">Score</th>
                  <th className="py-1 pr-3">Fase</th>
                  <th className="py-1 pr-3">Erros</th>
                </tr>
              </thead>
              <tbody>
                {report.critical_frames.map(frame => (
                  <tr key={frame.frame_seq} className="border-t border-gray-100">
                    <td className="py-1.5 pr-3 font-mono text-xs">{formatMs(frame.timestamp_ms)}</td>
                    <td className={`py-1.5 pr-3 font-semibold ${scoreColor(frame.score)}`}>{Math.round(frame.score)}</td>
                    <td className="py-1.5 pr-3 text-gray-500">{frame.phase}</td>
                    <td className="py-1.5 pr-3 text-gray-500">{frame.errors.map(e => e.type).join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, colorClass, big }: {
  label: string;
  value: string | number;
  colorClass?: string;
  big?: boolean;
}) {
  return (
    <div>
      <p className={`${big ? 'text-3xl' : 'text-lg'} font-bold ${colorClass ?? 'text-gray-800'}`}>
        {value}
      </p>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
    </div>
  );
}

function ScoreTimelineChart({ points }: { points: ScoreTimelinePoint[] }) {
  const width = 600;
  const height = 140;
  const padding = 8;
  const maxMs = Math.max(...points.map(p => p.ms), 1);
  const innerH = height - padding * 2;

  const coords = points
    .map(p => {
      const x = padding + (p.ms / maxMs) * (width - padding * 2);
      const y = height - padding - (Math.max(0, Math.min(100, p.score)) / 100) * innerH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36" preserveAspectRatio="none">
      <line x1={padding} y1={height - padding - innerH * 0.6} x2={width - padding} y2={height - padding - innerH * 0.6}
            stroke="#fde047" strokeDasharray="4 4" strokeWidth={1} />
      <line x1={padding} y1={height - padding - innerH * 0.8} x2={width - padding} y2={height - padding - innerH * 0.8}
            stroke="#86efac" strokeDasharray="4 4" strokeWidth={1} />
      <polyline points={coords} fill="none" stroke="#1f2937" strokeWidth={2} />
    </svg>
  );
}
