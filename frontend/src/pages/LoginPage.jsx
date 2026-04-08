import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, LockKeyhole, ShieldCheck, Stethoscope, UserCog } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const demoAccounts = [
  {
    role: 'Admin',
    email: 'admin@omnikavach.local',
    password: 'Admin@123',
    icon: UserCog,
    accent: 'from-rose-500/20 to-orange-400/10 dark:from-rose-500/25 dark:to-orange-300/10',
  },
  {
    role: 'Doctor',
    email: 'doctor@omnikavach.local',
    password: 'Doctor@123',
    icon: Stethoscope,
    accent: 'from-cyan-500/20 to-emerald-400/10 dark:from-cyan-500/25 dark:to-emerald-300/10',
  },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [form, setForm] = useState({ email: demoAccounts[0].email, password: demoAccounts[0].password });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const destination = location.state?.from?.pathname || '/';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(form);
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.message || 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-6 sm:px-6">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[8%] top-[10%] h-56 w-56 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-500/20" />
        <div className="absolute bottom-[12%] right-[10%] h-64 w-64 rounded-full bg-orange-300/20 blur-3xl dark:bg-rose-500/15" />
        <div className="absolute inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.16),transparent_52%)] dark:bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.18),transparent_52%)]" />
      </div>

      <div className="relative mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl items-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="auth-panel overflow-hidden rounded-[32px] p-6 sm:p-8 lg:p-10">
            <div className="mb-10 flex items-start justify-between gap-4">
              <div>
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/60 bg-white/70 shadow-sm dark:border-slate-700/60 dark:bg-slate-900/40">
                    <Activity className="h-5 w-5 text-blue-600 dark:text-cyan-400" />
                  </div>
                  <div>
                    <p className="section-label mb-1">Restricted Clinical Access</p>
                    <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">
                      OmniKavach Command Login
                    </h1>
                  </div>
                </div>
                <p className="max-w-xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                  Sign in as an administrator or attending doctor to view the live ward, review AI synthesis, and manage protected clinical actions from one secure workspace.
                </p>
              </div>

              <button
                onClick={toggleTheme}
                className="rounded-2xl border border-white/70 bg-white/80 px-4 py-2 text-xs font-semibold text-slate-500 shadow-sm transition-colors hover:text-blue-600 dark:border-slate-700/60 dark:bg-slate-900/40 dark:text-slate-300 dark:hover:text-cyan-400"
              >
                {isDark ? 'Light Theme' : 'Night Theme'}
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {demoAccounts.map((account) => {
                const Icon = account.icon;
                return (
                  <button
                    key={account.role}
                    type="button"
                    onClick={() => setForm({ email: account.email, password: account.password })}
                    className={`group rounded-[24px] border border-white/60 bg-gradient-to-br ${account.accent} p-5 text-left shadow-sm transition-all hover:-translate-y-1 hover:border-blue-200 dark:border-slate-700/60 dark:hover:border-cyan-500/30`}
                  >
                    <div className="mb-4 flex items-center justify-between">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/75 text-slate-700 dark:bg-slate-950/40 dark:text-cyan-300">
                        <Icon className="h-4 w-4" />
                      </div>
                      <span className="rounded-full border border-white/70 bg-white/70 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-slate-500 dark:border-slate-700/60 dark:bg-slate-950/30 dark:text-slate-300">
                        {account.role}
                      </span>
                    </div>
                    <p className="mb-1 text-base font-semibold text-slate-900 dark:text-white">{account.email}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Tap to prefill the demo credentials and enter the protected clinical workspace.
                    </p>
                  </button>
                );
              })}
            </div>

            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/60 bg-white/65 p-4 dark:border-slate-700/60 dark:bg-slate-900/35">
                <ShieldCheck className="mb-3 h-4 w-4 text-emerald-500" />
                <p className="text-xs font-semibold text-slate-800 dark:text-white">Protected workflows</p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">Analysis, notes, and uploads now require authenticated doctor or admin access.</p>
              </div>
              <div className="rounded-2xl border border-white/60 bg-white/65 p-4 dark:border-slate-700/60 dark:bg-slate-900/35">
                <LockKeyhole className="mb-3 h-4 w-4 text-blue-500 dark:text-cyan-400" />
                <p className="text-xs font-semibold text-slate-800 dark:text-white">Session-based entry</p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">JWT-backed sessions are restored automatically while your token remains valid.</p>
              </div>
              <div className="rounded-2xl border border-white/60 bg-white/65 p-4 dark:border-slate-700/60 dark:bg-slate-900/35">
                <Activity className="mb-3 h-4 w-4 text-amber-500" />
                <p className="text-xs font-semibold text-slate-800 dark:text-white">Live ICU dashboard</p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">Once signed in, the ward and patient views load real backend data instead of mocks.</p>
              </div>
            </div>
          </section>

          <section className="auth-panel rounded-[32px] p-6 sm:p-8">
            <p className="section-label mb-3">Secure Access</p>
            <h2 className="mb-2 text-2xl font-black tracking-tight text-slate-900 dark:text-white">Doctor and admin sign-in</h2>
            <p className="mb-8 text-sm text-slate-500 dark:text-slate-400">
              Use one of the demo accounts or enter credentials manually.
            </p>

            <form className="space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Email</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                  className="auth-input"
                  placeholder="doctor@omnikavach.local"
                  autoComplete="username"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Password</span>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                  className="auth-input"
                  placeholder="Enter secure password"
                  autoComplete="current-password"
                />
              </label>

              {error && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="auth-submit"
              >
                <span>{loading ? 'Authorizing clinical access...' : 'Enter Command Center'}</span>
                <ArrowRight className={`h-4 w-4 ${loading ? 'animate-pulse' : ''}`} />
              </button>
            </form>

            <div className="mt-8 rounded-[24px] border border-dashed border-slate-300/80 bg-white/55 p-5 dark:border-slate-700/60 dark:bg-slate-950/20">
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">Demo Credentials</p>
              <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span>Admin</span>
                  <span className="font-mono text-xs">admin@omnikavach.local / Admin@123</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span>Doctor</span>
                  <span className="font-mono text-xs">doctor@omnikavach.local / Doctor@123</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
