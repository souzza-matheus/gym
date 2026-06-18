import React, { useEffect, useState } from 'react';
import { getStoredToken, getStoredUser } from '../hooks/useAuth';

const EXERCISES = ['SQUAT', 'DEADLIFT', 'LUNGE', 'BENCH_PRESS', 'BENT_OVER_ROW'];

const exerciseLabel: Record<string, string> = {
  SQUAT:         'Agachamento',
  DEADLIFT:      'Levantamento Terra',
  LUNGE:         'Avanço',
  BENCH_PRESS:   'Supino',
  BENT_OVER_ROW: 'Remada Curvada',
};

const DAY_LABELS = ['—', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

interface PlanItem {
  id?: string;
  exerciseType: string;
  sets: number;
  repsPerSet: number;
  loadKg: number | null;
  notes: string;
  orderIndex: number;
}

interface WorkoutPlan {
  id: string;
  studentId: string;
  name: string;
  dayOfWeek: number | null;
  active: boolean;
  items: PlanItem[];
}

interface Student {
  id: string;
  name: string;
  email: string;
}

const emptyItem = (): PlanItem => ({
  exerciseType: 'SQUAT', sets: 3, repsPerSet: 10,
  loadKg: null, notes: '', orderIndex: 0,
});

export function WorkoutPlanPage() {
  const token   = getStoredToken();
  const user    = getStoredUser();
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const [students, setStudents]     = useState<Student[]>([]);
  const [plans, setPlans]           = useState<WorkoutPlan[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [showForm, setShowForm]     = useState(false);

  // form state
  const [planName, setPlanName]     = useState('');
  const [dayOfWeek, setDayOfWeek]   = useState<number>(0);
  const [formStudent, setFormStudent] = useState('');
  const [items, setItems]           = useState<PlanItem[]>([emptyItem()]);
  const [saving, setSaving]         = useState(false);

  const academyId = user?.academyId ?? '00000000-0000-0000-0000-000000000001';

  useEffect(() => {
    fetch('/api/v1/users?role=STUDENT', { headers })
      .then(r => r.json())
      .then(b => setStudents(b.data ?? b ?? []))
      .catch(() => setError('Erro ao carregar alunos.'));
  }, []);

  const loadPlans = (studentId: string) => {
    setSelectedStudent(studentId);
    if (!studentId) { setPlans([]); return; }
    setLoading(true);
    fetch(`/api/v1/workout-plans/student/${studentId}`, { headers })
      .then(r => r.json())
      .then(b => setPlans(b.data ?? []))
      .catch(() => setError('Erro ao carregar planos.'))
      .finally(() => setLoading(false));
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formStudent) return;
    setSaving(true);
    try {
      const body = {
        academyId,
        studentId: formStudent,
        professorId: user?.id ?? '00000000-0000-0000-0000-000000000001',
        name: planName,
        dayOfWeek: dayOfWeek === 0 ? null : dayOfWeek,
        items: items.map((it, idx) => ({ ...it, orderIndex: idx, notes: it.notes || null })),
      };
      const res = await fetch('/api/v1/workout-plans', {
        method: 'POST', headers, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Erro ${res.status}`);
      setShowForm(false);
      setPlanName(''); setDayOfWeek(0); setItems([emptyItem()]); setFormStudent('');
      if (formStudent === selectedStudent) loadPlans(selectedStudent);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (planId: string) => {
    if (!confirm('Remover este plano?')) return;
    await fetch(`/api/v1/workout-plans/${planId}`, { method: 'DELETE', headers });
    setPlans(prev => prev.filter(p => p.id !== planId));
  };

  const addItem = () => setItems(prev => [...prev, { ...emptyItem(), orderIndex: prev.length }]);
  const removeItem = (idx: number) => setItems(prev => prev.filter((_, i) => i !== idx));
  const updateItem = (idx: number, patch: Partial<PlanItem>) =>
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, ...patch } : it));

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Planos de Treino 📋</h1>
          <p className="text-sm text-gray-500 mt-1">Crie e gerencie planos por aluno</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-gray-900 text-white text-sm px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
        >
          + Novo plano
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>fechar</button>
        </div>
      )}

      {/* Student selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Ver planos do aluno</label>
        <select
          value={selectedStudent}
          onChange={e => loadPlans(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full max-w-sm"
        >
          <option value="">Selecione um aluno…</option>
          {students.map(s => (
            <option key={s.id} value={s.id}>{s.name} — {s.email}</option>
          ))}
        </select>
      </div>

      {/* Plan list */}
      {loading && <p className="text-sm text-gray-400">Carregando planos…</p>}

      {!loading && selectedStudent && plans.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-4xl mb-2">📋</p>
          <p>Nenhum plano ativo para este aluno.</p>
        </div>
      )}

      {plans.map(plan => (
        <PlanCard key={plan.id} plan={plan} onDeactivate={handleDeactivate} students={students} />
      ))}

      {/* Create plan modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Novo Plano de Treino</h2>
              <form onSubmit={handleCreatePlan} className="space-y-4">

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Aluno *</label>
                  <select
                    required
                    value={formStudent}
                    onChange={e => setFormStudent(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                  >
                    <option value="">Selecione…</option>
                    {students.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nome do plano *</label>
                  <input
                    required
                    type="text"
                    placeholder="ex: Treino A — Membros Inferiores"
                    value={planName}
                    onChange={e => setPlanName(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Dia da semana</label>
                  <select
                    value={dayOfWeek}
                    onChange={e => setDayOfWeek(Number(e.target.value))}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                  >
                    <option value={0}>Qualquer dia</option>
                    {DAY_LABELS.slice(1).map((d, i) => (
                      <option key={i + 1} value={i + 1}>{d}</option>
                    ))}
                  </select>
                </div>

                {/* Exercise items */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-700">Exercícios</label>
                    <button
                      type="button"
                      onClick={addItem}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      + adicionar exercício
                    </button>
                  </div>

                  <div className="space-y-3">
                    {items.map((item, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-xl p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-500">#{idx + 1}</span>
                          {items.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeItem(idx)}
                              className="text-xs text-red-500 hover:underline"
                            >
                              remover
                            </button>
                          )}
                        </div>

                        <select
                          value={item.exerciseType}
                          onChange={e => updateItem(idx, { exerciseType: e.target.value })}
                          className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm w-full"
                        >
                          {EXERCISES.map(ex => (
                            <option key={ex} value={ex}>{exerciseLabel[ex] ?? ex}</option>
                          ))}
                        </select>

                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="text-xs text-gray-500">Séries</label>
                            <input
                              type="number" min={1} max={10}
                              value={item.sets}
                              onChange={e => updateItem(idx, { sets: Number(e.target.value) })}
                              className="border border-gray-300 rounded-lg px-2 py-1 text-sm w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-gray-500">Reps</label>
                            <input
                              type="number" min={1} max={100}
                              value={item.repsPerSet}
                              onChange={e => updateItem(idx, { repsPerSet: Number(e.target.value) })}
                              className="border border-gray-300 rounded-lg px-2 py-1 text-sm w-full"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-gray-500">Carga (kg)</label>
                            <input
                              type="number" min={0} step={0.5}
                              placeholder="—"
                              value={item.loadKg ?? ''}
                              onChange={e => updateItem(idx, { loadKg: e.target.value ? Number(e.target.value) : null })}
                              className="border border-gray-300 rounded-lg px-2 py-1 text-sm w-full"
                            />
                          </div>
                        </div>

                        <input
                          type="text"
                          placeholder="Observações (opcional)"
                          value={item.notes}
                          onChange={e => updateItem(idx, { notes: e.target.value })}
                          className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm w-full"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 bg-gray-900 text-white text-sm py-2.5 rounded-lg hover:bg-gray-700
                               disabled:opacity-50 transition-colors"
                  >
                    {saving ? 'Salvando…' : 'Criar plano'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="flex-1 border border-gray-300 text-sm py-2.5 rounded-lg hover:bg-gray-50"
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCard({
  plan, onDeactivate, students,
}: { plan: WorkoutPlan; onDeactivate: (id: string) => void; students: Student[] }) {
  const student = students.find(s => s.id === plan.studentId);
  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-4 bg-gray-50 border-b border-gray-100">
        <div>
          <p className="font-semibold text-gray-900">{plan.name}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {student ? `${student.name} · ` : ''}
            {plan.dayOfWeek ? DAY_LABELS[plan.dayOfWeek] : 'Qualquer dia'}
          </p>
        </div>
        <button
          onClick={() => onDeactivate(plan.id)}
          className="text-xs text-red-400 hover:text-red-600 transition-colors"
        >
          Remover
        </button>
      </div>

      {/* Items */}
      <div className="divide-y divide-gray-100">
        {plan.items.map((item, idx) => (
          <div key={item.id ?? idx} className="flex items-center gap-4 px-5 py-3">
            <span className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center
                             text-xs font-bold text-gray-500 shrink-0">
              {idx + 1}
            </span>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">
                {exerciseLabel[item.exerciseType] ?? item.exerciseType}
              </p>
              {item.notes && (
                <p className="text-xs text-gray-400 mt-0.5">{item.notes}</p>
              )}
            </div>
            <div className="text-right text-xs text-gray-500 space-y-0.5">
              <p className="font-semibold text-gray-900">
                {item.sets}×{item.repsPerSet}
              </p>
              {item.loadKg != null && <p>{item.loadKg} kg</p>}
            </div>
          </div>
        ))}
        {plan.items.length === 0 && (
          <p className="text-sm text-gray-400 px-5 py-4">Nenhum exercício cadastrado.</p>
        )}
      </div>
    </div>
  );
}
