import { createContext, useContext, useEffect, useState } from 'react';
import { authStorage, getCurrentUser, loginUser } from '../services/api';

const AuthContext = createContext({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isAuthenticated: false,
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      const token = authStorage.getToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const res = await getCurrentUser();
        setUser(res.data);
      } catch {
        authStorage.clear();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    restoreSession();
  }, []);

  const login = async (credentials) => {
    const res = await loginUser(credentials);
    authStorage.setToken(res.data.access_token);
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    authStorage.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isAuthenticated: Boolean(user),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
