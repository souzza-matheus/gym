import React, { useEffect, useState } from 'react';
import { getStoredToken } from '../hooks/useAuth';

interface Student {
  id:       string;
  name:     string;
  email:    string;
  role:     string;
  academyId: string | null;
}

export function StudentsPage() {
  const [students, setStudents]   = useState<Student[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [search, setSearch]       = useState('');
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState({ name: '', email: '', password: '' });
  const [saving, setSaving]       = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const token = getStoredToken();

  const fetchStudents = () => {
    setLoading(true);
    fetch('/api/v1/users?role=STUDENT', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(body => setStudents(body.data ?? body ?? []))
      .catch(() => setError('Erro ao carregar alunos.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchStudents(); }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch('/api/v1/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ...form, role: 'STUDENT' }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.message ?? `Erro ${res.status}`);
      setShowForm(false);
      setForm({ name: '', email: '', password: '' });
      fetchStudents();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erro ao cadastrar.');
    } finally {
      setSaving(false);
    }
  };

  const filtered = students.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto space-y-4">

        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Alunos</h2>
          <button
            onClick={() => setShowForm(v => !v)}
            className="bg-gray-800 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
          >
            {showForm ? 'Cancelar' : '+ Novo aluno'}
          </button>
        </div>

        {/* Formulário de cadastro */}
        {showForm && (
          <div className="bg-white rounded-xl shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Cadastrar novo aluno</h3>
            <form onSubmit={handleRegister} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Nome</label>
                  <input
                    type="text" required value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-800"
                    placeholder="João Silva"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">E-mail</label>
                  <input
                    type="email" required value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-800"
                    placeholder="joao@email.com"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Senha inicial</label>
                  <input
                    type="password" required minLength={6} value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-800"
                    placeholder="mínimo 6 caracteres"
                  />
                </div>
              </div>
              {saveError && <p className="text-sm text-red-600">{saveError}</p>}
              <button
                type="submit" disabled={saving}
                className="bg-gray-800 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-40 hover:bg-gray-700"
              >
                {saving ? 'Cadastrando…' : 'Cadastrar aluno'}
              </button>
            </form>
          </div>
        )}

        {/* Busca */}
        <input
          type="search" value={search} placeholder="Buscar por nome ou e-mail…"
          onChange={e => setSearch(e.target.value)}
          className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-800"
        />

        {/* Lista */}
        {loading && <p className="text-sm text-gray-500 text-center py-8">Carregando…</p>}
        {error   && <p className="text-sm text-red-600 text-center py-4">{error}</p>}
        {!loading && !error && (
          <div className="space-y-2">
            {filtered.length === 0 ? (
              <div className="bg-white rounded-xl p-8 text-center text-gray-400 shadow-sm">
                <p className="text-sm">{search ? 'Nenhum aluno encontrado.' : 'Nenhum aluno cadastrado ainda.'}</p>
              </div>
            ) : filtered.map(s => (
              <div key={s.id} className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 font-bold text-sm flex-shrink-0">
                  {s.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{s.name}</p>
                  <p className="text-xs text-gray-400 truncate">{s.email}</p>
                </div>
                <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full font-medium flex-shrink-0">
                  Aluno
                </span>
              </div>
            ))}
            <p className="text-xs text-gray-400 text-center pt-2">
              {filtered.length} aluno{filtered.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
