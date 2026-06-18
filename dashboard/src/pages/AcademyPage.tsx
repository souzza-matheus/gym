import React, { useEffect, useState } from 'react';
import { getStoredToken, getStoredUser } from '../hooks/useAuth';

interface Academy {
  id: string;
  name: string;
  address: string | null;
  plan: 'FREE' | 'BASIC' | 'PRO';
  active: boolean;
  inviteCode: string | null;
  createdAt: string;
}

interface AcademyStats {
  total_sessions: number;
  total_reps: number;
  total_alerts: number;
  active_students: number;
}

const PLAN_COLOR: Record<string, string> = {
  FREE:  'bg-gray-100 text-gray-600',
  BASIC: 'bg-blue-100 text-blue-700',
  PRO:   'bg-purple-100 text-purple-700',
};

export function AcademyPage() {
  const token   = getStoredToken();
  const user    = getStoredUser();
  const isAdmin = user?.role === 'ADMIN';
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const [academies, setAcademies] = useState<Academy[]>([]);
  const [stats, setStats]         = useState<Record<string, AcademyStats>>({});
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState({ name: '', address: '', plan: 'FREE' });
  const [saving, setSaving]       = useState(false);
  const [codeSearch, setCodeSearch] = useState('');
  const [codeResult, setCodeResult] = useState<Academy | null>(null);
  const [codeError, setCodeError]   = useState<string | null>(null);

  const fetchAcademies = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/academies', { headers });
      const body = await res.json();
      const list: Academy[] = body.data ?? [];
      setAcademies(list);
      // Load stats for each academy in parallel
      const statResults = await Promise.all(
        list.map(a =>
          fetch(`/api/v1/analytics/academy/${a.id}/stats?days=30`, { headers })
            .then(r => r.json())
            .then(b => ({ id: a.id, stats: b }))
            .catch(() => ({ id: a.id, stats: null }))
        )
      );
      const statsMap: Record<string, AcademyStats> = {};
      statResults.forEach(({ id, stats: s }) => {
        if (s) statsMap[id] = { ...s.totals, active_students: s.active_students ?? 0 };
      });
      setStats(statsMap);
    } catch {
      setError('Erro ao carregar academias.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAcademies(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch('/api/v1/academies', {
        method: 'POST', headers,
        body: JSON.stringify({ name: form.name, address: form.address || null, plan: form.plan }),
      });
      if (!res.ok) throw new Error(`Erro ${res.status}`);
      setShowForm(false);
      setForm({ name: '', address: '', plan: 'FREE' });
      await fetchAcademies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar academia.');
    } finally {
      setSaving(false);
    }
  };

  const searchByCode = async () => {
    if (!codeSearch.trim()) return;
    setCodeError(null);
    setCodeResult(null);
    try {
      const res = await fetch(`/api/v1/academies/code/${codeSearch.trim().toUpperCase()}`, { headers });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message ?? 'Código não encontrado.');
      setCodeResult(body.data);
    } catch (err) {
      setCodeError(err instanceof Error ? err.message : 'Erro.');
    }
  };

  // Non-admin: show only own academy
  if (!isAdmin) {
    const myAcademy = academies.find(a => a.id === user?.academyId) ?? null;
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Minha Academia 🏛️</h1>
        {loading && <p className="text-sm text-gray-400">Carregando…</p>}
        {myAcademy && <AcademyCard academy={myAcademy} stats={stats[myAcademy.id]} />}
        {!loading && !myAcademy && (
          <p className="text-sm text-gray-500">Você não está vinculado a nenhuma academia.</p>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Academias 🏛️</h1>
          <p className="text-sm text-gray-500 mt-1">{academies.length} academia(s) cadastrada(s)</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-gray-900 text-white text-sm px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
        >
          + Nova academia
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {error} <button className="ml-2 underline" onClick={() => setError(null)}>fechar</button>
        </div>
      )}

      {/* Code lookup */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
        <p className="text-sm font-medium text-gray-700 mb-2">Buscar academia por código de convite</p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="ex: GYMVIS8412"
            value={codeSearch}
            onChange={e => setCodeSearch(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && searchByCode()}
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm uppercase"
          />
          <button
            onClick={searchByCode}
            className="bg-gray-800 text-white px-4 py-2 text-sm rounded-lg hover:bg-gray-700"
          >
            Buscar
          </button>
        </div>
        {codeError && <p className="text-xs text-red-500 mt-1">{codeError}</p>}
        {codeResult && (
          <div className="mt-3 p-3 bg-white rounded-lg border border-gray-200 text-sm">
            <p className="font-semibold">{codeResult.name}</p>
            <p className="text-gray-500">{codeResult.address ?? '—'} · Plano {codeResult.plan}</p>
          </div>
        )}
      </div>

      {/* Academies list */}
      {loading && <p className="text-sm text-gray-400">Carregando academias…</p>}

      {!loading && academies.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-2">🏛️</p>
          <p>Nenhuma academia cadastrada.</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {academies.map(a => (
          <AcademyCard key={a.id} academy={a} stats={stats[a.id]} />
        ))}
      </div>

      {/* Create modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Nova Academia</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nome *</label>
                <input
                  required type="text"
                  placeholder="Academia XYZ"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Endereço</label>
                <input
                  type="text"
                  placeholder="Rua …"
                  value={form.address}
                  onChange={e => setForm({ ...form, address: e.target.value })}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plano</label>
                <select
                  value={form.plan}
                  onChange={e => setForm({ ...form, plan: e.target.value })}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"
                >
                  <option value="FREE">Free</option>
                  <option value="BASIC">Basic</option>
                  <option value="PRO">Pro</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit" disabled={saving}
                  className="flex-1 bg-gray-900 text-white text-sm py-2.5 rounded-lg hover:bg-gray-700 disabled:opacity-50"
                >
                  {saving ? 'Criando…' : 'Criar academia'}
                </button>
                <button
                  type="button" onClick={() => setShowForm(false)}
                  className="flex-1 border border-gray-300 text-sm py-2.5 rounded-lg hover:bg-gray-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function AcademyCard({ academy, stats }: { academy: Academy; stats?: AcademyStats }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    if (!academy.inviteCode) return;
    navigator.clipboard.writeText(academy.inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="font-semibold text-gray-900 text-lg leading-tight">{academy.name}</p>
            {academy.address && (
              <p className="text-xs text-gray-500 mt-0.5">{academy.address}</p>
            )}
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ml-2 shrink-0 ${PLAN_COLOR[academy.plan]}`}>
            {academy.plan}
          </span>
        </div>

        {/* Invite code */}
        {academy.inviteCode && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-gray-500">Código:</span>
            <code className="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-800">
              {academy.inviteCode}
            </code>
            <button
              onClick={copy}
              className="text-xs text-blue-600 hover:underline"
            >
              {copied ? 'Copiado!' : 'Copiar'}
            </button>
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="border-t border-gray-100 px-5 py-3 grid grid-cols-3 gap-2 bg-gray-50">
          <StatItem label="Sessões" value={stats.total_sessions ?? 0} />
          <StatItem label="Reps"    value={stats.total_reps ?? 0} />
          <StatItem label="Alunos ativos" value={stats.active_students ?? 0} />
        </div>
      )}
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className="text-base font-bold text-gray-900">{value.toLocaleString()}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
