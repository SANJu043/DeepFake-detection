import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { authAPI } from '../api';

export default function RegisterPage({ onLogin }) {
  const [form, setForm] = useState({ email: '', display_name: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      await authAPI.register({
        email: form.email,
        display_name: form.display_name,
        password: form.password,
      });
      const { data: tokens } = await authAPI.login({ email: form.email, password: form.password });
      localStorage.setItem('access_token', tokens.access_token);
      const { data: user } = await authAPI.me();
      onLogin(user, tokens);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <div className="auth-page">
      <div className="auth-card fade-in">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          <div className="logo-icon" style={{ width: 48, height: 48, fontSize: '1.3rem' }}>
            <Shield size={24} />
          </div>
        </div>
        <h1>Create Account</h1>
        <p className="auth-subtitle">Join DeepAuth to start verifying videos</p>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
            borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: '16px',
            fontSize: '0.875rem', color: 'var(--accent-red)',
          }}>{error}</div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="reg-name">Display Name</label>
            <input id="reg-name" className="input" type="text" placeholder="John Doe"
              value={form.display_name} onChange={update('display_name')} required minLength={2} />
          </div>
          <div className="input-group">
            <label htmlFor="reg-email">Email</label>
            <input id="reg-email" className="input" type="email" placeholder="you@example.com"
              value={form.email} onChange={update('email')} required />
          </div>
          <div className="input-group">
            <label htmlFor="reg-password">Password</label>
            <input id="reg-password" className="input" type="password" placeholder="Min 8 characters"
              value={form.password} onChange={update('password')} required minLength={8} />
          </div>
          <div className="input-group">
            <label htmlFor="reg-confirm">Confirm Password</label>
            <input id="reg-confirm" className="input" type="password" placeholder="••••••••"
              value={form.confirm} onChange={update('confirm')} required />
          </div>

          <button className="btn btn-primary btn-lg" type="submit" disabled={loading} style={{ width: '100%', marginTop: '8px' }}>
            {loading ? <><div className="spinner" /> Creating account...</> : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
