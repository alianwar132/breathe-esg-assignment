import { useState, useEffect } from 'react';
import { getDashboard } from '../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const SCOPE_COLORS = { 1: '#ff6b35', 2: '#7eb8ff', 3: '#c97bff' };
const SOURCE_COLORS = { sap: '#2eff7a', utility: '#7eb8ff', travel: '#c97bff' };
const SOURCE_LABELS = { sap: 'SAP Fuel & Procurement', utility: 'Utility / Electricity', travel: 'Corporate Travel' };

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '20px 24px',
      borderTop: `2px solid ${accent || 'var(--border)'}`,
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 8 }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 700, color: accent || 'var(--text)', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboard().then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;
  if (!data) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Failed to load dashboard.</div>;

  const { totals, by_scope, by_source, by_category } = data;
  const totalCO2e = totals.total_co2e ? (totals.total_co2e / 1000).toFixed(1) : '—';

  const scopeData = by_scope.map(s => ({
    name: `Scope ${s.scope}`, value: parseFloat(s.co2e || 0), count: s.count
  }));

  const categoryData = by_category
    .map(c => ({ name: c.category?.replace('_', ' '), co2e: parseFloat(c.co2e || 0) }))
    .sort((a, b) => b.co2e - a.co2e);

  const reviewData = [
    { name: 'Pending', value: totals.pending, color: '#7eb8ff' },
    { name: 'Approved', value: totals.approved, color: '#2eff7a' },
    { name: 'Flagged', value: totals.flagged, color: '#ffaa2e' },
    { name: 'Rejected', value: totals.rejected, color: '#ff4d4d' },
  ].filter(d => d.value > 0);

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>
          Emissions Overview
        </h1>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Q1 2024 · Acme Manufacturing Ltd
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard label="TOTAL CO₂e" value={`${totalCO2e}t`} sub={`${totals.total_records} records`} accent="var(--accent)" />
        <StatCard label="PENDING REVIEW" value={totals.pending} sub="awaiting analyst" accent="var(--pending)" />
        <StatCard label="FLAGGED" value={totals.flagged + totals.suspicious} sub="needs attention" accent="var(--warn)" />
        <StatCard label="APPROVED" value={totals.approved} sub="locked for audit" accent="var(--approved)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
        {/* Scope breakdown */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 24 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 20 }}>
            CO₂e BY SCOPE
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={scopeData} barSize={40}>
              <XAxis dataKey="name" tick={{ fill: '#6b8f72', fontSize: 11, fontFamily: 'DM Mono' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b8f72', fontSize: 10, fontFamily: 'DM Mono' }} axisLine={false} tickLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}t`} />
              <Tooltip contentStyle={{ background: '#111a15', border: '1px solid #1e2e23', borderRadius: 4, fontSize: 12 }}
                formatter={v => [`${(v/1000).toFixed(2)}t CO₂e`]} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {scopeData.map((entry, i) => (
                  <Cell key={i} fill={SCOPE_COLORS[i + 1] || '#2eff7a'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
            {scopeData.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: SCOPE_COLORS[i + 1] }} />
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.name}: {(s.value/1000).toFixed(1)}t</span>
              </div>
            ))}
          </div>
        </div>

        {/* Review status pie */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 24 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 20 }}>
            REVIEW STATUS
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie data={reviewData} cx="50%" cy="50%" innerRadius={45} outerRadius={70}
                  dataKey="value" stroke="none">
                  {reviewData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1 }}>
              {reviewData.map((d, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: d.color }} />
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.name}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: d.color }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Category breakdown */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 24, marginBottom: 24 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 20 }}>
          EMISSIONS BY ACTIVITY CATEGORY
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={categoryData} layout="vertical" barSize={18}>
            <XAxis type="number" tick={{ fill: '#6b8f72', fontSize: 10 }} axisLine={false} tickLine={false}
              tickFormatter={v => `${(v/1000).toFixed(1)}t`} />
            <YAxis type="category" dataKey="name" tick={{ fill: '#6b8f72', fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
            <Tooltip contentStyle={{ background: '#111a15', border: '1px solid #1e2e23', borderRadius: 4, fontSize: 12 }}
              formatter={v => [`${(v/1000).toFixed(3)}t CO₂e`]} />
            <Bar dataKey="co2e" fill="var(--accent)" radius={[0, 3, 3, 0]} opacity={0.8} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Data source summary */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 24 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 16 }}>
          INGESTION SOURCES
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {by_source.map(s => (
            <div key={s.source_type} style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 6, padding: 16,
              borderLeft: `3px solid ${SOURCE_COLORS[s.source_type] || 'var(--accent)'}`,
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: 8 }}>
                {SOURCE_LABELS[s.source_type] || s.source_type}
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, color: SOURCE_COLORS[s.source_type] }}>
                {((parseFloat(s.co2e) || 0) / 1000).toFixed(2)}t
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{s.count} records</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 12, letterSpacing: '0.1em' }}>LOADING...</div>
    </div>
  );
}
