import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/layout/Layout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import IncidentList from './pages/IncidentList'
import IncidentDetail from './pages/IncidentDetail'
import AlertsPage from './pages/AlertsPage'
import LiveFeed from './pages/LiveFeed'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/*" element={
                <Layout>
                  <Routes>
                    <Route path="/incidents" element={<IncidentList />} />
                    <Route path="/incidents/:id" element={<IncidentDetail />} />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/live" element={<LiveFeed />} />
                    <Route path="/settings" element={<SettingsPage />} />
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
