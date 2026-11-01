import React, { useState } from 'react';
import advisorImg from '../assets/advisoradvising.png';
import { loginUser } from '../api/auth';

export default function SignInPage({ onNavigate, user, onLoginSuccess, onLogout }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // If already logged in, show logged-in prompt
  if (user) {
    return (
      <div className="page-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          padding: '40px',
          maxWidth: '480px',
          width: '100%',
          textAlign: 'center',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
        }}>
          <h2 style={{ color: '#1e4634', marginBottom: '12px' }}>Already Signed In</h2>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            You are currently logged in as <strong>{user.name}</strong> ({user.email}).
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button
              onClick={() => onNavigate('dashboard')}
              className="btn-primary-pill"
            >
              Go to Dashboard
            </button>
            <button
              onClick={onLogout}
              className="nav-link"
              style={{ color: '#dc2626' }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please fill in both email and password.');
      return;
    }

    setErrorMessage('');
    setLoading(true);

    const res = await loginUser(email, password);
    setLoading(false);

    if (res.success) {
      setSuccessMessage('Successfully signed in! Opening your advisor dashboard...');
      if (onLoginSuccess && res.data && res.data.advisor) {
        onLoginSuccess(res.data.advisor);
      }
      setTimeout(() => {
        onNavigate('dashboard');
      }, 900);
    } else {
      setErrorMessage(res.error || 'Failed to sign in. Please verify your credentials.');
    }
  };

  return (
    <div className="page-container" style={{ paddingBottom: '40px' }}>
      {/* Header Logo */}
      <header style={{
        maxWidth: '1240px',
        width: '100%',
        margin: '0 auto',
        padding: '8px 0 24px 0',
      }}>
        <div 
          className="logo" 
          onClick={() => onNavigate('landing')}
          role="button"
          tabIndex={0}
        >
          GradPath
        </div>
      </header>

      {/* Main Two-Column Content */}
      <main style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        maxWidth: '1240px',
        width: '100%',
        margin: '0 auto',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '56px',
          alignItems: 'center',
          width: '100%',
        }}>
          {/* Left Column: Sign In Form */}
          <div style={{ maxWidth: '440px' }}>
            <h1 style={{
              fontSize: '36px',
              fontWeight: 800,
              color: '#111827',
              marginBottom: '8px',
              letterSpacing: '-0.5px',
            }}>
              Sign In
            </h1>

            <p style={{
              fontSize: '15px',
              color: '#6b7280',
              marginBottom: '32px',
            }}>
              Don't have an account?{' '}
              <span
                onClick={() => onNavigate('register')}
                style={{
                  color: '#1e4634',
                  fontWeight: 600,
                  textDecoration: 'underline',
                  cursor: 'pointer',
                }}
              >
                Create now
              </span>
            </p>

            {errorMessage && (
              <div className="alert-box alert-error">
                {errorMessage}
              </div>
            )}

            {successMessage && (
              <div className="alert-box alert-success">
                {successMessage}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {/* Email Field */}
              <div className="form-group">
                <label className="form-label" htmlFor="email-input">
                  E-mail
                </label>
                <input
                  id="email-input"
                  type="email"
                  className="form-input"
                  placeholder="example@gmail.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>

              {/* Password Field */}
              <div className="form-group">
                <label className="form-label" htmlFor="password-input">
                  Password
                </label>
                <div className="input-wrapper">
                  <input
                    id="password-input"
                    type={showPassword ? 'text' : 'password'}
                    className="form-input"
                    placeholder="@#*%"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    style={{ paddingRight: '48px' }}
                    required
                  />
                  <button
                    type="button"
                    className="input-icon-btn"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{ right: '12px' }}
                  >
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#9ca3af"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                      {showPassword && (
                        <line x1="3" y1="3" x2="21" y2="21" stroke="#4b5563" />
                      )}
                    </svg>
                  </button>
                </div>
              </div>

              {/* Remember me Checkbox */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                marginBottom: '28px',
                cursor: 'pointer',
              }}>
                <label style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '14.5px',
                  color: '#4b5563',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}>
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    style={{
                      width: '18px',
                      height: '18px',
                      accentColor: '#1e4634',
                      cursor: 'pointer',
                      borderRadius: '4px',
                    }}
                  />
                  Remember me
                </label>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="btn-primary-pill"
                style={{
                  width: '100%',
                  padding: '14px 24px',
                  fontSize: '16px',
                  fontWeight: 600,
                  borderRadius: '12px',
                }}
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>

          {/* Right Column: Illustration */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}>
            <div style={{
              width: '100%',
              maxWidth: '560px',
              borderRadius: '20px',
              overflow: 'hidden',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.04)',
            }}>
              <img
                src={advisorImg}
                alt="Advising session"
                style={{
                  width: '100%',
                  height: 'auto',
                  display: 'block',
                  objectFit: 'contain',
                }}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
