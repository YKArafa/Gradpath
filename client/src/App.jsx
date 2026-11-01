import React, { useState, useEffect } from 'react';
import LandingPage from './pages/LandingPage';
import SignInPage from './pages/SignInPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import AddStudentPage from './pages/AddStudentPage';
import { getCurrentUser, logoutUser } from './api/auth';

export default function App() {
  const [currentPage, setCurrentPage] = useState('landing');
  const [user, setUser] = useState(() => getCurrentUser());

  // Sync with browser hash for seamless routing
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#/', '').replace('#', '');
      if (hash === 'signin' || hash === 'login') {
        setCurrentPage('signin');
      } else if (hash === 'register' || hash === 'signup') {
        setCurrentPage('register');
      } else if (hash === 'dashboard') {
        setCurrentPage('dashboard');
      } else if (hash === 'add-student' || hash === 'add') {
        setCurrentPage('add-student');
      } else {
        // If logged in and at root, default to dashboard
        const loggedInUser = getCurrentUser();
        if (loggedInUser && !hash) {
          setCurrentPage('dashboard');
        } else {
          setCurrentPage('landing');
        }
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = (page) => {
    setCurrentPage(page);
    window.location.hash = page === 'landing' ? '' : `#/${page}`;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleLoginSuccess = (advisorData) => {
    setUser(advisorData);
  };

  const handleLogout = () => {
    logoutUser();
    setUser(null);
    navigateTo('landing');
  };

  return (
    <div className="app-root">
      {currentPage === 'landing' && (
        <LandingPage 
          onNavigate={navigateTo} 
          user={user} 
          onLogout={handleLogout} 
        />
      )}

      {currentPage === 'signin' && (
        <SignInPage 
          onNavigate={navigateTo} 
          user={user} 
          onLoginSuccess={handleLoginSuccess}
          onLogout={handleLogout} 
        />
      )}

      {currentPage === 'register' && (
        <RegisterPage 
          onNavigate={navigateTo} 
          user={user} 
          onLoginSuccess={handleLoginSuccess}
          onLogout={handleLogout} 
        />
      )}

      {currentPage === 'dashboard' && (
        <DashboardPage 
          onNavigate={navigateTo} 
          user={user} 
          onLogout={handleLogout} 
        />
      )}

      {currentPage === 'add-student' && (
        <AddStudentPage 
          onNavigate={navigateTo} 
          user={user} 
        />
      )}
    </div>
  );
}
