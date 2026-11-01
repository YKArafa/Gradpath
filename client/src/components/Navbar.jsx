import React from 'react';

export default function Navbar({ onNavigate, currentPage, user, onLogout }) {
  const isLoggedIn = !!user;

  return (
    <header className="navbar">
      <div 
        className="logo" 
        onClick={() => onNavigate(isLoggedIn ? 'dashboard' : 'landing')}
        role="button"
        tabIndex={0}
      >
        GradPath
      </div>

      <nav className="nav-actions">
        {isLoggedIn ? (
          <>
            <button 
              type="button" 
              className="nav-link"
              onClick={() => onNavigate(currentPage === 'dashboard' ? 'landing' : 'dashboard')}
            >
              {currentPage === 'dashboard' ? 'Home' : 'Dashboard'}
            </button>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: '#f0f7f3',
              padding: '6px 14px',
              borderRadius: '9999px',
              border: '1px solid #cce3d7',
              fontSize: '14px',
              color: '#1e4634',
              fontWeight: 600,
            }}>
              <span>{user.name || 'Advisor'}</span>
            </div>

            <button 
              type="button" 
              className="nav-link"
              onClick={onLogout}
              style={{ color: '#dc2626', fontWeight: 600 }}
            >
              Sign Out
            </button>
          </>
        ) : (
          <>
            {currentPage !== 'signin' && (
              <button 
                type="button" 
                className="nav-link"
                onClick={() => onNavigate('signin')}
              >
                Login
              </button>
            )}

            {currentPage !== 'register' && (
              <button 
                type="button" 
                className="btn-primary-pill"
                onClick={() => onNavigate('register')}
              >
                Sign Up
              </button>
            )}
          </>
        )}
      </nav>
    </header>
  );
}
