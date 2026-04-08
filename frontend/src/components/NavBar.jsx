import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, ChevronRight, Wifi, Bell, Shield, Clock, Sun, Moon, LogOut, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function NavBar() {
  const [time, setTime] = useState(new Date());
  const location = useLocation();
  const navigate = useNavigate();
  const isDetail = location.pathname.startsWith('/patient/');
  const { isDark, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <nav className="glass-panel flex-shrink-0 h-16 rounded-[24px] px-4 sm:px-5 flex items-center justify-between gap-4 z-50 mb-3">
      {/* Brand + Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="relative">
          <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-cyan-500/15 border border-blue-200 dark:border-cyan-500/30 flex items-center justify-center shadow-sm dark:shadow-none">
            <Activity className="w-4 h-4 text-blue-600 dark:text-cyan-400" />
          </div>
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
        </div>
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="text-slate-900 dark:text-white font-bold text-sm tracking-[0.18em] uppercase">OmniKavach</span>
          <span className="text-slate-400 dark:text-slate-600 text-[10px] font-mono">v1.0</span>
        </div>

        {isDetail && (
          <div className="hidden lg:flex items-center gap-1.5 ml-3 text-[11px] text-slate-400 dark:text-slate-500">
            <ChevronRight className="w-3 h-3" />
            <Link to="/" className="hover:text-blue-600 dark:hover:text-cyan-400 transition-colors cursor-pointer">ICU Ward</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-slate-600 dark:text-slate-300">Patient Detail</span>
          </div>
        )}
      </div>

      {/* Centre: System status */}
      <div className="hidden md:flex items-center gap-3 lg:gap-5">
        <div className="flex items-center gap-1.5 rounded-full px-2.5 py-1 bg-white/60 dark:bg-slate-900/35 border border-white/70 dark:border-slate-700/40">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">6 Agents Online</span>
        </div>
        <div className="h-3 w-px bg-slate-200 dark:bg-slate-700" />
        <div className="flex items-center gap-1.5 rounded-full px-2.5 py-1 bg-white/60 dark:bg-slate-900/35 border border-white/70 dark:border-slate-700/40">
          <Wifi className="w-3 h-3 text-blue-500 dark:text-cyan-500" />
          <span className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">API Connected</span>
        </div>
        <div className="h-3 w-px bg-slate-200 dark:bg-slate-700" />
        <div className="hidden lg:flex items-center gap-1.5 rounded-full px-2.5 py-1 bg-white/60 dark:bg-slate-900/35 border border-white/70 dark:border-slate-700/40">
          <Shield className="w-3 h-3 text-slate-300 dark:text-slate-600" />
          <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">HIPAA Compliant</span>
        </div>
      </div>

      {/* Right: Theme toggle + Alerts + Clock */}
      <div className="flex items-center gap-3">
        {user && (
          <div className="hidden lg:flex items-center gap-3 rounded-2xl border border-white/70 bg-white/65 px-3 py-2 shadow-sm dark:border-slate-700/50 dark:bg-slate-900/35">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-cyan-500/15 dark:text-cyan-300">
              <UserRound className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <p className="text-xs font-semibold text-slate-800 dark:text-white">{user.name}</p>
              <p className="text-[10px] uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">{user.role}</p>
            </div>
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-500 transition-colors hover:text-blue-600 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-300 dark:hover:text-cyan-400"
            >
              <LogOut className="h-3.5 w-3.5" />
              Logout
            </button>
          </div>
        )}

        {/* Theme Toggle */}
        <button
          id="btn-theme-toggle"
          onClick={toggleTheme}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          className="relative w-14 h-7 rounded-full p-0.5 transition-colors duration-300
            bg-slate-200 dark:bg-slate-700 border border-slate-300 dark:border-slate-600
            hover:border-blue-300 dark:hover:border-cyan-500/50"
        >
          {/* Track icons */}
          <Sun  className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-amber-400 dark:text-slate-600 transition-colors" />
          <Moon className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 dark:text-cyan-400 transition-colors" />
          {/* Knob */}
          <div
            className={`w-6 h-6 rounded-full bg-white dark:bg-slate-800 shadow-md
              border border-slate-300 dark:border-slate-500
              transition-transform duration-300 ease-in-out
              ${isDark ? 'translate-x-7' : 'translate-x-0'}`}
          />
        </button>

        <div className="h-4 w-px bg-slate-200 dark:bg-slate-700" />

        <button className="relative p-1.5 rounded-xl hover:bg-slate-100/80 dark:hover:bg-slate-800/80 transition-colors">
          <Bell className="w-4 h-4 text-slate-500 dark:text-slate-400" />
          <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
        </button>
        <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono rounded-full px-2.5 py-1 bg-white/60 dark:bg-slate-900/35 border border-white/70 dark:border-slate-700/40">
          <Clock className="w-3 h-3 text-slate-400 dark:text-slate-500" />
          <span className="text-slate-700 dark:text-slate-200 tabular-nums">
            {time.toLocaleTimeString('en-IN', { hour12: false })}
          </span>
          <span className="text-slate-400 dark:text-slate-600">
            {time.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
          </span>
        </div>
      </div>
    </nav>
  );
}
