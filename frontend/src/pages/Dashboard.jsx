import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileCheck, Activity, Shield, ArrowRight } from 'lucide-react';
import { videosAPI, jobsAPI, attestationsAPI } from '../api';

export default function DashboardPage() {
  const [stats, setStats] = useState({ videos: 0, jobs: 0, attestations: 0 });
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      videosAPI.list(0, 1).catch(() => ({ data: { total: 0 } })),
      jobsAPI.list(0, 5).catch(() => ({ data: { total: 0, jobs: [] } })),
      attestationsAPI.list(0, 1).catch(() => ({ data: { total: 0 } })),
    ]).then(([vRes, jRes, aRes]) => {
      setStats({
        videos: vRes.data.total,
        jobs: jRes.data.total,
        attestations: aRes.data.total,
      });
      setRecentJobs(jRes.data.jobs || []);
    }).finally(() => setLoading(false));
  }, []);

  const verdictBadge = (verdict) => {
    if (!verdict) return null;
    const map = {
      'NO_MANIPULATION_DETECTED': { cls: 'badge-green', label: 'Clean' },
      'LIKELY_MANIPULATED': { cls: 'badge-red', label: 'Manipulated' },
      'INCONCLUSIVE': { cls: 'badge-amber', label: 'Inconclusive' },
    };
    const v = map[verdict] || { cls: 'badge-blue', label: verdict };
    return <span className={`badge ${v.cls}`}>{v.label}</span>;
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
      <div className="page-header fade-in">
        <h2>Dashboard</h2>
        <p>Deepfake detection and cryptographic verification overview</p>
      </div>

      {/* Stats */}
      <div className="stats-grid fade-in fade-in-delay-1">
        <div className="stat-card" onClick={() => navigate('/upload')} style={{ cursor: 'pointer' }}>
          <div className="stat-label"><Upload size={14} style={{ marginRight: 6, verticalAlign: -2 }} />Videos Uploaded</div>
          <div className="stat-value blue">{stats.videos}</div>
        </div>
        <div className="stat-card" onClick={() => navigate('/jobs')} style={{ cursor: 'pointer' }}>
          <div className="stat-label"><Activity size={14} style={{ marginRight: 6, verticalAlign: -2 }} />Detection Jobs</div>
          <div className="stat-value amber">{stats.jobs}</div>
        </div>
        <div className="stat-card" onClick={() => navigate('/attestations')} style={{ cursor: 'pointer' }}>
          <div className="stat-label"><FileCheck size={14} style={{ marginRight: 6, verticalAlign: -2 }} />Attestations</div>
          <div className="stat-value green">{stats.attestations}</div>
        </div>
        <div className="stat-card" onClick={() => navigate('/verify')} style={{ cursor: 'pointer' }}>
          <div className="stat-label"><Shield size={14} style={{ marginRight: 6, verticalAlign: -2 }} />Verify</div>
          <div className="stat-value" style={{ color: 'var(--accent-purple)', fontSize: '1rem', paddingTop: '8px' }}>
            Public Endpoint <ArrowRight size={16} style={{ verticalAlign: -3 }} />
          </div>
        </div>
      </div>

      {/* Recent Jobs */}
      <div className="card fade-in fade-in-delay-2">
        <div className="card-header">
          <span className="card-title">Recent Detection Jobs</span>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/jobs')}>
            View All <ArrowRight size={14} />
          </button>
        </div>

        {recentJobs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            <Upload size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
            <p>No jobs yet. Upload a video to get started.</p>
            <button className="btn btn-primary" onClick={() => navigate('/upload')} style={{ marginTop: 16 }}>
              Upload Video
            </button>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Verdict</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map(job => (
                  <tr key={job.id}>
                    <td className="mono">{job.id.slice(0, 8)}…</td>
                    <td>
                      <span className={`badge ${
                        job.status === 'completed' ? 'badge-green' :
                        job.status === 'failed' ? 'badge-red' :
                        job.status === 'running' ? 'badge-blue' : 'badge-amber'
                      }`}>{job.status}</span>
                    </td>
                    <td>{job.result_summary ? verdictBadge(job.result_summary.verdict) : '—'}</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Honesty Reminder */}
      <div className="verdict-reminder fade-in fade-in-delay-3" style={{ marginTop: '24px' }}>
        <strong>⚠️ Important:</strong> Cryptography proves <em>who vouched for what, when</em>, and that <em>nothing changed since</em>.
        The AI gives a <em>probabilistic opinion</em>. Together they provide verified provenance plus an AI assessment — <strong>not absolute truth</strong>.
      </div>
    </div>
  );
}
