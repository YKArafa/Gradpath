/**
 * API client helper for Authentication (Sign in, Register, Token management)
 */

const API_BASE_URL = 'http://localhost:8000';

export async function loginUser(email, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Sign in failed. Please check your credentials.');
    }

    if (data.access_token) {
      localStorage.setItem('gradpath_token', data.access_token);
      localStorage.setItem('gradpath_advisor', JSON.stringify(data.advisor || {}));
    }
    return { success: true, data };
  } catch (err) {
    if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
      return {
        success: false,
        error: 'Unable to connect to the backend server at http://localhost:8000. Please ensure the backend is running.',
      };
    }
    return { success: false, error: err.message };
  }
}

export async function registerUser({ name, institution, email, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        institution,
        email,
        password,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Registration failed. Please check your details.');
    }

    if (data.access_token) {
      localStorage.setItem('gradpath_token', data.access_token);
      localStorage.setItem('gradpath_advisor', JSON.stringify(data.advisor || {}));
    }
    return { success: true, data };
  } catch (err) {
    if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
      return {
        success: false,
        error: 'Unable to connect to the backend server at http://localhost:8000. Please ensure the backend is running.',
      };
    }
    return { success: false, error: err.message };
  }
}

export function getCurrentUser() {
  try {
    const raw = localStorage.getItem('gradpath_advisor');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function logoutUser() {
  localStorage.removeItem('gradpath_token');
  localStorage.removeItem('gradpath_advisor');
}

