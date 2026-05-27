import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Records from './pages/Records';
import Upload from './pages/Upload';
import Batches from './pages/Batches';
import './index.css';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Overview' },
  { key: 'records', label: 'Records' },
  { key: 'upload', label: 'Ingest' },
  { key: 'batches', label: 'Batches' },
];

export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem('access_token'));
  const [page, setPage] = useState('dashboard');

  useEffect(() => {
    const handler = () => setAuthed(!!localStorage.getItem('access_token'));
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  const logout = () => {
    localStorage.clear();
    setAuthed(false);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar page={page} setPage={setPage} logout={logout} />
      <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
        {page === 'dashboard' && <Dashboard />}
        {page === 'records' && <Records />}
        {page === 'upload' && <Upload />}
        {page === 'batches' && <Batches />}
      </main>
    </div>
  );
}

function Sidebar({ page, setPage, logout }) {
  return (
    <nav style={{
      width: 200, background: 'var(--surface)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      padding: '0',
    }}>
      {/* Logo */}
      <div style={{
        padding: '24px 20px 20px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em' }}>
          BREATHE
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.15em', marginTop: 2 }}>
          ESG · ANALYST
        </div>
      </div>

      {/* Nav */}
      <div style={{ flex: 1, padding: '12px 0' }}>
        {NAV_ITEMS.map(item => (
          <button key={item.key} onClick={() => setPage(item.key)} style={{
            display: 'block', width: '100%', textAlign: 'left',
            padding: '10px 20px',
            background: page === item.key ? 'var(--accent-glow)' : 'transparent',
            color: page === item.key ? 'var(--accent)' : 'var(--text-muted)',
            border: 'none',
            borderLeft: `2px solid ${page === item.key ? 'var(--accent)' : 'transparent'}`,
            fontSize: 12, letterSpacing: '0.05em',
            transition: 'all 0.15s',
          }}>
            {item.label}
          </button>
        ))}
      </div>

      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
        <button onClick={logout} style={{
          width: '100%', padding: '8px 12px',
          background: 'transparent', color: 'var(--text-dim)',
          border: '1px solid var(--border2)', borderRadius: 'var(--radius)',
          fontSize: 11, letterSpacing: '0.05em',
        }}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
