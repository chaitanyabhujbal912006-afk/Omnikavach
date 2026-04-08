import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="auth-panel max-w-sm rounded-[28px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-blue-600 dark:text-cyan-400" />
          <p className="text-sm text-slate-500 dark:text-slate-400">Restoring secure session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
