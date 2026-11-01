import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';

export default function DashboardPage({ onNavigate, user, onLogout }) {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [riskFilter, setRiskFilter] = useState('All');
  const [selectedStudentPlan, setSelectedStudentPlan] = useState(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [activeSidebarItem, setActiveSidebarItem] = useState('dashboard');

  // Load real students from backend and calculate their graduation risk using backend method
  useEffect(() => {
    async function loadAdvisorStudentsAndRisks() {
      setLoading(true);
      setErrorMessage('');
      const token = localStorage.getItem('gradpath_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      };

      try {
        // 1. Fetch advisees assigned to the currently authenticated advisor
        const res = await fetch(`${API_BASE_URL}/students/my/students`, { headers });
        if (!res.ok) {
          throw new Error('Failed to retrieve students from backend.');
        }

        const dbStudents = await res.json();
        if (!Array.isArray(dbStudents) || dbStudents.length === 0) {
          setStudents([]);
          setLoading(false);
          return;
        }

        // 2. For EACH student, invoke the backend general_risk_analysis method
        const studentsWithBackendRisk = await Promise.all(
          dbStudents.map(async (s) => {
            const nameParts = (s.name || '').trim().split(' ');
            const inits = nameParts.length > 1
              ? `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`.toUpperCase()
              : (s.name || 'ST').substring(0, 2).toUpperCase();

            try {
              const riskRes = await fetch(`${API_BASE_URL}/analysis/general-risk-analysis/${s.id}`, { headers });
              if (riskRes.ok) {
                const analysisData = await riskRes.json();
                const passedCredits = analysisData.passed_credits ?? analysisData.breakdown?.passed_credits ?? 0;
                
                // Get degree course credits and major credits (or 80 if undeclared)
                const degreeCredits = analysisData.degree_total_credits || analysisData.breakdown?.degree_total_credits || 0;
                const majorCredits = analysisData.has_major
                  ? (analysisData.breakdown?.major_total_credits || 0)
                  : 80;
                // Total credits includes degree credits + major credits (or + 80 if undeclared)
                const totalProgramCredits = analysisData.total_program_credits || (degreeCredits + majorCredits);
                
                const targetGrad = analysisData.finish_semester || s.preferences?.finish_semester || 'N/A';

                const creditsDisplay = totalProgramCredits > 0 
                  ? `${passedCredits} / ${totalProgramCredits}`
                  : `${passedCredits} CH`;

                return {
                  id: s.id,
                  name: s.name,
                  email: s.email,
                  initials: inits,
                  program: s.major_name || s.degree_name || 'Undeclared',
                  credits: creditsDisplay,
                  passedCredits: passedCredits,
                  totalCredits: totalProgramCredits,
                  degreeCredits: degreeCredits,
                  majorCredits: majorCredits,
                  targetGraduation: targetGrad,
                  risk: `${analysisData.risk_level} risk`,
                  riskLevel: analysisData.risk_level,
                  analysis: analysisData,
                  rawStudent: s,
                };
              }
            } catch (riskErr) {
              console.warn(`Failed to compute backend risk for student ${s.id}:`, riskErr);
            }

            // Fallback if risk analysis endpoint fails for an individual student
            return {
              id: s.id,
              name: s.name,
              email: s.email,
              initials: inits,
              program: s.major_name || s.degree_name || 'Undeclared',
              credits: '0 CH',
              targetGraduation: s.preferences?.finish_semester || 'N/A',
              risk: 'Low risk',
              riskLevel: 'Low',
              analysis: null,
              rawStudent: s,
            };
          })
        );

        setStudents(studentsWithBackendRisk);
      } catch (err) {
        console.error('Error loading students and calculating risks:', err);
        setErrorMessage(err.message || 'Could not fetch students.');
        setStudents([]);
      } finally {
        setLoading(false);
      }
    }

    loadAdvisorStudentsAndRisks();
  }, []);

  // Filter students dynamically
  const filteredStudents = students.filter((student) => {
    const matchesSearch =
      student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      student.program.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesRisk =
      riskFilter === 'All' ||
      student.risk.toLowerCase() === riskFilter.toLowerCase() ||
      student.riskLevel.toLowerCase() === riskFilter.toLowerCase();

    return matchesSearch && matchesRisk;
  });

  // Calculate dynamic stats from real backend risk values
  const totalCount = students.length;
  const onTrackCount = students.filter((s) => s.riskLevel === 'Low').length;
  const needAttentionCount = students.filter((s) => s.riskLevel === 'Medium').length;
  const highRiskCount = students.filter((s) => s.riskLevel === 'High' || s.riskLevel === 'Critical').length;
  const onTrackPercent = totalCount > 0 ? Math.round((onTrackCount / totalCount) * 100) : 0;

  // View plan handler
  const handleViewPlan = async (student) => {
    if (student.analysis) {
      setSelectedStudentPlan(student);
      return;
    }

    setSelectedStudentPlan(student);
    setLoadingPlan(true);

    const token = localStorage.getItem('gradpath_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    try {
      const res = await fetch(`${API_BASE_URL}/analysis/general-risk-analysis/${student.id}`, { headers });
      if (res.ok) {
        const riskData = await res.json();
        setSelectedStudentPlan({
          ...student,
          analysis: riskData,
        });
      }
    } catch (err) {
      console.warn('Error fetching detailed plan:', err);
    } finally {
      setLoadingPlan(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      backgroundColor: '#f5f7f5',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* ------------------------------------------------------------- */}
      {/* 1. LEFT SIDEBAR (Image 1 reference) */}
      {/* ------------------------------------------------------------- */}
      <aside style={{
        width: '240px',
        backgroundColor: '#1f2937',
        color: '#ffffff',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '24px 0',
        flexShrink: 0,
      }}>
        <div>
          {/* Logo */}
          <div style={{
            padding: '0 24px 28px 24px',
            fontSize: '24px',
            fontWeight: 800,
            color: '#10b981',
            letterSpacing: '-0.5px',
          }}>
            GradPath
          </div>

          {/* Navigation Links */}
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {/* Dashboard (Active Item) */}
            <button
              type="button"
              onClick={() => setActiveSidebarItem('dashboard')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                width: '100%',
                border: 'none',
                background: activeSidebarItem === 'dashboard' ? '#166534' : 'transparent',
                color: activeSidebarItem === 'dashboard' ? '#ffffff' : '#94a3b8',
                fontSize: '14.5px',
                fontWeight: activeSidebarItem === 'dashboard' ? 600 : 500,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'background-color 0.15s',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
              </svg>
              <span>Dashboard</span>
            </button>

            {/* What-if Simulator */}
            <button
              type="button"
              onClick={() => setActiveSidebarItem('simulator')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                width: '100%',
                border: 'none',
                background: activeSidebarItem === 'simulator' ? '#166534' : 'transparent',
                color: activeSidebarItem === 'simulator' ? '#ffffff' : '#94a3b8',
                fontSize: '14.5px',
                fontWeight: 500,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="4" y="2" width="16" height="20" rx="2" />
                <line x1="8" y1="6" x2="16" y2="6" />
                <line x1="16" y1="14" x2="16" y2="18" />
                <path d="M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01" />
              </svg>
              <span>What-if Simulator</span>
            </button>

            {/* Recommendation */}
            <button
              type="button"
              onClick={() => setActiveSidebarItem('recommendation')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                width: '100%',
                border: 'none',
                background: activeSidebarItem === 'recommendation' ? '#166534' : 'transparent',
                color: activeSidebarItem === 'recommendation' ? '#ffffff' : '#94a3b8',
                fontSize: '14.5px',
                fontWeight: 500,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>Recommendation</span>
            </button>

            {/* Profile */}
            <button
              type="button"
              onClick={() => setActiveSidebarItem('profile')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                width: '100%',
                border: 'none',
                background: activeSidebarItem === 'profile' ? '#166534' : 'transparent',
                color: activeSidebarItem === 'profile' ? '#ffffff' : '#94a3b8',
                fontSize: '14.5px',
                fontWeight: 500,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <span>Profile</span>
            </button>
          </nav>
        </div>

        {/* Bottom Actions: Home & Logout */}
        <div style={{ borderTop: '1px solid #334155', paddingTop: '16px' }}>
          <button
            type="button"
            onClick={() => onNavigate('landing')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 24px',
              width: '100%',
              border: 'none',
              background: 'transparent',
              color: '#94a3b8',
              fontSize: '14px',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
            <span>Home</span>
          </button>

          <button
            type="button"
            onClick={onLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 24px',
              width: '100%',
              border: 'none',
              background: 'transparent',
              color: '#f87171',
              fontSize: '14px',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------- */}
      {/* 2. MAIN DASHBOARD CONTENT AREA */}
      {/* ------------------------------------------------------------- */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top Header */}
        <header style={{
          height: '68px',
          backgroundColor: '#f5f7f5',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          padding: '0 40px',
          gap: '24px',
        }}>
          <button
            type="button"
            onClick={() => onNavigate('landing')}
            style={{ background: 'none', border: 'none', color: '#4b5563', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}
          >
            Home
          </button>

          <button
            type="button"
            style={{ background: 'none', border: 'none', color: '#166534', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}
          >
            Dashboard
          </button>

          {/* Notification Bell */}
          <div style={{ position: 'relative', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1f2937" strokeWidth="2">
              <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
              <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
            </svg>
            {highRiskCount > 0 && (
              <span style={{
                position: 'absolute',
                top: '-6px',
                right: '-8px',
                backgroundColor: '#ef4444',
                color: '#ffffff',
                fontSize: '11px',
                fontWeight: 700,
                borderRadius: '9999px',
                width: '18px',
                height: '18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {highRiskCount}
              </span>
            )}
          </div>

          {/* User Profile Avatar Icon */}
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: '#ffffff',
            border: '1.5px solid #d1d5db',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#1f2937',
            cursor: 'pointer',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
        </header>

        {/* Dashboard Body Scrollable */}
        <div style={{ padding: '0 40px 48px 40px', overflowY: 'auto' }}>
          {/* Welcome Banner Card (Image 1) */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            padding: '32px 36px',
            border: '1px solid #eef2f0',
            boxShadow: '0 2px 10px rgba(0, 0, 0, 0.02)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '28px',
          }}>
            <div>
              <h1 style={{
                fontSize: '32px',
                fontWeight: 800,
                color: '#111827',
                marginBottom: '8px',
                letterSpacing: '-0.5px',
              }}>
                Welcome back, {user?.name ? user.name.split(' ')[0] : 'Advisor'}
              </h1>
              <p style={{
                fontSize: '15px',
                color: '#374151',
                marginBottom: '24px',
              }}>
                Advise Another Student?
              </p>
              <button
                type="button"
                onClick={() => onNavigate('add-student')}
                style={{
                  backgroundColor: '#1e4634',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '9999px',
                  padding: '12px 28px',
                  fontSize: '15px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'background-color 0.2s',
                }}
              >
                <span>Add Student</span>
              </button>
            </div>

            {/* Illustration: Students studying at desk */}
            <div style={{ width: '220px', height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="220" height="140" viewBox="0 0 240 160" fill="none">
                <rect x="20" y="115" width="200" height="8" rx="2" fill="#d2b48c" />
                <rect x="35" y="123" width="8" height="35" rx="1" fill="#b08d57" />
                <rect x="197" y="123" width="8" height="35" rx="1" fill="#b08d57" />
                <path d="M185 115 L190 102 L198 102 L203 115 Z" fill="#d97706" />
                <circle cx="194" cy="98" r="6" fill="#10b981" />
                <circle cx="190" cy="93" r="5" fill="#059669" />
                <circle cx="198" cy="93" r="5" fill="#34d399" />
                <rect x="80" y="110" width="45" height="12" rx="1" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1.5" />
                <rect x="68" y="114" width="10" height="6" rx="1" fill="#64748b" />
                <circle cx="95" cy="52" r="16" fill="#fbcfe8" />
                <path d="M80 50 Q95 32 110 50 Q112 36 95 36 Q78 36 80 50" fill="#1e293b" />
                <path d="M80 68 Q95 72 110 68 L114 115 L76 115 Z" fill="#7c3aed" />
                <circle cx="91" cy="52" r="1.5" fill="#1e293b" />
                <circle cx="99" cy="52" r="1.5" fill="#1e293b" />
                <circle cx="150" cy="54" r="16" fill="#fed7aa" />
                <path d="M136 50 Q150 36 164 50 Q162 40 150 40 Q138 40 136 50" fill="#0f172a" />
                <path d="M136 70 Q150 74 164 70 L168 115 L132 115 Z" fill="#f59e0b" />
                <circle cx="146" cy="54" r="1.5" fill="#0f172a" />
                <circle cx="154" cy="54" r="1.5" fill="#0f172a" />
                <circle cx="106" cy="112" r="3.5" fill="#fbcfe8" />
                <circle cx="138" cy="112" r="3.5" fill="#fed7aa" />
              </svg>
            </div>
          </div>

          {errorMessage && (
            <div style={{
              backgroundColor: '#fef2f2',
              color: '#991b1b',
              border: '1px solid #fecaca',
              padding: '12px 18px',
              borderRadius: '12px',
              fontSize: '14px',
              marginBottom: '20px',
            }}>
              {errorMessage}
            </div>
          )}

          {/* 4 Stats Cards Grid - 100% Dynamic Calculated from Backend Risk Analysis */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '20px',
            marginBottom: '32px',
          }}>
            {/* Card 1: Total students */}
            <div style={{
              backgroundColor: '#ffffff',
              borderRadius: '16px',
              padding: '20px 24px',
              border: '1px solid #eef2f0',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.02)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13.5px', color: '#4b5563', fontWeight: 500 }}>Total students</span>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#3b82f6' }}></span>
              </div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#111827', lineHeight: 1.2 }}>
                {loading ? '...' : totalCount}
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>Currently advising</div>
            </div>

            {/* Card 2: On track */}
            <div style={{
              backgroundColor: '#ffffff',
              borderRadius: '16px',
              padding: '20px 24px',
              border: '1px solid #eef2f0',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.02)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13.5px', color: '#4b5563', fontWeight: 500 }}>On track</span>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }}></span>
              </div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#111827', lineHeight: 1.2 }}>
                {loading ? '...' : onTrackCount}
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                {loading ? '...' : totalCount > 0 ? `${onTrackPercent}% of students` : '0% of students'}
              </div>
            </div>

            {/* Card 3: Need attention */}
            <div style={{
              backgroundColor: '#ffffff',
              borderRadius: '16px',
              padding: '20px 24px',
              border: '1px solid #eef2f0',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.02)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13.5px', color: '#4b5563', fontWeight: 500 }}>Need attention</span>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f97316' }}></span>
              </div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#111827', lineHeight: 1.2 }}>
                {loading ? '...' : needAttentionCount}
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>Medium risk</div>
            </div>

            {/* Card 4: At high risk */}
            <div style={{
              backgroundColor: '#ffffff',
              borderRadius: '16px',
              padding: '20px 24px',
              border: '1px solid #eef2f0',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.02)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13.5px', color: '#4b5563', fontWeight: 500 }}>At high risk</span>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }}></span>
              </div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#111827', lineHeight: 1.2 }}>
                {loading ? '...' : highRiskCount}
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>Review recommended</div>
            </div>
          </div>

          {/* ------------------------------------------------------------- */}
          {/* 5. "MY STUDENTS" TABLE CARD (Image 1 reference) */}
          {/* ------------------------------------------------------------- */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            padding: '28px',
            border: '1px solid #eef2f0',
            boxShadow: '0 2px 12px rgba(0, 0, 0, 0.03)',
          }}>
            {/* Top Toolbar */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
              marginBottom: '24px',
            }}>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#111827' }}>
                  My students
                </h2>
                <span style={{ fontSize: '13.5px', color: '#6b7280' }}>
                  {filteredStudents.length} {filteredStudents.length === 1 ? 'student' : 'students'} shown
                </span>
              </div>

              {/* Search & Filter Controls */}
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                {/* Search Input */}
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#9ca3af"
                    strokeWidth="2"
                    style={{ position: 'absolute', left: '12px' }}
                  >
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  <input
                    type="text"
                    placeholder="Search students"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{
                      padding: '8px 14px 8px 36px',
                      borderRadius: '10px',
                      border: '1px solid #e5e7eb',
                      fontSize: '13.5px',
                      backgroundColor: '#f9fafb',
                      outline: 'none',
                      width: '200px',
                    }}
                  />
                </div>

                {/* Risk Filter Select */}
                <select
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '10px',
                    border: '1px solid #e5e7eb',
                    backgroundColor: '#f9fafb',
                    fontSize: '13.5px',
                    color: '#374151',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  <option value="All">All Risks</option>
                  <option value="Low">Low risk</option>
                  <option value="Medium">Medium risk</option>
                  <option value="High">High risk</option>
                  <option value="Critical">Critical risk</option>
                </select>
              </div>
            </div>

            {/* Students Table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{
                    borderBottom: '1px solid #f1f5f9',
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    color: '#94a3b8',
                    letterSpacing: '0.6px',
                  }}>
                    <th style={{ padding: '14px 16px' }}>STUDENT</th>
                    <th style={{ padding: '14px 16px' }}>PROGRAM</th>
                    <th style={{ padding: '14px 16px' }}>CREDITS</th>
                    <th style={{ padding: '14px 16px' }}>TARGET GRADUATION</th>
                    <th style={{ padding: '14px 16px' }}>GRADUATION RISK</th>
                    <th style={{ padding: '14px 16px', textAlign: 'right' }}>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: '#6b7280' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                          <span style={{ fontSize: '15px', fontWeight: 600, color: '#166534' }}>
                            Calculating graduation risks with backend engine...
                          </span>
                          <span style={{ fontSize: '13px', color: '#94a3b8' }}>
                            Analyzing student transcripts, course loads, and remaining semesters
                          </span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredStudents.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px' }}>
                        <div style={{ maxWidth: '440px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                          <div style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '50%',
                            backgroundColor: '#f0fdf4',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#166534',
                          }}>
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                              <circle cx="9" cy="7" r="4" />
                              <line x1="19" y1="8" x2="19" y2="14" />
                              <line x1="22" y1="11" x2="16" y2="11" />
                            </svg>
                          </div>
                          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#111827', margin: 0 }}>
                            {students.length === 0 ? 'No students registered yet' : 'No matching students'}
                          </h3>
                          <p style={{ fontSize: '13.5px', color: '#6b7280', margin: 0 }}>
                            {students.length === 0
                              ? "You don't have any students in your advising list yet. Add a student to automatically evaluate graduation path and risk."
                              : 'Try adjusting your search keywords or risk filter.'}
                          </p>
                          {students.length === 0 && (
                            <button
                              type="button"
                              onClick={() => onNavigate('add-student')}
                              style={{
                                marginTop: '8px',
                                backgroundColor: '#1e4634',
                                color: '#ffffff',
                                border: 'none',
                                borderRadius: '9999px',
                                padding: '10px 24px',
                                fontSize: '13.5px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              + Add Student
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredStudents.map((s) => (
                      <tr
                        key={s.id}
                        style={{
                          borderBottom: '1px solid #f8fafc',
                          transition: 'background-color 0.15s',
                        }}
                      >
                        {/* Student Initials + Name */}
                        <td style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: '50%',
                            backgroundColor: '#f1f5f9',
                            color: '#475569',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '12.5px',
                            fontWeight: 700,
                            flexShrink: 0,
                          }}>
                            {s.initials}
                          </div>
                          <div>
                            <div style={{ fontSize: '14.5px', fontWeight: 600, color: '#111827' }}>
                              {s.name}
                            </div>
                            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                              {s.email}
                            </div>
                          </div>
                        </td>

                        {/* Program */}
                        <td style={{ padding: '16px', fontSize: '14px', color: '#4b5563' }}>
                          {s.program}
                        </td>

                        {/* Credits */}
                        <td style={{ padding: '16px', fontSize: '14px', fontWeight: 600, color: '#374151' }}>
                          {s.credits}
                        </td>

                        {/* Target Graduation */}
                        <td style={{ padding: '16px', fontSize: '14px', color: '#4b5563' }}>
                          {s.targetGraduation}
                        </td>

                        {/* Graduation Risk Badge */}
                        <td style={{ padding: '16px' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '4px 12px',
                            borderRadius: '9999px',
                            fontSize: '12px',
                            fontWeight: 600,
                            backgroundColor:
                              s.riskLevel === 'Low' ? '#eaf8ef' :
                              s.riskLevel === 'Medium' ? '#fef3c7' : '#fee2e2',
                            color:
                              s.riskLevel === 'Low' ? '#166534' :
                              s.riskLevel === 'Medium' ? '#92400e' : '#b91c1c',
                          }}>
                            <span style={{
                              width: '6px',
                              height: '6px',
                              borderRadius: '50%',
                              backgroundColor:
                                s.riskLevel === 'Low' ? '#22c55e' :
                                s.riskLevel === 'Medium' ? '#d97706' : '#ef4444',
                            }}></span>
                            {s.risk}
                          </span>
                        </td>

                        {/* Action */}
                        <td style={{ padding: '16px', textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={() => handleViewPlan(s)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#1e4634',
                              fontSize: '13.5px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            View plan &rarr;
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 6. MODAL: "VIEW PLAN" & REAL RISK ANALYSIS BREAKDOWN */}
      {/* ------------------------------------------------------------- */}
      {selectedStudentPlan && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px',
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            padding: '32px',
            maxWidth: '640px',
            width: '100%',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.15)',
            maxHeight: '90vh',
            overflowY: 'auto',
          }}>
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: '#166534', letterSpacing: '0.8px' }}>
                  Backend Academic Analysis
                </span>
                <h3 style={{ fontSize: '24px', fontWeight: 800, color: '#111827', marginTop: '2px' }}>
                  {selectedStudentPlan.name}
                </h3>
                <p style={{ fontSize: '14px', color: '#6b7280' }}>
                  {selectedStudentPlan.program} &bull; Target: {selectedStudentPlan.targetGraduation}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setSelectedStudentPlan(null)}
                style={{
                  background: '#f1f5f9',
                  border: 'none',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '18px',
                  cursor: 'pointer',
                  color: '#64748b',
                }}
              >
                &times;
              </button>
            </div>

            {loadingPlan ? (
              <div style={{ padding: '30px', textAlign: 'center', color: '#64748b' }}>
                Loading full risk breakdown...
              </div>
            ) : selectedStudentPlan.analysis ? (
              <div>
                {/* Risk Level Highlight */}
                <div style={{
                  padding: '16px 20px',
                  borderRadius: '12px',
                  backgroundColor:
                    selectedStudentPlan.analysis.risk_level === 'Low' ? '#ecfdf5' :
                    selectedStudentPlan.analysis.risk_level === 'Medium' ? '#fffbeb' : '#fef2f2',
                  border: `1px solid ${
                    selectedStudentPlan.analysis.risk_level === 'Low' ? '#a7f3d0' :
                    selectedStudentPlan.analysis.risk_level === 'Medium' ? '#fde68a' : '#fecaca'
                  }`,
                  marginBottom: '20px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{
                      fontWeight: 700,
                      fontSize: '15px',
                      color:
                        selectedStudentPlan.analysis.risk_level === 'Low' ? '#065f46' :
                        selectedStudentPlan.analysis.risk_level === 'Medium' ? '#92400e' : '#991b1b',
                    }}>
                      Graduation Risk: {selectedStudentPlan.analysis.risk_level} Risk
                    </span>
                    <span style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: '#4b5563',
                    }}>
                      Current: {selectedStudentPlan.analysis.current_semester}
                    </span>
                  </div>
                  <p style={{
                    fontSize: '13.5px',
                    color: '#374151',
                    marginTop: '8px',
                    lineHeight: 1.5,
                  }}>
                    {selectedStudentPlan.analysis.summary}
                  </p>
                </div>

                {/* Key Risk Metrics Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '24px' }}>
                  <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Credits Needed to Graduate</div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: '#1e293b' }}>
                      {selectedStudentPlan.analysis.credit_score_counter} CH
                    </div>
                  </div>

                  <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Semesters Left</div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: '#1e293b' }}>
                      {selectedStudentPlan.analysis.semesters_left} regular semesters
                    </div>
                  </div>

                  <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Needed per Semester</div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: selectedStudentPlan.analysis.credits_per_semester_needed > 30 ? '#dc2626' : '#166534' }}>
                      {selectedStudentPlan.analysis.credits_per_semester_needed} CH / sem
                    </div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>Standard benchmark: 30.0 CH</div>
                  </div>

                  <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Total Program Credits</div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: '#1e293b' }}>
                      {selectedStudentPlan.totalCredits || selectedStudentPlan.analysis.total_program_credits || selectedStudentPlan.analysis.breakdown?.total_program_credits || 0} CH
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>
                      Degree: {selectedStudentPlan.analysis.degree_total_credits || selectedStudentPlan.analysis.breakdown?.degree_total_credits || 0} CH + {selectedStudentPlan.analysis.has_major ? `Major: ${selectedStudentPlan.analysis.breakdown?.major_total_credits || 0} CH` : 'Undeclared: 80 CH'}
                    </div>
                  </div>

                  <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Major Status</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#1e293b' }}>
                      {selectedStudentPlan.analysis.has_major ? 'Declared Major' : 'Undeclared (+80 CH in total)'}
                    </div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                      {selectedStudentPlan.analysis.has_major ? selectedStudentPlan.rawStudent?.major_name || 'Major assigned' : '80 credits added to required total'}
                    </div>
                  </div>
                </div>

                {/* Remaining Semesters Sequence */}
                {selectedStudentPlan.analysis.remaining_semesters && selectedStudentPlan.analysis.remaining_semesters.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#374151', marginBottom: '8px' }}>
                      Timeline to Graduation:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {selectedStudentPlan.analysis.remaining_semesters.map((sem, idx) => (
                        <span
                          key={idx}
                          style={{
                            backgroundColor: '#e0e7ff',
                            color: '#3730a3',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 600,
                          }}
                        >
                          {sem}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Failed courses (if any) */}
                {selectedStudentPlan.analysis.breakdown?.failed_courses && selectedStudentPlan.analysis.breakdown.failed_courses.length > 0 && (
                  <div style={{
                    marginBottom: '20px',
                    backgroundColor: '#fff1f2',
                    padding: '14px',
                    borderRadius: '10px',
                    border: '1px solid #fecdd3',
                  }}>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#9f1239', marginBottom: '6px' }}>
                      Failed Courses Requiring Retake ({selectedStudentPlan.analysis.breakdown.failed_courses.length}):
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12.5px', color: '#881337' }}>
                      {selectedStudentPlan.analysis.breakdown.failed_courses.map((fc, idx) => (
                        <li key={idx}>
                          {fc.code || fc.title || fc.course_identifier} &bull; {fc.credit_hours} CH (Grade: {fc.grade})
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: '24px 0', textAlign: 'center', color: '#6b7280' }}>
                No detailed analysis record available for this student.
              </div>
            )}

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button
                type="button"
                onClick={() => setSelectedStudentPlan(null)}
                style={{
                  backgroundColor: '#1e4634',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '9999px',
                  padding: '10px 24px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Close Plan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
