import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
  Users,
  BarChart2,
} from 'lucide-react';
import { jobsAPI } from '../api';

const STATUS_BADGE = {
  pending:   { cls: 'badge-amber',  label: 'Pending'   },
  running:   { cls: 'badge-blue',   label: 'Running'   },
  completed: { cls: 'badge-green',  label: 'Completed' },
  failed:    { cls: 'badge-red',    label: 'Failed'    },
};

const VERDICT_BADGE = {
  NO_MANIPULATION_DETECTED: { cls: 'badge-green',  label: 'Clean'         },
  LIKELY_MANIPULATED:       { cls: 'badge-red',    label: 'Manipulated'   },
  INCONCLUSIVE:             { cls: 'badge-amber',  label: 'Inconclusive'  },
};

function fmt(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString();
}

function elapsed(start, end) {
  if (!start) return null;
  const ms = new Date(end ?? Date.now()) - new Date(start);
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

function StatusIcon({ status }) {
  const size = 15;
  if (status === 'completed') return <CheckCircle2 size={size} style={{ color: 'var(--accent-green)' }} />;
  if (status === 'failed')    return <XCircle      size={size} style={{ color: 'var(--accent-red)'   }} />;
  if (status === 'running')   return <Loader2      size={size} style={{ color: 'var(--accent-blue)', animation: 'spin 1.2s linear infinite' }} />;
  return <Clock size={size} style={{ color: 'var(--accent-amber)' }} />;
}

function ResultDetail({ summary }) {
  if (!summary) return <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No result summary available.</p>;

  const verdict = summary.verdict;
  const vMap = VERDICT_BADGE[verdict] || { cls: 'badge-blue', label: verdict ?? '—' };

  const rows = [
    { icon: <BarChart2 size={14} />, label: 'AI Score',    value: summary.score != null ? `${(summary.score * 100).toFixed(1)}%` : '—' },
    { icon: <Users     size={14} />, label: 'Face Count',  value: summary.face_count ?? '—' },
    { icon: <Activity  size={14} />, label: 'Frames Analysed', value: summary.frames_analyzed ?? '—' },
    { icon: <Clock     size={14} />, label: 'Model',       value: summary.model ?? '—' },
  ];

  return (
    <div style={{ padding: '20px 24px', background: 'var(--bg-primary)', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Verdict</span>
        <span className={`badge ${vMap.cls}`}>{vMap.label}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
        {rows.map(({ icon, label, value }) => (
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

      {summary.extra && (
        <details style={{ marginTop: '14px' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8125rem', userSelect: 'none' }}>Raw summary JSON</summary>
          <pre className="mono" style={{
            marginTop: '8px', background: 'var(--bg-secondary)',
            border: '1px solid rgba(255,255,255,0.06)', borderRadius: 'var(--radius-sm)',
            padding: '12px', fontSize: '0.75rem', overflowX: 'auto',
            color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {JSON.stringify(summary, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState('');
  const [expanded, setExpanded]   = useState(null);
  const pollRef = useRef(null);

  const fetchJobs = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const { data } = await jobsAPI.list(0, 100);
      setJobs(data.jobs ?? data ?? []);
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load jobs');
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => { fetchJobs(false); }, [fetchJobs]);

  // Auto-poll while any job is pending/running
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'running');
    if (hasActive) {
      pollRef.current = setInterval(() => fetchJobs(true), 5000);
    }
    return () => clearInterval(pollRef.current);
  }, [jobs, fetchJobs]);

  const toggle = (id) => setExpanded(prev => (prev === id ? null : id));

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
          <h2>Detection Jobs</h2>
          <p>AI analysis jobs for your uploaded videos</p>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => fetchJobs(false)}
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
            <Activity size={16} style={{ marginRight: 6, verticalAlign: -2 }} />
            All Jobs
          </span>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            {jobs.length} total
          </span>
        </div>

        {jobs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '56px 24px', color: 'var(--text-muted)' }}>
            <Activity size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p>No detection jobs yet. Upload a video to start analysis.</p>
          </div>
        ) : (
          <div className="table-container" style={{ margin: 0, borderRadius: 0, border: 'none' }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }} />
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Verdict</th>
                  <th>Duration</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => {
                  const isExpanded = expanded === job.id;
                  const sb = STATUS_BADGE[job.status] || { cls: 'badge-blue', label: job.status };
                  const verdict = job.result_summary?.verdict;
                  const vb = verdict ? (VERDICT_BADGE[verdict] || { cls: 'badge-blue', label: verdict }) : null;
                  const isClickable = job.status === 'completed' || job.status === 'failed';

                  return (
                    <>
                      <tr
                        key={job.id}
                        onClick={() => isClickable && toggle(job.id)}
                        style={{
                          cursor: isClickable ? 'pointer' : 'default',
                          background: isExpanded ? 'rgba(59,130,246,0.06)' : undefined,
                          transition: 'background 0.15s',
                        }}
                      >
                        <td style={{ textAlign: 'center', paddingRight: 0 }}>
                          {isClickable
                            ? (isExpanded
                                ? <ChevronDown size={14} style={{ color: 'var(--accent-blue)' }} />
                                : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />)
                            : <StatusIcon status={job.status} />}
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {isClickable && <StatusIcon status={job.status} />}
                            <span className="mono" style={{ fontSize: '0.8125rem' }}>
                              {job.id.slice(0, 8)}…
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${sb.cls}`}>{sb.label}</span>
                        </td>
                        <td>
                          {vb
                            ? <span className={`badge ${vb.cls}`}>{vb.label}</span>
                            : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                          {job.started_at
                            ? elapsed(job.started_at, job.completed_at)
                            : '—'}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                          {fmt(job.created_at)}
                        </td>
                      </tr>

                      {/* Expanded detail row */}
                      {isExpanded && (
                        <tr key={`${job.id}-detail`}>
                          <td colSpan={6} style={{ padding: 0, border: 'none' }}>
                            {job.status === 'failed' ? (
                              <div style={{
                                padding: '16px 24px', background: 'var(--bg-primary)',
                                borderTop: '1px solid rgba(255,255,255,0.05)',
                                display: 'flex', alignItems: 'flex-start', gap: '10px',
                              }}>
                                <XCircle size={16} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: 2 }} />
                                <div>
                                  <div style={{ color: 'var(--accent-red)', fontWeight: 600, marginBottom: '4px', fontSize: '0.875rem' }}>Error</div>
                                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                    {job.error_message || 'An unknown error occurred.'}
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <ResultDetail summary={job.result_summary} />
                            )}

                            {/* Timestamps footer */}
                            <div style={{
                              padding: '10px 24px',
                              background: 'rgba(0,0,0,0.2)',
                              borderTop: '1px solid rgba(255,255,255,0.04)',
                              display: 'flex', flexWrap: 'wrap', gap: '20px',
                              fontSize: '0.75rem', color: 'var(--text-muted)',
                            }}>
                              {[
                                ['Created',   job.created_at],
                                ['Started',   job.started_at],
                                ['Completed', job.completed_at],
                              ].map(([label, ts]) => (
                                <span key={label}>
                                  <strong style={{ color: 'var(--text-secondary)' }}>{label}:</strong> {fmt(ts)}
                                </span>
                              ))}
                              <span className="mono" style={{ marginLeft: 'auto', opacity: 0.5 }}>{job.id}</span>
                            </div>
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

      {jobs.some(j => j.status === 'pending' || j.status === 'running') && (
        <div className="fade-in" style={{
          marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px',
          color: 'var(--accent-blue)', fontSize: '0.8125rem',
        }}>
          <Loader2 size={14} style={{ animation: 'spin 1.2s linear infinite' }} />
          Auto-refreshing every 5 seconds while jobs are active…
        </div>
      )}
    </div>
  );
}
