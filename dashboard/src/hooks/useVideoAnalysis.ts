import { useCallback, useState } from 'react';

export type ExerciseType = 'SQUAT' | 'DEADLIFT' | 'LUNGE' | 'BENCH_PRESS' | 'BENT_OVER_ROW';

export interface TopError {
  error_type: string;
  count: number;
  pct_frames: number;
}

export interface ProfessorAlert {
  timestamp_ms: number;
  timestamp_label: string;
  frame_seq: number;
  error_type: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  severity: 'WARNING' | 'CRITICAL';
  description: string;
  joint_angle: number | null;
  score: number;
  phase: string;
  channel: string;
}

export interface RepReport {
  rep_number: number;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  min_knee_angle: number | null;
  avg_score: number;
  errors: string[];
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  severity: 'WARNING' | 'CRITICAL';
}

export interface ScoreTimelinePoint {
  ms: number;
  score: number;
  phase: string;
}

export interface CriticalFrame {
  frame_seq: number;
  timestamp_ms: number;
  score: number;
  phase: string;
  errors: { type: string; risk: string; severity: string; desc: string }[];
}

export interface VideoAnalysisReport {
  exercise_type: string;
  video_duration_ms: number;
  total_frames_analyzed: number;
  frames_with_landmarks: number;
  analysis_fps: number;
  avg_score: number;
  min_score: number;
  max_score: number;
  total_reps: number;
  total_alerts_fired: number;
  top_errors: TopError[];
  professor_alerts: ProfessorAlert[];
  reps: RepReport[];
  score_timeline: ScoreTimelinePoint[];
  phase_distribution: Record<string, number>;
  avg_score_by_phase: Record<string, number>;
  critical_frames: CriticalFrame[];
}

interface AnalyzeParams {
  file: File;
  exerciseType: ExerciseType;
  frameIntervalMs: number;
  academyId?: string;
}

export function useVideoAnalysis() {
  const [report, setReport] = useState<VideoAnalysisReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async ({ file, exerciseType, frameIntervalMs, academyId }: AnalyzeParams) => {
    setLoading(true);
    setError(null);
    setReport(null);

    const formData = new FormData();
    formData.append('video', file);
    formData.append('exercise_type', exerciseType);
    formData.append('frame_interval_ms', String(frameIntervalMs));
    if (academyId) formData.append('academy_id', academyId);

    try {
      const res = await fetch('/api/v1/pose/analyze-video', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Erro ${res.status} ao analisar o vídeo.`);
      }

      setReport(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido ao analisar o vídeo.');
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setReport(null);
    setError(null);
  }, []);

  return { report, loading, error, analyze, reset };
}
