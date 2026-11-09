import { useState } from 'react';
import { Search, CheckCircle, XCircle, MinusCircle, AlertTriangle, Shield } from 'lucide-react';
import { verifyAPI } from '../api';

const statusIcons = {
  pass: <CheckCircle size={16} />,
  fail: <XCircle size={16} />,
  skip: <MinusCircle size={16} />,
  warn: <AlertTriangle size={16} />,
};

export default function VerifyPage() {
  const [attestationId, setAttestationId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!attestationId.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const { data } = await verifyAPI.byId(attestationId.trim());
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const verdictInfo = (verdict) => {
    const map = {
      'NO_MANIPULATION_DETECTED': { cls: 'clean', label: 'No Manipulation Detected', color: 'var(--accent-green)' },
      'LIKELY_MANIPULATED': { cls: 'manipulated', label: 'Likely Manipulated', color: 'var(--accent-red)' },
      'INCONCLUSIVE': { cls: 'inconclusive', label: 'Inconclusive', color: 'var(--accent-amber)' },
    };
    return map[verdict] || { cls: 'inconclusive', label: verdict, color: 'var(--text-secondary)' };
  };

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '40px 20px' }}>
      <div className="page-header fade-in" style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
          <div className="logo-icon" style={{ width: 56, height: 56 }}>
            <Shield size={28} />
          </div>
        </div>
        <h2>Verify Attestation</h2>
        <p>Enter an attestation ID to independently verify its cryptographic integrity</p>
      </div>

      <form onSubmit={handleVerify} className="fade-in fade-in-delay-1" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <input
            id="verify-attestation-id"
            className="input"
            type="text"
            placeholder="Enter attestation ID (UUID)"
            value={attestationId}
            onChange={e => setAttestationId(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? <div className="spinner" /> : <><Search size={16} /> Verify</>}
          </button>
        </div>
      </form>

      {error && (
        <div className="fade-in" style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
          borderRadius: 'var(--radius-sm)', padding: '12px 16px', color: 'var(--accent-red)',
          fontSize: '0.875rem', marginBottom: '24px',
        }}>
          <XCircle size={18} /> {error}
        </div>
      )}

      {result && (
        <div className="fade-in">
          {/* Verdict */}
          {result.ai_verdict && (
            <div className={`verdict-display ${verdictInfo(result.ai_verdict).cls}`}>
              <div className="verdict-label" style={{ color: verdictInfo(result.ai_verdict).color }}>
                {verdictInfo(result.ai_verdict).label}
              </div>
              {result.ai_score != null && (
                <div className="verdict-score" style={{ color: verdictInfo(result.ai_verdict).color }}>
                  {(result.ai_score * 100).toFixed(2)}%
                </div>
              )}
            </div>
          )}

          {/* Checks */}
          <div className="card" style={{ marginBottom: '16px' }}>
            <div className="card-header">
              <span className="card-title">Verification Checks</span>
              <span className={`badge ${result.all_passed ? 'badge-green' : 'badge-red'}`}>
                {result.all_passed ? 'All Passed' : 'Issues Found'}
              </span>
            </div>
            <div className="check-list">
              {result.checks?.map((check, i) => (
                <div key={i} className="check-item">
                  <div className={`check-icon ${check.status}`}>
                    {statusIcons[check.status] || statusIcons.skip}
                  </div>
                  <div>
                    <div className="check-name">{check.name.replace(/_/g, ' ')}</div>
                    {check.detail && <div className="check-detail">{check.detail}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reminder */}
          <div className="verdict-reminder">
            {result.reminder}
          </div>
        </div>
      )}
    </div>
  );
}
