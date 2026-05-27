import { useState, useEffect } from 'react';
import { getBatches } from '../api';

const STATUS_COLOR = { processing: '#7eb8ff', complete: '#2eff7a', failed: '#ff4d4d' };
const SOURCE_LABELS = { sap: 'SAP', utility: 'Utility', travel: 'Travel' };

export default function Batches() {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    getBatches().then(r => {
      setBatches(r.data.results || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>
          Ingestion Batches
        </h1>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Upload history and parse results
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading...</div>
      ) : batches.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No batches yet. Upload a file to get started.</div>
      ) : batches.map(batch => (
        <div key={batch.id} style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 8, marginBottom: 12, overflow: 'hidden',
        }}>
          <div
            onClick={() => setExpanded(expanded === batch.id ? null : batch.id)}
            style={{
              display: 'grid', gridTemplateColumns: '120px 100px 200px 80px 80px 80px 1fr',
              padding: '14px 20px', alignItems: 'center', cursor: 'pointer',
              gap: 12,
            }}>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>
              {new Date(batch.uploaded_at).toLocaleDateString()}
            </div>
            <div>
              <span style={{
                display: 'inline-block', padding: '2px 8px',
                background: `${STATUS_COLOR[batch.status]}18`, color: STATUS_COLOR[batch.status],
                border: `1px solid ${STATUS_COLOR[batch.status]}30`,
                borderRadius: 3, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase',
              }}>
                {batch.status}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {batch.original_filename}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {SOURCE_LABELS[batch.source_type] || batch.source_type}
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--accent)' }}>{batch.row_count}</span>
              <span style={{ color: 'var(--text-dim)' }}> rows</span>
            </div>
            <div style={{ fontSize: 12 }}>
              {batch.error_count > 0 ? (
                <span style={{ color: 'var(--warn)' }}>{batch.error_count} errors</span>
              ) : (
                <span style={{ color: 'var(--text-dim)' }}>clean</span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
              {batch.uploaded_by_name || 'system'} {expanded === batch.id ? '▲' : '▼'}
            </div>
          </div>

          {expanded === batch.id && batch.errors?.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', padding: '16px 20px', background: 'var(--bg)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 12 }}>PARSE ERRORS</div>
              {batch.errors.map(err => (
                <div key={err.id} style={{
                  display: 'flex', gap: 16, marginBottom: 6, fontSize: 12,
                  borderLeft: '2px solid var(--warn)', paddingLeft: 12,
                }}>
                  <span style={{ color: 'var(--text-dim)' }}>Row {err.row_number}</span>
                  <span style={{ color: 'var(--warn)' }}>[{err.field_name}]</span>
                  <span style={{ color: 'var(--text-muted)' }}>{err.error_message}</span>
                  {err.raw_value && <span style={{ color: 'var(--text-dim)' }}>raw: "{err.raw_value}"</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
