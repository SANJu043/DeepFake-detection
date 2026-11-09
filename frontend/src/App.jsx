import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation, Link } from 'react-router-dom';
import {
  Upload, Shield, FileCheck, Search, Settings, LogOut,
  LayoutDashboard
} from 'lucide-react';
import { authAPI } from './api';
import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import DashboardPage from './pages/Dashboard';
import UploadPage from './pages/UploadPage';
import VerifyPage from './pages/Verify';
import AttestationsPage from './pages/Attestations';
import JobsPage from './pages/Jobs';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      authAPI.me()
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = (userData, tokens) => {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="spinner spinner-lg" />
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={
        user ? <Navigate to="/" /> : <LoginPage onLogin={handleLogin} />
      } />
      <Route path="/register" element={
        user ? <Navigate to="/" /> : <RegisterPage onLogin={handleLogin} />
      } />
      <Route path="/verify" element={<VerifyPage />} />

      {/* Protected routes */}
      <Route path="/*" element={
        user ? (
          <AppLayout user={user} onLogout={handleLogout}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/jobs" element={<JobsPage />} />
              <Route path="/attestations" element={<AttestationsPage />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </AppLayout>
        ) : <Navigate to="/login" />
      } />
    </Routes>
  );
}

function AppLayout({ user, onLogout, children }) {
  const location = useLocation();

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload Video' },
    { path: '/jobs', icon: Settings, label: 'Detection Jobs' },
    { path: '/attestations', icon: FileCheck, label: 'Attestations' },
    { path: '/verify', icon: Search, label: 'Verify' },
  ];

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Shield size={20} />
          </div>
          <h1>DeepAuth</h1>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              <item.icon size={20} />
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div style={{ padding: '8px 12px', marginBottom: '8px' }}>
            <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{user.display_name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{user.email}</div>
            <span className={`badge ${user.role === 'admin' ? 'badge-purple' : 'badge-blue'}`} style={{ marginTop: '6px' }}>
              {user.role}
            </span>
          </div>
          <button className="nav-item" onClick={onLogout}>
            <LogOut size={20} />
            Sign Out
          </button>
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

export default App;
