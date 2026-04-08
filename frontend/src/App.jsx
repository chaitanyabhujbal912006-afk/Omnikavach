import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import NavBar from './components/NavBar';
import ProtectedRoute from './components/ProtectedRoute';
import WardDashboard from './pages/WardDashboard';
import PatientDetail from './pages/PatientDetail';
import LoginPage from './pages/LoginPage';

function AppShell() {
  const location = useLocation();
  const isLoginRoute = location.pathname === '/login';

  return (
    <div className={`flex h-screen flex-col overflow-hidden ${isLoginRoute ? '' : 'px-3 py-3 sm:px-4 sm:py-4'}`}>
      {!isLoginRoute && <NavBar />}
      <main className={isLoginRoute ? 'flex-1 overflow-auto' : 'dashboard-shell flex-1 overflow-hidden min-h-0'}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={(
              <ProtectedRoute>
                <WardDashboard />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/patient/:id"
            element={(
              <ProtectedRoute>
                <PatientDetail />
              </ProtectedRoute>
            )}
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}

export default App;
