// src/App.js
import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// Lazy load components
const Dashboard = lazy(() => import('./components/Dashboard/Dashboard'));
const Requests = lazy(() => import('./components/Requests/RequestsList'));
const RequestDetail = lazy(() => import('./components/Requests/RequestDetail'));
const Anomalies = lazy(() => import('./components/Anomalies/AnomaliesList'));
const AnomalyDetail = lazy(() => import('./components/Anomalies/AnomalyDetail'));
const Analytics = lazy(() => import('./components/Analytics/AnalyticsPage'));
const Settings = lazy(() => import('./components/Settings/Settings'));
const NotFound = lazy(() => import('./components/common/NotFound'));
const LoadingSpinner = lazy(() => import('./components/common/LoadingSpinner'));

// API Configuration
const API_URL = process.env.REACT_APP_API_URL;
const API_KEY = process.env.REACT_APP_API_KEY;

if (!API_URL || !API_KEY) {
  throw new Error('Missing required environment variables: REACT_APP_API_URL and REACT_APP_API_KEY must be set');
}

// Create axios instance with retry logic
const axiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  }
});

// Add retry interceptor
axiosInstance.interceptors.response.use(null, async (error) => {
  const { config } = error;
  if (!config || !config.retry) {
    return Promise.reject(error);
  }
  config.retry -= 1;
  const delayMs = config.retryDelay || 1000;
  await new Promise(resolve => setTimeout(resolve, delayMs));
  return axiosInstance(config);
});

// Export for use in other components
export { axiosInstance };

// Color palette for charts
export const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

// Main App component
function App() {
  return (
    <Router>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">
            <h1>LLM Monitor</h1>
          </div>
          <ul className="nav-links">
            <li>
              <Link to="/">Dashboard</Link>
            </li>
            <li>
              <Link to="/requests">Requests</Link>
            </li>
            <li>
              <Link to="/anomalies">Anomalies</Link>
            </li>
            <li>
              <Link to="/analytics">Analytics</Link>
            </li>
            <li>
              <Link to="/settings">Settings</Link>
            </li>
          </ul>
          <div className="nav-footer">
            <p>LLM Monitoring v0.1.0</p>
          </div>
        </nav>
        
        <main className="content">
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/requests" element={<Requests />} />
              <Route path="/requests/:requestId" element={<RequestDetail />} />
              <Route path="/anomalies" element={<Anomalies />} />
              <Route path="/anomalies/:anomalyId" element={<AnomalyDetail />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/404" element={<NotFound />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </Router>
  );
}

export default App;
