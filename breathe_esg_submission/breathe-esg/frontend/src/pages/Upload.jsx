import { useState, useRef } from 'react';
import { uploadFile } from '../api';

const SOURCE_INFO = {
  sap: {
    label: 'SAP Fuel & Procurement',
    description: 'SAP ALV Grid export (tab-separated .txt or .csv). Handles Belegdatum/Document Date, Werk, Material, Menge, Mengeneinheit. Resolves German/English mixed headers automatically.',
    scope: 'Scope 1 (fuel) / Scope 3 (procurement)',
    example: 'acme_sap_export_q1_2024.txt',
    color: '#2eff7a',
  },
  utility: {
    label: 'Utility / Electricity',
    description: 'Portal CSV export. Handles Account Reference, Meter Serial Number, Read Date, Consumption (kWh), Read Type (Actual/Estimated). Supports kWh, MWh, GWh, therms.',
    scope: 'Scope 2',
    example: 'electricity_q1_2024.csv',
    color: '#7eb8ff',
  },
  travel: {
    label: 'Corporate Travel (Concur)',
    description: 'Concur Travel export CSV. Handles Flight/Hotel/Car/Rail. Computes flight distances via IATA airport lookup + Haversine + 9% uplift when not provided.',
    scope: 'Scope 3',
    example: 'concur_travel_export_q1_2024.csv',
    color: '#c97bff',
  },
};

export default function Upload() {
  const [sourceType, setSourceType] = useState('sap');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const inputRef = useRef();

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const submit = async () => {
    if (!file) { setError('Select a file first.'); return; }
    setLoading(true); setError(''); setResult(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('source_type', sourceType);
    try {
      const r = await uploadFile(fd);
      setResult(r.data);
      setFile(null);
    } catch (e) {
      setError(e.response?.data?.error || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const info = SOURCE_INFO[sourceType];

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>
          Ingest Data
        </h1>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          Upload source files for normalisation and review
        </div>
      </div>

      {/* Source type selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
        {Object.entries(SOURCE_INFO).map(([key, s]) => (
          <button key={key} onClick={() => setSourceType(key)} style={{
            padding: '16px 20px', textAlign: 'left',
            background: sourceType === key ? `${s.color}10` : 'var(--surface)',
            border: `1px solid ${sourceType === key ? s.color : 'var(--border)'}`,
            borderRadius: 8, cursor: 'pointer',
            transition: 'all 0.15s',
          }}>
            <div style={{ fontSize: 10, color: s.color, letterSpacing: '0.1em', marginBottom: 6 }}>
              {s.scope}
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 600, color: sourceType === key ? s.color : 'var(--text)', marginBottom: 4 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {s.description}
            </div>
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
        style={{
          border: `2px dashed ${file ? info.color : 'var(--border2)'}`,
          borderRadius: 8, padding: '48px 32px', textAlign: 'center',
          cursor: 'pointer', marginBottom: 24,
          background: file ? `${info.color}06` : 'transparent',
          transition: 'all 0.2s',
        }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>
          {file ? '📄' : '⬆'}
        </div>
        {file ? (
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: info.color, marginBottom: 4 }}>{file.name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{(file.size / 1024).toFixed(1)} KB</div>
          </div>
        ) : (
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--text)', marginBottom: 4 }}>
              Drop file here or click to browse
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Expected: {info.example}
            </div>
          </div>
        )}
        <input ref={inputRef} type="file" accept=".csv,.txt,.tsv" style={{ display: 'none' }}
          onChange={e => setFile(e.target.files[0])} />
      </div>

      {error && (
        <div style={{
          background: 'var(--danger-dim)', border: '1px solid rgba(255,77,77,0.2)',
          borderRadius: 6, padding: 12, marginBottom: 16, color: 'var(--danger)', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{
          background: 'rgba(46,255,122,0.07)', border: '1px solid rgba(46,255,122,0.2)',
          borderRadius: 6, padding: 16, marginBottom: 16,
        }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--accent)', marginBottom: 8 }}>
            ✓ Ingestion complete
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 2 }}>
            <div>Rows created: <strong style={{ color: 'var(--text)' }}>{result.rows_created}</strong></div>
            <div>Parse errors: <strong style={{ color: result.errors?.length > 0 ? 'var(--warn)' : 'var(--text)' }}>{result.errors?.length || 0}</strong></div>
            <div>Batch ID: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{result.batch_id}</span></div>
          </div>
          {result.errors?.length > 0 && (
            <details style={{ marginTop: 12 }}>
              <summary style={{ fontSize: 11, color: 'var(--warn)', cursor: 'pointer' }}>View parse errors</summary>
              <div style={{ marginTop: 8, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                {result.errors.map((e, i) => (
                  <div key={i} style={{ color: 'var(--warn)', marginBottom: 4 }}>
                    Row {e._row}: [{e._field}] {e._msg}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      <button onClick={submit} disabled={!file || loading} style={{
        padding: '12px 32px',
        background: file ? info.color : 'var(--surface)',
        color: '#0a0f0d',
        border: 'none', borderRadius: 'var(--radius)',
        fontSize: 13, fontWeight: 600, letterSpacing: '0.08em',
        opacity: (!file || loading) ? 0.5 : 1,
        cursor: file && !loading ? 'pointer' : 'not-allowed',
      }}>
        {loading ? 'PROCESSING...' : 'INGEST FILE'}
      </button>
    </div>
  );
}
