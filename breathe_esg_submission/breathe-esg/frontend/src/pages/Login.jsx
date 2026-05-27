import { useState } from 'react';
import { login } from '../api';

export default function Login({ onLogin }) {
  const [user, setUser] = useState('analyst');
  const [pass, setPass] = useState('breathe2024');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setErr('');
    try {
      const r = await login(user, pass);
      localStorage.setItem('access_token', r.data.access);
      localStorage.setItem('refresh_token', r.data.refresh);
      onLogin();
    } catch {
      setErr('Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)',
      backgroundImage: 'radial-gradient(ellipse 60% 40% at 50% 30%, rgba(46,255,122,0.04) 0%, transparent 60%)',
    }}>
      <div style={{ width: 360 }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 32, fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.03em' }}>
            BREATHE ESG
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.2em', marginTop: 6 }}>
            EMISSIONS INGESTION PLATFORM
          </div>
        </div>

        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 32,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 24, letterSpacing: '0.1em' }}>
            ANALYST LOGIN
          </div>
          <form onSubmit={submit}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, letterSpacing: '0.05em' }}>
                USERNAME
              </label>
              <input value={user} onChange={e => setUser(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px',
                  background: 'var(--bg)', border: '1px solid var(--border2)',
                  borderRadius: 'var(--radius)', color: 'var(--text)', fontSize: 13,
                  outline: 'none',
                }} />
            </div>
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, letterSpacing: '0.05em' }}>
                PASSWORD
              </label>
              <input type="password" value={pass} onChange={e => setPass(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px',
                  background: 'var(--bg)', border: '1px solid var(--border2)',
                  borderRadius: 'var(--radius)', color: 'var(--text)', fontSize: 13,
                  outline: 'none',
                }} />
            </div>
            {err && <div style={{ color: 'var(--danger)', fontSize: 12, marginBottom: 16 }}>{err}</div>}
            <button type="submit" disabled={loading} style={{
              width: '100%', padding: '11px',
              background: 'var(--accent)', color: '#0a0f0d',
              border: 'none', borderRadius: 'var(--radius)',
              fontSize: 12, fontWeight: 600, letterSpacing: '0.1em',
              opacity: loading ? 0.7 : 1,
            }}>
              {loading ? 'SIGNING IN...' : 'SIGN IN'}
            </button>
          </form>
          <div style={{ marginTop: 16, fontSize: 11, color: 'var(--text-dim)', textAlign: 'center' }}>
            analyst / breathe2024
          </div>
        </div>
      </div>
    </div>
  );
}
