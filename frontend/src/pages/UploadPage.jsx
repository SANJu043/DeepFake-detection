import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, CheckCircle, XCircle, FileVideo } from 'lucide-react';
import { videosAPI } from '../api';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer?.files?.[0];
    if (f && f.type.startsWith('video/')) setFile(f);
  }, []);

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    setProgress(0);
    try {
      const { data } = await videosAPI.upload(file, (e) => {
        setProgress(Math.round((e.loaded / e.total) * 100));
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError('');
    setProgress(0);
  };

  return (
    <div>
      <div className="page-header fade-in">
        <h2>Upload Video</h2>
        <p>Upload a video for AI-powered deepfake detection and cryptographic attestation</p>
      </div>

      {result ? (
        <div className="card fade-in" style={{ textAlign: 'center', padding: '48px' }}>
          <CheckCircle size={56} style={{ color: 'var(--accent-green)', marginBottom: '16px' }} />
          <h3 style={{ marginBottom: '8px' }}>Upload Successful</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>{result.message}</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', maxWidth: '400px', margin: '0 auto 24px', textAlign: 'left' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Video ID</div>
              <div className="mono">{result.video_id?.slice(0, 12)}…</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Job ID</div>
              <div className="mono">{result.job_id?.slice(0, 12)}…</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>SHA-256</div>
              <div className="mono">{result.sha256?.slice(0, 16)}…</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Size</div>
              <div>{(result.size_bytes / 1024 / 1024).toFixed(2)} MB</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => navigate('/jobs')}>View Jobs</button>
            <button className="btn btn-secondary" onClick={reset}>Upload Another</button>
          </div>
        </div>
      ) : (
        <div className="fade-in fade-in-delay-1">
          <div
            className={`upload-zone ${dragging ? 'dragging' : ''}`}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onClick={() => document.getElementById('file-input').click()}
          >
            <input id="file-input" type="file" accept="video/*" hidden onChange={handleFileSelect} />
            <div className="upload-zone-content">
              <div className="upload-zone-icon">
                <Upload size={28} />
              </div>
              <div className="upload-zone-title">
                {file ? file.name : 'Drop video here or click to browse'}
              </div>
              <div className="upload-zone-subtitle">
                {file
                  ? `${(file.size / 1024 / 1024).toFixed(2)} MB • ${file.type}`
                  : 'Supports MP4, MOV, WebM • Max 200 MB'}
              </div>
            </div>
          </div>

          {error && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px',
              background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: 'var(--radius-sm)', padding: '12px 16px', color: 'var(--accent-red)', fontSize: '0.875rem',
            }}>
              <XCircle size={18} /> {error}
            </div>
          )}

          {uploading && (
            <div style={{ marginTop: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginBottom: '8px' }}>
                <span>Uploading...</span>
                <span>{progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {file && !uploading && (
            <div style={{ display: 'flex', gap: '12px', marginTop: '20px', justifyContent: 'center' }}>
              <button className="btn btn-primary btn-lg" onClick={handleUpload}>
                <FileVideo size={18} /> Analyze Video
              </button>
              <button className="btn btn-secondary btn-lg" onClick={reset}>Cancel</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
