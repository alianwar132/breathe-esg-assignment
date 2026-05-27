import { useState, useEffect, useCallback } from 'react';
import { getRecords, reviewRecord, getAuditTrail } from '../api';

const STATUS_COLORS = {
  pending: '#7eb8ff', approved: '#2eff7a', flagged: '#ffaa2e', rejected: '#ff4d4d'
};
const SCOPE_COLORS = { 1: '#ff6b35', 2: '#7eb8ff', 3: '#c97bff' };

function Badge({ text, color }) {
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px',
      background: `${color}18`, color, border: `1px solid ${color}30`,
      borderRadius: 3, fontSize: 10, fontWeight: 500, letterSpacing: '0.06em',
      textTransform: 'uppercase',
    }}>
      {text}
    </span>
  );
}

function FilterBar({ filters, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
      {[
        { key: 'review_status', label: 'Status', opts: ['', 'pending', 'approved', 'flagged', 'rejected'] },
        { key: 'scope', label: 'Scope', opts: ['', '1', '2', '3'] },
        { key: 'source_type', label: 'Source', opts: ['', 'sap', 'utility', 'travel'] },
        { key: 'category', label: 'Category', opts: ['', 'fuel', 'procurement', 'electricity', 'flight', 'hotel', 'ground_transport'] },
      ].map(f => (
        <select key={f.key} value={filters[f.key] || ''} onChange={e => onChange(f.key, e.target.value)}
          style={{
            padding: '7px 12px', background: 'var(--surface)',
            border: '1px solid var(--border2)', borderRadius: 'var(--radius)',
            color: filters[f.key] ? 'var(--text)' : 'var(--text-muted)',
            fontSize: 12,
          }}>
          {f.opts.map(o => <option key={o} value={o}>{o ? o.charAt(0).toUpperCase() + o.slice(1) : `All ${f.label}s`}</option>)}
        </select>
      ))}
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--warn)', cursor: 'pointer' }}>
        <input type="checkbox" checked={filters.flagged === 'true'} onChange={e => onChange('flagged', e.target.checked ? 'true' : '')} />
        Suspicious only
      </label>
    </div>
  );
}

