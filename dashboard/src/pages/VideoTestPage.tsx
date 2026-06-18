import React, { useRef, useState } from 'react';
import { ExerciseType, useVideoAnalysis } from '../hooks/useVideoAnalysis';
import { VideoReportView } from '../components/VideoReportView';

const ACADEMY_ID = import.meta.env.VITE_ACADEMY_ID ?? '00000000-0000-0000-0000-000000000001';

const EXERCISES: { value: ExerciseType; label: string }[] = [
  { value: 'SQUAT',         label: 'Agachamento (Squat)' },
  { value: 'DEADLIFT',      label: 'Levantamento Terra (Deadlift)' },
  { value: 'LUNGE',         label: 'Avanço (Lunge)' },
  { value: 'BENCH_PRESS',   label: 'Supino (Bench Press)' },
  { value: 'BENT_OVER_ROW', label: 'Remada Curvada (Bent-over Row)' },
];

const FPS_OPTIONS = [
  { value: 200, label: '5 fps — mais rápido' },
  { value: 100, label: '10 fps' },
  { value: 50, label: '20 fps' },
  { value: 33, label: '30 fps — mais lento' },
];

const MAX_VIDEO_SIZE = 500 * 1024 * 1024; // 500 MB

export function VideoTestPage() {
  const { report, loading, error, analyze, reset } = useVideoAnalysis();
  const [file, setFile] = useState<File | null>(null);
  const [exerciseType, setExerciseType] = useState<ExerciseType>('SQUAT');
  const [frameIntervalMs, setFrameIntervalMs] = useState(200);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (selected && selected.size > MAX_VIDEO_SIZE) {
      setFileError('Vídeo muito grande. Máximo: 500 MB.');
      setFile(null);
      return;
    }
    setFileError(null);
    setFile(selected);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    analyze({ file, exerciseType, frameIntervalMs, academyId: ACADEMY_ID });
  };

  const handleNewTest = () => {
    reset();
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900 mb-1">Testar análise com vídeo</h2>
          <p className="text-sm text-gray-500 mb-4">
            Envie um vídeo (.mp4, .mov, .avi — máx 500 MB / 5 min) para rodar o mesmo
            pipeline de detecção de pose e análise de execução usado pelo app, sem
            precisar do celular.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Arquivo de vídeo</label>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/quicktime,video/x-msvideo,video/avi"
                onChange={handleFileChange}
                disabled={loading}
                className="block w-full text-sm text-gray-600 border border-gray-300 rounded-lg p-2
                           file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0
                           file:bg-gray-800 file:text-white file:text-sm file:cursor-pointer"
              />
              {fileError && <p className="text-xs text-red-500 mt-1">{fileError}</p>}
              {file && !fileError && (
                <p className="text-xs text-gray-500 mt-1">
                  {file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Exercício</label>
                <select
                  value={exerciseType}
                  onChange={e => setExerciseType(e.target.value as ExerciseType)}
                  disabled={loading}
                  className="block w-full text-sm border border-gray-300 rounded-lg p-2"
                >
                  {EXERCISES.map(ex => (
                    <option key={ex.value} value={ex.value}>{ex.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Taxa de análise</label>
                <select
                  value={frameIntervalMs}
                  onChange={e => setFrameIntervalMs(Number(e.target.value))}
                  disabled={loading}
                  className="block w-full text-sm border border-gray-300 rounded-lg p-2"
                >
                  {FPS_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={!file || loading}
                className="bg-gray-800 text-white text-sm font-medium px-4 py-2 rounded-lg
                           disabled:opacity-40 hover:bg-gray-700 transition-colors"
              >
                {loading ? 'Analisando…' : 'Analisar vídeo'}
              </button>
              {report && (
                <button
                  type="button"
                  onClick={handleNewTest}
                  className="text-sm text-gray-600 hover:text-gray-900"
                >
                  Novo teste
                </button>
              )}
            </div>

            {loading && (
              <p className="text-xs text-gray-500">
                Processando frame a frame — vídeos longos podem levar alguns minutos.
              </p>
            )}
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
            )}
          </form>
        </div>

        {report && <VideoReportView report={report} />}
      </div>
    </div>
  );
}
