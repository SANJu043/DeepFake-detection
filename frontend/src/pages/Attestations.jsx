import { useState, useEffect, useCallback } from 'react';
import {
  FileCheck,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Download,
  ShieldCheck,
  ShieldOff,
  AlertCircle,
  Hash,
  Key,
  GitBranch,
  Layers,
  Clock,
  BarChart2,
  Users,
} from 'lucide-react';
import { attestationsAPI } from '../api';

const VERDICT_BADGE = {
  NO_MANIPULATION_DETECTED: { cls: 'badge-green',  label: 'Clean'        },
  LIKELY_MANIPULATED:       { cls: 'badge-red',    label: 'Manipulated'  },
  INCONCLUSIVE:             { cls: 'badge-amber',  label: 'Inconclusive' },
};

function fmt(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString();
}

function truncHex(hex, chars = 24) {
  if (!hex) return '—';
  if (hex.length <= chars * 2) return hex;
  return `${hex.slice(0, chars)}…${hex.slice(-8)}`;
}

function InfoRow({ icon, label, children, mono }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '180px 1fr',
      gap: '12px',
      padding: '10px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      alignItems: 'start',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', color: 'var(--text-muted)', fontSize: '0.8125rem', paddingTop: 2 }}>
        {icon}{label}
      </div>
      <div className={mono ? 'mono' : ''} style={{ color: 'var(--text-primary)', fontSize: '0.875rem', wordBreak: 'break-all' }}>
        {children}
      </div>
    </div>
  );
}

function ExpandedAttestation({ att, onDownload, downloading }) {
  const vMap = VERDICT_BADGE[att.verdict] || { cls: 'badge-blue', label: att.verdict ?? '—' };

  let manifestFormatted = '—';
  try {
    manifestFormatted = JSON.stringify(
      typeof att.manifest === 'string' ? JSON.parse(att.manifest) : att.manifest,
      null,
      2
    );
  } catch { manifestFormatted = String(att.manifest ?? '—'); }

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary)', borderTop: '1px solid rgba(255,255,255,0.05)' }}>

      {/* Revocation Banner */}
      {att.is_revoked && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 'var(--radius-sm)', padding: '12px 16px', marginBottom: '20px',
          color: 'var(--accent-red)', fontWeight: 600,
        }}>
          <ShieldOff size={18} /> This attestation has been revoked and is no longer valid.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        {[
          { icon: <BarChart2 size={14} />, label: 'AI Score',         value: att.ai_score != null ? `${(att.ai_score * 100).toFixed(1)}%` : '—' },
          { icon: <Users     size={14} />, label: 'Face Count',       value: att.face_count ?? '—' },
          { icon: <Layers    size={14} />, label: 'Merkle Leaf Index', value: att.merkle_leaf_index ?? '—' },
          { icon: <Clock     size={14} />, label: 'Created',          value: fmt(att.created_at) },
        ].map(({ icon, label, value }) => (
          <div key={label} style={{
            background: 'var(--bg-card)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 14px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '4px' }}>
              {icon}{label}
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: '0.9375rem' }}>{String(value)}</div>
          </div>
        ))}
      </div>

      {/* Detail rows */}
      <div style={{ marginBottom: '20px' }}>
        <InfoRow icon={<Hash size={13} />}      label="Attestation ID"  mono>{att.attestation_id}</InfoRow>
        <InfoRow icon={<FileCheck size={13} />}  label="Video ID"        mono>{att.video_id}</InfoRow>
        <InfoRow icon={<BarChart2 size={13} />}  label="Verdict">
          <span className={`badge ${vMap.cls}`}>{vMap.label}</span>
        </InfoRow>
        <InfoRow icon={<GitBranch size={13} />}  label="Merkle Root"     mono>{att.merkle_root || '—'}</InfoRow>
        <InfoRow icon={<Key size={13} />}         label="Signature"       mono>{truncHex(att.signature)}</InfoRow>
        <InfoRow icon={<Key size={13} />}         label="Public Key" mono>
          <span style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', display: 'block' }}>
            {att.public_key_pem || '—'}
          </span>
        </InfoRow>
        {att.timestamp_token && (
          <InfoRow icon={<Clock size={13} />} label="Timestamp Token" mono>{truncHex(att.timestamp_token, 20)}</InfoRow>
        )}
        {att.model_versions?.length > 0 && (
          <InfoRow icon={<Layers size={13} />} label="Model Versions">
            {att.model_versions.map((m, i) => (
              <span key={i} className="badge badge-purple" style={{ marginRight: 4 }}>{m}</span>
            ))}
          </InfoRow>
        )}
      </div>

      {/* Manifest */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={13} /> Manifest
        </div>
        <pre className="mono" style={{
          background: 'var(--bg-secondary)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 'var(--radius-sm)',
          padding: '14px', fontSize: '0.75rem',
          overflowX: 'auto', color: 'var(--text-secondary)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          maxHeight: '280px', overflowY: 'auto',
        }}>
          {manifestFormatted}
        </pre>
      </div>

      {/* Download */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          className="btn btn-primary btn-sm"
          onClick={onDownload}
          disabled={downloading}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          {downloading
            ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Downloading…</>
            : <><Download size={14} /> Download Package</>}
        </button>
      </div>
    </div>
  );
}

