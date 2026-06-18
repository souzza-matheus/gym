import React, { useState } from 'react';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { VideoTestPage } from './pages/VideoTestPage';
import { LoginPage } from './pages/LoginPage';
import { StudentProgressPage } from './pages/StudentProgressPage';
import { StudentsPage } from './pages/StudentsPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { WorkoutPlanPage } from './pages/WorkoutPlanPage';
import { AcademyPage } from './pages/AcademyPage';
import { useAuth } from './hooks/useAuth';

type Tab = 'alerts' | 'video-test' | 'progress' | 'students' | 'leaderboard' | 'plans' | 'academies';

export default function App() {
  const { isAuthenticated, user, login, logout, loading, error } = useAuth();
  const [tab, setTab] = useState<Tab>('alerts');

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} loading={loading} error={error} />;
  }

  return (
    <div>
      <nav className="bg-white border-b border-gray-200 px-4 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex gap-1">
            <TabButton label="Alertas"       active={tab === 'alerts'}      onClick={() => setTab('alerts')} />
            <TabButton label="Testar Vídeo"  active={tab === 'video-test'}  onClick={() => setTab('video-test')} />
            <TabButton label="Progresso"     active={tab === 'progress'}    onClick={() => setTab('progress')} />
            <TabButton label="Alunos"        active={tab === 'students'}    onClick={() => setTab('students')} />
            <TabButton label="Ranking 🏆"    active={tab === 'leaderboard'} onClick={() => setTab('leaderboard')} />
            <TabButton label="Planos 📋"     active={tab === 'plans'}       onClick={() => setTab('plans')} />
            {user?.role === 'ADMIN' && (
              <TabButton label="Academias 🏛️" active={tab === 'academies'}   onClick={() => setTab('academies')} />
            )}
          </div>
          <div className="flex items-center gap-3 py-2">
            <span className="text-xs text-gray-500 hidden sm:block">{user?.name ?? user?.email}</span>
            <button
              onClick={logout}
              className="text-xs text-gray-500 hover:text-gray-800 border border-gray-200
                         rounded-lg px-3 py-1.5 transition-colors"
            >
              Sair
            </button>
          </div>
        </div>
      </nav>
      {tab === 'alerts'       && <TeacherDashboard />}
      {tab === 'video-test'   && <VideoTestPage />}
      {tab === 'progress'     && <StudentProgressPage />}
      {tab === 'students'     && <StudentsPage />}
      {tab === 'leaderboard'  && <LeaderboardPage />}
      {tab === 'plans'        && <WorkoutPlanPage />}
      {tab === 'academies'    && <AcademyPage />}
    </div>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-4 py-3 border-b-2 font-medium transition-colors ${
        active ? 'border-gray-800 text-gray-900' : 'border-transparent text-gray-400 hover:text-gray-600'
      }`}
    >
      {label}
    </button>
  );
}
