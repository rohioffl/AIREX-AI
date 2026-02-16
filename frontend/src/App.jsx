import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/layout/Layout'
import LoginPage from './pages/LoginPage'
import IncidentList from './pages/IncidentList'
import IncidentDetail from './pages/IncidentDetail'
import AlertsPage from './pages/AlertsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/*" element={
                <Layout>
                  <Routes>
                    <Route path="/" element={<Navigate to="/incidents" replace />} />
                    <Route path="/incidents" element={<IncidentList />} />
                    <Route path="/incidents/:id" element={<IncidentDetail />} />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/live" element={<PlaceholderPage title="Live Feed" />} />
                    <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
                  </Routes>
                </Layout>
              } />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

function PlaceholderPage({ title }) {
  return (
    <div className="flex flex-col items-center justify-center py-32 animate-fade-in">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 glass" style={{ color: 'var(--text-muted)' }}>
        <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
      </div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h2>
      <p style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 4 }}>Coming soon.</p>
    </div>
  )
}
