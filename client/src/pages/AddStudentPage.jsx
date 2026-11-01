import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';

// Fixed list of subject types for preferences
const FIXED_SUBJECT_TYPES = [
  'Mathematics & Statistics',
  'Computer Science & IT',
  'Engineering & Technology',
  'Business & Finance',
  'Natural Sciences',
  'Humanities & Literature',
  'Social Sciences',
  'Law & Legal Studies',
  'Medicine & Health Sciences',
  'Arts & Design',
  'Communication & Media',
  'Architecture & Design',
  'Interdisciplinary Studies',
  'Environmental & Agricultural Sciences',
];

const WORKLOAD_PACES = [
  'Standard Load (30 credits / semester)',
  'Lighter Load (20 - 25 credits / semester)',
  'Accelerated Pace (35+ credits / semester)',
];

const SCHEDULE_PREFERENCES = [
  'Morning Classes Preferred',
  'Afternoon Classes Preferred',
  'Flexible / No Preference',
];

export default function AddStudentPage({ onNavigate, user }) {
  // Basic Form State matching Image 2
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [enrollmentDate, setEnrollmentDate] = useState('');
  const [institution, setInstitution] = useState(user?.institution || '');
  const [degreeId, setDegreeId] = useState('');
  const [majorId, setMajorId] = useState('');

  // Fixed list preferences state
  const [selectedSubjectTypes, setSelectedSubjectTypes] = useState([
    'Software Engineering & Systems',
    'AI, Machine Learning & Data Science',
  ]);
  const [workloadPace, setWorkloadPace] = useState(WORKLOAD_PACES[0]);
  const [schedulePref, setSchedulePref] = useState(SCHEDULE_PREFERENCES[2]);
  const [willingSummer, setWillingSummer] = useState(true);
  const [targetGraduation, setTargetGraduation] = useState('Spring 2028');

  // Degrees and Majors from backend
  const [degreesList, setDegreesList] = useState([]);
  const [majorsList, setMajorsList] = useState([]);
  const [loadingOptions, setLoadingOptions] = useState(true);

  // Form submission state
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Fetch degrees and majors strictly from backend - NO HARDCODED FALLBACKS
  useEffect(() => {
    async function fetchDegreesAndMajors() {
      setLoadingOptions(true);
      const token = localStorage.getItem('gradpath_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      try {
        // Fetch degrees from /transcripts/degrees
        const degRes = await fetch(`${API_BASE_URL}/transcripts/degrees`, { headers });
        if (degRes.ok) {
          const degData = await degRes.json();
          setDegreesList(degData || []);
          if (degData && degData.length > 0 && !degreeId) {
            setDegreeId(String(degData[0].id));
          }
        } else {
          setDegreesList([]);
          setErrorMessage('Could not load degrees from backend (Status ' + degRes.status + '). Ensure server is running.');
        }

        // Fetch majors from /transcripts/majors
        const majRes = await fetch(`${API_BASE_URL}/transcripts/majors`, { headers });
        if (majRes.ok) {
          const majData = await majRes.json();
          setMajorsList(majData || []);
        } else {
          setMajorsList([]);
        }
      } catch (err) {
        console.warn('Backend options fetch error:', err);
        setDegreesList([]);
        setMajorsList([]);
        setErrorMessage('Cannot connect to backend server at http://localhost:8000. Please start the backend server.');
      } finally {
        setLoadingOptions(false);
      }
    }

    fetchDegreesAndMajors();
  }, []);

  // Filter majors strictly where degree_id matches the chosen degree ID
  const filteredMajors = degreeId
    ? majorsList.filter((m) => Number(m.degree_id) === Number(degreeId))
    : [];

  const handleDegreeChange = (newDegId) => {
    setDegreeId(newDegId);
    setMajorId(''); // Reset major when degree changes to ensure major belongs to chosen degree
  };

  const toggleSubjectType = (subject) => {
    if (selectedSubjectTypes.includes(subject)) {
      setSelectedSubjectTypes(selectedSubjectTypes.filter((s) => s !== subject));
    } else {
      setSelectedSubjectTypes([...selectedSubjectTypes, subject]);
    }
  };

  const isFormValid = name.trim() && email.trim() && degreeId;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim()) {
      setErrorMessage('Please provide student name and email.');
      return;
    }

    setLoading(true);
    setErrorMessage('');
    setSuccessMessage('');

    const token = localStorage.getItem('gradpath_token');
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };

    // Format enrollment date to ISO timestamp
    let parsedEnrollment = new Date().toISOString();
    if (enrollmentDate) {
      const d = new Date(enrollmentDate);
      if (!isNaN(d.getTime())) {
        parsedEnrollment = d.toISOString();
      }
    }

    const payload = {
      name: name.trim(),
      email: email.trim().toLowerCase(),
      institution: institution.trim() || user?.institution || 'University',
      time_of_enrollment: parsedEnrollment,
      degree_id: parseInt(degreeId, 10),
      major_id: majorId ? parseInt(majorId, 10) : null,
      preferences: {
        preferred_subject_types: selectedSubjectTypes,
        workload_pace: workloadPace,
        schedule_preference: schedulePref,
        summer_courses: willingSummer,
        finish_semester: targetGraduation,
      },
      gpa: 3.5, // Default initial GPA baseline
    };

    try {
      const response = await fetch(`${API_BASE_URL}/students`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add student record.');
      }

      const createdStudent = await response.json();
      setSuccessMessage(`Student '${createdStudent.name}' added successfully! Redirecting to Dashboard...`);

      setTimeout(() => {
        onNavigate('dashboard');
      }, 1200);
    } catch (err) {
      setErrorMessage(err.message || 'Error creating student.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f7faf8',
      display: 'flex',
      flexDirection: 'column',
      padding: '24px 32px 60px 32px',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Top Navbar */}
      <header style={{
        maxWidth: '800px',
        width: '100%',
        margin: '0 auto 20px auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div
          onClick={() => onNavigate('dashboard')}
          style={{
            fontSize: '26px',
            fontWeight: 800,
            color: '#1e4634',
            cursor: 'pointer',
            letterSpacing: '-0.5px',
          }}
        >
          Grad Path
        </div>

        <button
          type="button"
          onClick={() => onNavigate('dashboard')}
          style={{
            background: 'none',
            border: 'none',
            color: '#1e4634',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          &larr; Back to Dashboard
        </button>
      </header>

      {/* Main Container */}
      <main style={{
        maxWidth: '580px',
        width: '100%',
        margin: '0 auto',
      }}>
        <h1 style={{
          textAlign: 'center',
          fontSize: '28px',
          fontWeight: 800,
          color: '#1e4634',
          marginBottom: '32px',
        }}>
          Add Student
        </h1>

        {errorMessage && (
          <div style={{
            backgroundColor: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            padding: '12px 16px',
            borderRadius: '10px',
            fontSize: '14px',
            marginBottom: '20px',
          }}>
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div style={{
            backgroundColor: '#f0fdf4',
            color: '#166534',
            border: '1px solid #bbf7d0',
            padding: '12px 16px',
            borderRadius: '10px',
            fontSize: '14px',
            marginBottom: '20px',
          }}>
            {successMessage}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Field 1: Name */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              Name
            </label>
            <input
              type="text"
              placeholder="Student's name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
              }}
            />
          </div>

          {/* Field 2: email */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              email:
            </label>
            <input
              type="email"
              placeholder="Student's email..."
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
              }}
            />
          </div>

          {/* Field 3: Date of enrollment */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              Date of enrollment:
            </label>
            <input
              type="date"
              placeholder="DD/MM/YYYY"
              value={enrollmentDate}
              onChange={(e) => setEnrollmentDate(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
                color: enrollmentDate ? '#111827' : '#9ca3af',
              }}
            />
          </div>

          {/* Field 4: Institution */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              Institution:
            </label>
            <input
              type="text"
              placeholder="university name..."
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
              }}
            />
          </div>

          {/* Field 5: Degree Dropdown */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              Degree:
            </label>
            <select
              value={degreeId}
              onChange={(e) => handleDegreeChange(e.target.value)}
              required
              disabled={loadingOptions || degreesList.length === 0}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: degreesList.length === 0 ? '#f9fafb' : '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
                color: degreeId ? '#111827' : '#9ca3af',
              }}
            >
              {loadingOptions ? (
                <option value="" disabled>Loading degrees from server...</option>
              ) : degreesList.length === 0 ? (
                <option value="" disabled>No degrees found (Check backend on port 8000)</option>
              ) : (
                <option value="" disabled>Select Degree...</option>
              )}
              {degreesList.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          {/* Field 6: Major Dropdown (Filtered strictly by chosen Degree ID) */}
          <div style={{ marginBottom: '28px' }}>
            <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 500, color: '#4b5563', marginBottom: '6px' }}>
              Major (Optional):
            </label>
            <select
              value={majorId}
              onChange={(e) => setMajorId(e.target.value)}
              disabled={!degreeId}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                backgroundColor: !degreeId ? '#f9fafb' : '#ffffff',
                fontSize: '14.5px',
                outline: 'none',
                color: majorId ? '#111827' : '#9ca3af',
                cursor: !degreeId ? 'not-allowed' : 'pointer',
              }}
            >
              {!degreeId ? (
                <option value="">Select a degree first...</option>
              ) : filteredMajors.length === 0 ? (
                <option value="">No majors for this degree (will be undeclared)</option>
              ) : (
                <>
                  <option value="">Select Major (or leave undeclared)...</option>
                  {filteredMajors.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </>
              )}
            </select>
            <span style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px', display: 'block' }}>
              {degreeId ? 'Only majors belonging to the selected degree are shown.' : 'Choose a degree above to view available majors.'}
            </span>
          </div>

          {/* ------------------------------------------------------------- */}
          {/* USER SPECIFICATION: SETTING STUDENT PREFERENCES */}
          {/* ------------------------------------------------------------- */}
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            padding: '24px',
            marginBottom: '32px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.02)',
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '16px',
              borderBottom: '1px solid #f3f4f6',
              paddingBottom: '10px',
            }}>
              <span style={{ fontSize: '18px' }}>🎯</span>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#1e4634' }}>
                Student Preferences & Study Plan Goals
              </h3>
            </div>

            {/* Preference: Preferred Subject Types (Fixed List) */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#374151', marginBottom: '8px' }}>
                Preferred Subject Types (Select all that apply):
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {FIXED_SUBJECT_TYPES.map((type) => {
                  const isSelected = selectedSubjectTypes.includes(type);
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleSubjectType(type)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '9999px',
                        fontSize: '12.5px',
                        fontWeight: 500,
                        cursor: 'pointer',
                        border: isSelected ? '1px solid #1e4634' : '1px solid #e5e7eb',
                        backgroundColor: isSelected ? '#eef5f1' : '#ffffff',
                        color: isSelected ? '#1e4634' : '#6b7280',
                        transition: 'all 0.15s ease-in-out',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <span>{isSelected ? '✓' : '+'}</span>
                      <span>{type}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Preference: Workload Pace */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                Semester Workload Pace:
              </label>
              <select
                value={workloadPace}
                onChange={(e) => setWorkloadPace(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb',
                  backgroundColor: '#ffffff',
                  fontSize: '13.5px',
                }}
              >
                {WORKLOAD_PACES.map((pace) => (
                  <option key={pace} value={pace}>
                    {pace}
                  </option>
                ))}
              </select>
            </div>

            {/* Preference: Target Graduation Semester */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13.5px', fontWeight: 600, color: '#374151', marginBottom: '6px' }}>
                Target Graduation Semester:
              </label>
              <input
                type="text"
                value={targetGraduation}
                onChange={(e) => setTargetGraduation(e.target.value)}
                placeholder="e.g. Spring 2028 or May 2026"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb',
                  backgroundColor: '#ffffff',
                  fontSize: '13.5px',
                }}
              />
            </div>

            {/* Preference: Summer Courses Checkbox */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                id="summer-checkbox"
                type="checkbox"
                checked={willingSummer}
                onChange={(e) => setWillingSummer(e.target.checked)}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: '#1e4634',
                  cursor: 'pointer',
                }}
              />
              <label htmlFor="summer-checkbox" style={{ fontSize: '13.5px', color: '#4b5563', cursor: 'pointer' }}>
                Open to taking Summer semester courses for credit acceleration
              </label>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '15px 24px',
              borderRadius: '9999px',
              fontSize: '16px',
              fontWeight: 600,
              border: 'none',
              cursor: isFormValid ? 'pointer' : 'default',
              backgroundColor: isFormValid ? '#1e4634' : '#c1d7cc',
              color: isFormValid ? '#ffffff' : '#4e6b5e',
              transition: 'all 0.2s',
            }}
          >
            {loading ? 'Adding Student...' : 'Add'}
          </button>
        </form>
      </main>
    </div>
  );
}

