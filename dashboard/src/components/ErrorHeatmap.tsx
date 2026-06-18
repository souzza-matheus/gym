import React from 'react';
import { Alert } from '../hooks/useAlerts';

interface Props {
  alerts: Alert[];
}

const DAYS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

const ERROR_LABELS: Record<string, string> = {
  KNEE_CAVE_LEFT:           'Joelho esq. p/ dentro',
  KNEE_CAVE_RIGHT:          'Joelho dir. p/ dentro',
  BACK_NOT_STRAIGHT:        'Coluna inclinada',
  BACK_ROUNDED:             'Lombar arredondada',
  DEPTH_INSUFFICIENT:       'Profundidade insuficiente',
  KNEE_OVER_TOE_LEFT:       'Joelho esq. além do pé',
  KNEE_OVER_TOE_RIGHT:      'Joelho dir. além do pé',
  ELBOW_FLARE:              'Cotovelos abertos',
  ELBOW_INSUFFICIENT_RANGE: 'Amplitude insuficiente',
  WRIST_BENT:               'Pulso dobrado',
  ROW_INCOMPLETE:           'Remada incompleta',
  HIPS_TOO_HIGH:            'Quadril alto',
};

export function ErrorHeatmap({ alerts }: Props) {
  if (alerts.length === 0) return null;

  // Agrupa: errorType → dayOfWeek → count
  const matrix: Record<string, number[]> = {};
  alerts.forEach(a => {
    const day = new Date(a.timestamp).getDay();
    if (!matrix[a.errorType]) matrix[a.errorType] = Array(7).fill(0);
    matrix[a.errorType][day]++;
  });

  const errorTypes = Object.keys(matrix);
  const maxVal = Math.max(...Object.values(matrix).flatMap(v => v));

  const cellColor = (count: number) => {
    if (count === 0) return '#f3f4f6';
    const intensity = count / maxVal;
    if (intensity < 0.33) return '#fde68a';
    if (intensity < 0.66) return '#f97316';
    return '#dc2626';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Mapa de erros por dia da semana</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left text-gray-400 font-normal pr-3 py-1 min-w-[140px]">Erro</th>
              {DAYS.map(d => (
                <th key={d} className="text-center text-gray-400 font-normal px-1 py-1 min-w-[32px]">{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {errorTypes.map(et => (
              <tr key={et}>
                <td className="text-gray-600 pr-3 py-1 truncate max-w-[140px]">
                  {ERROR_LABELS[et] ?? et.replace(/_/g, ' ').toLowerCase()}
                </td>
                {matrix[et].map((count, i) => (
                  <td key={i} className="px-1 py-1 text-center">
                    <div
                      title={`${count} alerta(s)`}
                      style={{ backgroundColor: cellColor(count) }}
                      className="w-6 h-6 rounded mx-auto flex items-center justify-center text-[10px] font-medium"
                    >
                      {count > 0 ? count : ''}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-2 mt-3">
        <span className="text-xs text-gray-400">Menos</span>
        {['#fde68a', '#f97316', '#dc2626'].map(c => (
          <div key={c} className="w-4 h-4 rounded" style={{ backgroundColor: c }} />
        ))}
        <span className="text-xs text-gray-400">Mais</span>
      </div>
    </div>
  );
}