export default function AttestationsPage() {
  const [attestations, setAttestations] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [error, setError]               = useState('');
  const [expanded, setExpanded]         = useState(null);
  const [downloading, setDownloading]   = useState({});

  const fetchAttestations = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const { data } = await attestationsAPI.list(0, 100);
      setAttestations(data.attestations ?? data ?? []);
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load attestations');
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAttestations(false); }, [fetchAttestations]);

  const toggle = (id) => setExpanded(prev => (prev === id ? null : id));

  const downloadPackage = async (att) => {
    setDownloading(prev => ({ ...prev, [att.id]: true }));
    try {
      const { data } = await attestationsAPI.package(att.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attestation-${att.attestation_id ?? att.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.response?.data?.detail || 'Download failed');
    } finally {
      setDownloading(prev => ({ ...prev, [att.id]: false }));
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
        <div className="spinner spinner-lg" />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header fade-in" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2>Attestations</h2>
          <p>Cryptographically signed records of deepfake analysis results</p>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => fetchAttestations(false)}
          disabled={refreshing}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={14} style={{ animation: refreshing ? 'spin 0.8s linear infinite' : 'none' }} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="fade-in" style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 'var(--radius-sm)', padding: '12px 16px',
          color: 'var(--accent-red)', fontSize: '0.875rem', marginBottom: '20px',
        }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <div className="card fade-in fade-in-delay-1" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-header">
          <span className="card-title">
            <FileCheck size={16} style={{ marginRight: 6, verticalAlign: -2 }} />
            All Attestations
          </span>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            {attestations.length} total
          </span>
        </div>

        {attestations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '56px 24px', color: 'var(--text-muted)' }}>
            <FileCheck size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p>No attestations yet. Complete a detection job to generate one.</p>
          </div>
        ) : (
          <div className="table-container" style={{ margin: 0, borderRadius: 0, border: 'none' }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }} />
                  <th>Attestation ID</th>
                  <th>Verdict</th>
                  <th>Score</th>
                  <th>Merkle Leaf</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th style={{ width: 32 }} />
                </tr>
              </thead>
              <tbody>
                {attestations.map(att => {
                  const isExpanded = expanded === att.id;
                  const vMap = VERDICT_BADGE[att.verdict] || { cls: 'badge-blue', label: att.verdict ?? '—' };

                  return (
                    <>
                      <tr
                        key={att.id}
                        onClick={() => toggle(att.id)}
                        style={{
                          cursor: 'pointer',
                          background: isExpanded ? 'rgba(59,130,246,0.06)' : undefined,
                          transition: 'background 0.15s',
                        }}
                      >
                        <td style={{ textAlign: 'center', paddingRight: 0 }}>
                          {isExpanded
                            ? <ChevronDown  size={14} style={{ color: 'var(--accent-blue)' }} />
                            : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
                        </td>
                        <td>
                          <span className="mono" style={{ fontSize: '0.8125rem' }}>
                            {(att.attestation_id ?? att.id).slice(0, 14)}…
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${vMap.cls}`}>{vMap.label}</span>
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                          {att.ai_score != null ? `${(att.ai_score * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                          {att.merkle_leaf_index ?? '—'}
                        </td>
                        <td>
                          {att.is_revoked ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--accent-red)', fontSize: '0.8125rem', fontWeight: 600 }}>
                              <ShieldOff size={13} /> Revoked
                            </span>
                          ) : (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--accent-green)', fontSize: '0.8125rem', fontWeight: 600 }}>
                              <ShieldCheck size={13} /> Valid
                            </span>
                          )}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                          {fmt(att.created_at)}
                        </td>
                        <td onClick={e => { e.stopPropagation(); downloadPackage(att); }} style={{ cursor: 'pointer' }}>
                          <Download size={14} style={{ color: 'var(--text-muted)', verticalAlign: -2 }} />
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr key={`${att.id}-detail`}>
                          <td colSpan={8} style={{ padding: 0, border: 'none' }}>
                            <ExpandedAttestation
                              att={att}
                              onDownload={() => downloadPackage(att)}
                              downloading={!!downloading[att.id]}
                            />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="fade-in fade-in-delay-2" style={{
        marginTop: '20px', padding: '14px 18px',
        background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)',
        borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem', color: 'var(--text-secondary)',
        display: 'flex', alignItems: 'flex-start', gap: '10px',
      }}>
        <ShieldCheck size={15} style={{ color: 'var(--accent-purple)', flexShrink: 0, marginTop: 1 }} />
        <span>
          Each attestation is cryptographically signed and anchored in a Merkle tree.
          The <strong style={{ color: 'var(--text-primary)' }}>Download Package</strong> button exports a verifiable JSON bundle
          containing the manifest, signature, public key, and Merkle proof — suitable for third-party verification.
        </span>
      </div>
    </div>
  );
}