function ReviewPanel({ record, onReviewed, onClose }) {
  const [action, setAction] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [auditLog, setAuditLog] = useState([]);

  useEffect(() => {
    getAuditTrail(record.id).then(r => setAuditLog(r.data)).catch(() => {});
    setNotes(record.review_notes || '');
  }, [record.id]);

  const submit = async () => {
    if (!action) return;
    setLoading(true);
    try {
      await reviewRecord(record.id, action, notes);
      onReviewed();
      onClose();
    } catch (e) {
      alert('Review failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const co2t = record.co2e_kg ? (record.co2e_kg / 1000).toFixed(4) : '—';

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        width: 640, maxHeight: '90vh', overflow: 'auto',
        background: 'var(--surface)', border: '1px solid var(--border2)',
        borderRadius: 8, padding: 28,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 16, marginBottom: 4 }}>
              Record Review
            </h3>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{record.id}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 18 }}>×</button>
        </div>

        {/* Record details */}
        <div style={{ background: 'var(--bg)', borderRadius: 6, padding: 16, marginBottom: 20 }}>
          <Grid2>
            <Field label="Category" value={record.category?.replace('_', ' ')} />
            <Field label="Scope" value={`Scope ${record.scope}`} accent={SCOPE_COLORS[record.scope]} />
            <Field label="Activity Date" value={record.activity_date} />
            <Field label="Source" value={record.batch_info?.source_type} />
            <Field label="CO₂e" value={`${co2t} t`} accent="var(--accent)" />
            <Field label="Calc Method" value={record.calculation_method || '—'} small />
          </Grid2>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <Grid2>
              <Field label="Raw Quantity" value={`${record.raw_quantity} ${record.raw_unit}`} />
              {record.quantity_kwh && <Field label="Normalised" value={`${parseFloat(record.quantity_kwh).toFixed(2)} kWh`} />}
              {record.quantity_litres && <Field label="Normalised" value={`${parseFloat(record.quantity_litres).toFixed(2)} L`} />}
              {record.quantity_km && <Field label="Normalised" value={`${parseFloat(record.quantity_km).toFixed(1)} km`} />}
              {record.quantity_nights && <Field label="Nights" value={record.quantity_nights} />}
            </Grid2>
          </div>
          {record.raw_description && (
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>{record.raw_description}</div>
          )}
        </div>

        {/* Suspicious flags */}
        {record.is_flagged_suspicious && (
          <div style={{
            background: 'var(--warn-dim)', border: '1px solid rgba(255,170,46,0.2)',
            borderRadius: 6, padding: 12, marginBottom: 20,
          }}>
            <div style={{ fontSize: 11, color: 'var(--warn)', letterSpacing: '0.08em', marginBottom: 6 }}>⚠ QUALITY FLAGS</div>
            {record.flag_reasons?.map((f, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--warn)' }}>· {f.replace(/_/g, ' ')}</div>
            ))}
          </div>
        )}

        {/* Extra metadata */}
        {Object.keys(record.extra || {}).length > 0 && (
          <details style={{ marginBottom: 20 }}>
            <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer', letterSpacing: '0.08em' }}>
              SOURCE METADATA
            </summary>
            <div style={{
              marginTop: 8, background: 'var(--bg)', borderRadius: 4,
              padding: 12, fontSize: 11, fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)', lineHeight: 1.8,
            }}>
              {Object.entries(record.extra).map(([k, v]) => (
                <div key={k}><span style={{ color: 'var(--accent-dim)' }}>{k}:</span> {String(v)}</div>
              ))}
            </div>
          </details>
        )}

        {/* Review action */}
        {record.review_status === 'pending' || record.review_status === 'flagged' ? (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 12 }}>
              REVIEW ACTION
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              {['approve', 'flag', 'reject'].map(a => (
                <button key={a} onClick={() => setAction(a)} style={{
                  flex: 1, padding: '9px 12px',
                  background: action === a ?
                    (a === 'approve' ? 'rgba(46,255,122,0.15)' : a === 'flag' ? 'var(--warn-dim)' : 'var(--danger-dim)')
                    : 'var(--bg)',
                  border: `1px solid ${action === a ?
                    (a === 'approve' ? 'var(--accent)' : a === 'flag' ? 'var(--warn)' : 'var(--danger)')
                    : 'var(--border2)'}`,
                  color: action === a ?
                    (a === 'approve' ? 'var(--accent)' : a === 'flag' ? 'var(--warn)' : 'var(--danger)')
                    : 'var(--text-muted)',
                  borderRadius: 'var(--radius)', fontSize: 11, letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                }}>
                  {a}
                </button>
              ))}
            </div>
            <textarea value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Review notes (optional)..."
              style={{
                width: '100%', height: 80, padding: 10,
                background: 'var(--bg)', border: '1px solid var(--border2)',
                borderRadius: 'var(--radius)', color: 'var(--text)', fontSize: 12, resize: 'vertical',
              }} />
            <button onClick={submit} disabled={!action || loading} style={{
              marginTop: 12, padding: '10px 24px',
              background: action === 'approve' ? 'var(--accent)' : action === 'flag' ? 'var(--warn)' : 'var(--danger)',
              color: '#0a0f0d', border: 'none', borderRadius: 'var(--radius)',
              fontSize: 12, fontWeight: 600, letterSpacing: '0.08em',
              opacity: (!action || loading) ? 0.5 : 1,
            }}>
              {loading ? 'SUBMITTING...' : `CONFIRM ${action.toUpperCase()}`}
            </button>
          </div>
        ) : (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16, fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>Status: </span>
            <Badge text={record.review_status} color={STATUS_COLORS[record.review_status]} />
            {record.review_notes && (
              <div style={{ marginTop: 8, color: 'var(--text-muted)' }}>{record.review_notes}</div>
            )}
          </div>
        )}

        {/* Audit trail */}
        {auditLog.length > 0 && (
          <div style={{ marginTop: 20, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 12 }}>
              AUDIT TRAIL
            </div>
            {auditLog.map(log => (
              <div key={log.id} style={{
                display: 'flex', gap: 12, marginBottom: 8,
                fontSize: 11, color: 'var(--text-muted)',
              }}>
                <span style={{ color: STATUS_COLORS[log.action] || 'var(--accent)' }}>{log.action.toUpperCase()}</span>
                <span>{log.performed_by_name}</span>
                <span>{new Date(log.performed_at).toLocaleString()}</span>
                {log.notes && <span>— {log.notes}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Grid2({ children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>{children}</div>;
}

function Field({ label, value, accent, small }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: small ? 10 : 13, color: accent || 'var(--text)', wordBreak: 'break-all' }}>{value || '—'}</div>
    </div>
  );
}

export default function Records() {
  const [records, setRecords] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    getRecords({ ...filters, page }).then(r => {
      setRecords(r.data.results || []);
      setCount(r.data.count || 0);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const updateFilter = (key, val) => {
    setFilters(f => ({ ...f, [key]: val || undefined }));
    setPage(1);
  };

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>
            Emissions Records
          </h1>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {count} records
          </div>
        </div>
      </div>

      <FilterBar filters={filters} onChange={updateFilter} />

      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 8, overflow: 'hidden',
      }}>
        {/* Table header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '90px 90px 100px 110px 100px 90px 80px 80px',
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)',
          fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.1em',
        }}>
          {['DATE', 'SOURCE', 'CATEGORY', 'CO₂e (kg)', 'SCOPE', 'STATUS', 'FLAGS', 'ACTION'].map(h => (
            <div key={h}>{h}</div>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>Loading...</div>
        ) : records.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>No records found.</div>
        ) : records.map((r, i) => (
          <div key={r.id} style={{
            display: 'grid',
            gridTemplateColumns: '90px 90px 100px 110px 100px 90px 80px 80px',
            padding: '11px 16px', alignItems: 'center',
            borderBottom: i < records.length - 1 ? '1px solid var(--border)' : 'none',
            background: r.is_flagged_suspicious ? 'rgba(255,170,46,0.03)' : 'transparent',
            transition: 'background 0.1s',
          }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.activity_date}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.source_type}</div>
            <div style={{ fontSize: 11, color: 'var(--text)' }}>{r.category?.replace('_', ' ')}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
              {r.co2e_kg ? parseFloat(r.co2e_kg).toFixed(1) : '—'}
            </div>
            <div>
              <Badge text={`S${r.scope}`} color={SCOPE_COLORS[r.scope] || 'var(--text-muted)'} />
            </div>
            <div>
              <Badge text={r.review_status} color={STATUS_COLORS[r.review_status]} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--warn)' }}>
              {r.is_flagged_suspicious ? '⚠' : ''}
            </div>
            <div>
              <button onClick={() => setSelected(r)} style={{
                padding: '4px 10px', background: 'transparent',
                border: '1px solid var(--border2)', borderRadius: 'var(--radius)',
                color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer',
              }}>
                Review
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Page {page}</span>
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
          style={{ padding: '6px 12px', background: 'var(--surface)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer' }}>
          ← Prev
        </button>
        <button onClick={() => setPage(p => p + 1)} disabled={records.length < 50}
          style={{ padding: '6px 12px', background: 'var(--surface)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer' }}>
          Next →
        </button>
      </div>

      {selected && (
        <ReviewPanel
          record={selected}
          onClose={() => setSelected(null)}
          onReviewed={load}
        />
      )}
    </div>
  );
}
