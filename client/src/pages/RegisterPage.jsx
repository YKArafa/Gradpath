import React, { useState } from 'react';
import { registerUser } from '../api/auth';

export default function RegisterPage({ onNavigate, user, onLoginSuccess, onLogout }) {
  const [name, setName] = useState('');
  const [institution, setInstitution] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // If already logged in, show prompt instead of registration form
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
          <h2 style={{ color: '#1e4634', marginBottom: '12px' }}>Account Already Active</h2>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            You are currently signed in as <strong>{user.name}</strong> ({user.email}).
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

  // Form validity check for button style state
  const isFormValid = name.trim() && institution.trim() && email.trim() && password.length >= 8;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !institution.trim() || !email.trim() || !password) {
      setErrorMessage('Please fill in all required fields.');
      return;
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    setErrorMessage('');
    setLoading(true);

    const res = await registerUser({
      name: name.trim(),
      institution: institution.trim(),
      email: email.trim(),
      password,
    });
    setLoading(false);

    if (res.success) {
      setSuccessMessage('Account created! Opening your advisor dashboard...');
      if (onLoginSuccess && res.data && res.data.advisor) {
        onLoginSuccess(res.data.advisor);
      }
      setTimeout(() => {
        onNavigate('dashboard');
      }, 1000);
    } else {
      setErrorMessage(res.error || 'Failed to create account. Please check your details.');
    }
  };

  return (
    <div className="page-container" style={{
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      padding: '40px 20px',
    }}>
      {/* Centered Register Card */}
      <div style={{
        width: '100%',
        maxWidth: '520px',
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        padding: '36px 40px',
        boxShadow: '0 4px 24px rgba(0, 0, 0, 0.03)',
        border: '1px solid #eef2f0',
      }}>
        {/* Top Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{
            fontSize: '32px',
            fontWeight: 800,
            color: '#1e4634',
            marginBottom: '8px',
            letterSpacing: '-0.5px',
          }}>
            Create an account
          </h1>

          <p style={{
            fontSize: '15px',
            color: '#6b7280',
          }}>
            Already have an Account?{' '}
            <span
              onClick={() => onNavigate('signin')}
              style={{
                color: '#1e4634',
                fontWeight: 600,
                textDecoration: 'underline',
                cursor: 'pointer',
              }}
            >
              Sign In
            </span>
          </p>
        </div>

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
          {/* Field 1: What should we call you? */}
          <div className="form-group">
            <label className="form-label" htmlFor="register-name">
              What should we call you?
            </label>
            <input
              id="register-name"
              type="text"
              className="form-input"
              placeholder="Enter your profile name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          {/* Field 2: Institution Name? */}
          <div className="form-group">
            <label className="form-label" htmlFor="register-institution">
              Institution Name?
            </label>
            <input
              id="register-institution"
              type="text"
              className="form-input"
              placeholder="Enter Institution name"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              required
            />
          </div>

          {/* Field 3: What's your email? */}
          <div className="form-group">
            <label className="form-label" htmlFor="register-email">
              What's your email?
            </label>
            <input
              id="register-email"
              type="email"
              className="form-input"
              placeholder="Enter your email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          {/* Field 4: Create a password with Show/Hide toggle */}
          <div className="form-group" style={{ marginBottom: '22px' }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
            }}>
              <label className="form-label" htmlFor="register-password" style={{ margin: 0 }}>
                Create a password
              </label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#6b7280',
                  fontSize: '13.5px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#6b7280"
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
                <span>{showPassword ? 'Hide' : 'Show'}</span>
              </button>
            </div>

            <input
              id="register-password"
              type={showPassword ? 'text' : 'password'}
              className="form-input"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
            <span style={{
              fontSize: '12px',
              color: '#6b7280',
              marginTop: '6px',
              display: 'block',
            }}>
              Use 8 or more characters with a mix of letters, numbers & symbols
            </span>
          </div>

          {/* Terms Agreement */}
          <p style={{
            fontSize: '13px',
            color: '#374151',
            lineHeight: 1.5,
            marginBottom: '20px',
          }}>
            By creating an account, you agree to the{' '}
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>
              Terms of use
            </span>{' '}
            and{' '}
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>
              Privacy Policy.
            </span>
          </p>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className={`btn-submit-full ${isFormValid ? 'btn-submit-active' : 'btn-submit-disabled'}`}
          >
            {loading ? 'Creating account...' : 'Create an account'}
          </button>
        </form>
      </div>

      {/* Back to Home Link */}
      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <button
          type="button"
          onClick={() => onNavigate('landing')}
          style={{
            background: 'none',
            border: 'none',
            color: '#1e4634',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          &larr; Back to GradPath Home
        </button>
      </div>
    </div>
  );
}
