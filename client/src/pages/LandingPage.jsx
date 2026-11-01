import React from 'react';
import Navbar from '../components/Navbar';
import advisorImg from '../assets/advisoradvising.png';

export default function LandingPage({ onNavigate, user, onLogout }) {
  const isLoggedIn = !!user;

  return (
    <div className="page-container">
      <Navbar 
        onNavigate={onNavigate} 
        currentPage="landing" 
        user={user} 
        onLogout={onLogout} 
      />

      <main style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        maxWidth: '1240px',
        width: '100%',
        margin: '0 auto',
        padding: '30px 0 60px 0',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '48px',
          alignItems: 'center',
          width: '100%',
        }}>
          {/* Left Column: Headline and Call to Actions */}
          <div style={{ maxWidth: '560px' }}>
            <h1 style={{
              fontSize: 'clamp(42px, 5.5vw, 68px)',
              fontWeight: 800,
              lineHeight: 1.08,
              letterSpacing: '-1.5px',
              color: '#1e4634',
              marginBottom: '24px',
            }}>
              A clearer<br />
              path<br />
              <span className="serif-text" style={{
                color: '#d05a2b',
                fontWeight: 700,
                letterSpacing: '-0.5px',
              }}>
                to graduation.
              </span>
            </h1>

            <p style={{
              fontSize: '16.5px',
              lineHeight: 1.6,
              color: '#374151',
              maxWidth: '460px',
              marginBottom: '40px',
            }}>
              Gradpath recommends the courses each student should take next,
              helping advisors guide them toward graduation in the best possible time.
            </p>

            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '16px',
            }}>
              {isLoggedIn ? (
                <>
                  <button
                    type="button"
                    className="btn-primary-pill"
                    onClick={() => onNavigate('dashboard')}
                    style={{
                      padding: '16px 36px',
                      borderRadius: '9999px',
                      fontSize: '16px',
                    }}
                  >
                    Go to My Dashboard &rarr;
                  </button>
                  <button
                    type="button"
                    className="nav-link"
                    onClick={onLogout}
                    style={{
                      border: '1px solid #e5e7eb',
                      borderRadius: '9999px',
                      padding: '12px 24px',
                      color: '#dc2626',
                      fontWeight: 600,
                    }}
                  >
                    Sign Out
                  </button>
                </>
              ) : (
                <>
                  {/* Button 1: Get Started as an advisor */}
                  <button
                    type="button"
                    className="btn-primary-pill"
                    onClick={() => onNavigate('register')}
                    style={{
                      padding: '12px 28px',
                      borderRadius: '9999px',
                      lineHeight: 1.25,
                      textAlign: 'left',
                    }}
                  >
                    <span>
                      Get Started as<br />an advisor
                    </span>
                    <span style={{ fontSize: '18px', marginLeft: '6px' }}>&rarr;</span>
                  </button>

                  {/* Button 2: Get Started */}
                  <button
                    type="button"
                    className="btn-primary-pill"
                    onClick={() => onNavigate('signin')}
                    style={{
                      padding: '16px 36px',
                      borderRadius: '9999px',
                    }}
                  >
                    Get Started
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Right Column: Illustration */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}>
            <div style={{
              width: '100%',
              maxWidth: '580px',
              borderRadius: '20px',
              overflow: 'hidden',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.04)',
            }}>
              <img
                src={advisorImg}
                alt="Academic Advisor with student reviewing academic plan"
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
