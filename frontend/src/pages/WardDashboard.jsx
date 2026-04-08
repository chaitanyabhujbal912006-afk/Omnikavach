import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAllPatients } from '../services/api';
import { AlertTriangle, Activity, Users, Shield, RefreshCw, ChevronRight, MessageCircleMore } from 'lucide-react';

const STATUS = {
  critical: {
    dot: 'bg-red-500 animate-pulse',
    border: 'border-red-200 dark:border-red-500/25 hover:border-red-300 dark:hover:border-red-400/40',
    glow: 'dark:hover:shadow-glow-red',
    badge: 'badge-critical',
    label: 'Critical',
  },
  warning: {
    dot: 'bg-amber-500',
    border: 'border-amber-200 dark:border-amber-500/20 hover:border-amber-300 dark:hover:border-amber-400/40',
    glow: 'dark:hover:shadow-glow-amber',
    badge: 'badge-warning',
    label: 'Warning',
  },
  stable: {
    dot: 'bg-emerald-500',
    border: 'border-slate-200 dark:border-slate-700/50 hover:border-slate-300 dark:hover:border-slate-600/60',
    glow: '',
    badge: 'badge-stable',
    label: 'Stable',
  },
};

const riskColor = (s) => s >= 75 ? 'text-red-600 dark:text-red-400' : s >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400';
const riskBar = (s) => s >= 75 ? 'bg-red-500' : s >= 50 ? 'bg-amber-500' : 'bg-emerald-500';

function PatientCard({ patient, onClick }) {
  const cfg = STATUS[patient.status];

  return (
    <button
      onClick={() => onClick(patient.id)}
      className={`glass-panel w-full text-left rounded-2xl p-4 sm:p-5
        transition-all duration-200 group cursor-pointer animate-slide-up hover:-translate-y-1
        ${cfg.border} ${cfg.glow}`}
    >
      <div className="flex items-start justify-between mb-4 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
          <span className="text-[11px] font-mono font-medium text-slate-400 dark:text-slate-500 tracking-[0.2em] uppercase">
            {patient.bed}
          </span>
        </div>
        <span className={cfg.badge}>
          {cfg.label}
        </span>
      </div>

      <div className="mb-4">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-cyan-300 transition-colors mb-1">
          {patient.name}
        </h3>
        <p className="text-[11px] text-slate-500 dark:text-slate-400">{patient.age} yrs | {patient.condition}</p>
      </div>

      <div className="space-y-1.5">
        <div className="flex justify-between items-center">
          <span className="section-label">AI Risk Score</span>
          <span className={`text-xs font-black font-mono ${riskColor(patient.riskScore)}`}>
            {patient.riskScore}%
          </span>
        </div>
        <div className="h-2 w-full bg-slate-200/80 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${riskBar(patient.riskScore)}`}
            style={{ width: `${patient.riskScore}%` }}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-end gap-1 text-[10px] text-slate-400 dark:text-slate-600 group-hover:text-blue-500 dark:group-hover:text-cyan-500 transition-colors">
        View Detail <ChevronRight className="w-3 h-3" />
      </div>
    </button>
  );
}

function FamilyCard({ patient, onClick }) {
  const family = patient.familyCommunication;
  const previewTranslation = family?.translations?.[0]
    || (family?.regional
      ? {
          label: family.regionalLanguage || 'Hindi',
          text: family.regional,
        }
      : null);
  return (
    <button
      onClick={() => onClick(patient.id)}
      className="glass-panel w-full rounded-2xl p-5 text-left transition-all duration-200 hover:-translate-y-1"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">{patient.bed}</p>
          <h3 className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{patient.name}</h3>
        </div>
        <span className="rounded-full border border-pink-200 bg-pink-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-pink-600 dark:border-pink-500/20 dark:bg-pink-500/10 dark:text-pink-300">
          Family
        </span>
      </div>

      {family ? (
        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-200 bg-white/75 p-3 dark:border-slate-700/60 dark:bg-slate-950/20">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">English</p>
            <p className="max-h-[5.5rem] overflow-hidden text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">{family.english}</p>
          </div>
          {previewTranslation && (
            <div className="rounded-2xl border border-slate-200 bg-white/75 p-3 dark:border-slate-700/60 dark:bg-slate-950/20">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">{previewTranslation.label}</p>
              <p className="max-h-[4.5rem] overflow-hidden text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">{previewTranslation.text}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300/80 bg-slate-50/80 p-4 dark:border-slate-700/60 dark:bg-slate-900/20">
          <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
            Family communication will appear here after AI analysis is run for this patient.
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center justify-end gap-1 text-[10px] text-slate-400 transition-colors hover:text-pink-500 dark:text-slate-600 dark:hover:text-pink-300">
        Open Patient <ChevronRight className="h-3 w-3" />
      </div>
    </button>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className={`glass-panel rounded-2xl p-4 sm:p-5 ${color.border}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color.icon}`} />
        <span className={`text-[10px] font-bold uppercase tracking-[0.24em] ${color.icon}`}>{label}</span>
      </div>
      <div className="flex items-end justify-between gap-3">
        <span className={`text-3xl font-black ${color.value}`}>{value}</span>
        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">Live</span>
      </div>
    </div>
  );
}

export default function WardDashboard() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [activeTab, setActiveTab] = useState('clinical');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAllPatients();
      setPatients(res.data);
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  };

  useEffect(() => { load(); }, []);

  const counts = {
    critical: patients.filter((p) => p.status === 'critical').length,
    warning: patients.filter((p) => p.status === 'warning').length,
    stable: patients.filter((p) => p.status === 'stable').length,
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
      <div className="glass-panel rounded-[24px] p-5 sm:p-6 mb-6 overflow-hidden relative">
        <div className="absolute inset-y-0 right-0 w-40 bg-gradient-to-l from-blue-100/70 via-transparent to-transparent dark:from-cyan-500/10 pointer-events-none" />
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="section-label mb-2">Clinical Command Center</p>
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">ICU Ward</h1>
            <p className="text-slate-400 dark:text-slate-500 text-xs sm:text-sm mt-1">
              ICU Bay A and B{' '}
              <span className="font-mono text-slate-500 dark:text-slate-400">
                | Updated {lastRefresh.toLocaleTimeString('en-IN', { hour12: false })}
              </span>
            </p>
          </div>
          <button
            onClick={load}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl
              bg-white/85 dark:bg-slate-900/50 border border-white/80 dark:border-slate-700/50
              hover:border-blue-300 dark:hover:border-cyan-500/40
              text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-cyan-400
              text-xs transition-all shadow-sm dark:shadow-none"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="mb-6 inline-flex rounded-2xl border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900/30 dark:shadow-none">
        <button
          type="button"
          onClick={() => setActiveTab('clinical')}
          className={`rounded-2xl px-4 py-2 text-xs font-semibold transition-colors ${
            activeTab === 'clinical'
              ? 'bg-blue-600 text-white dark:bg-cyan-500 dark:text-slate-950'
              : 'text-slate-500 hover:text-blue-600 dark:text-slate-400 dark:hover:text-cyan-300'
          }`}
        >
          Clinical Dashboard
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('family')}
          className={`rounded-2xl px-4 py-2 text-xs font-semibold transition-colors ${
            activeTab === 'family'
              ? 'bg-pink-600 text-white dark:bg-pink-500'
              : 'text-slate-500 hover:text-pink-600 dark:text-slate-400 dark:hover:text-pink-300'
          }`}
        >
          <span className="inline-flex items-center gap-2">
            <MessageCircleMore className="h-3.5 w-3.5" />
            Family Communication
          </span>
        </button>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={Users}
          label="Total"
          value={patients.length}
          color={{ border: 'border-slate-200 dark:border-slate-700/50', icon: 'text-slate-400', value: 'text-slate-900 dark:text-white' }}
        />
        <StatCard
          icon={AlertTriangle}
          label="Critical"
          value={counts.critical}
          color={{ border: 'border-red-200 dark:border-red-500/20', icon: 'text-red-500 dark:text-red-400', value: 'text-red-600 dark:text-red-400' }}
        />
        <StatCard
          icon={Activity}
          label="Warning"
          value={counts.warning}
          color={{ border: 'border-amber-200 dark:border-amber-500/20', icon: 'text-amber-500 dark:text-amber-400', value: 'text-amber-600 dark:text-amber-400' }}
        />
        <StatCard
          icon={Shield}
          label="Stable"
          value={counts.stable}
          color={{ border: 'border-emerald-200 dark:border-emerald-500/20', icon: 'text-emerald-500 dark:text-emerald-400', value: 'text-emerald-600 dark:text-emerald-400' }}
        />
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-panel rounded-2xl p-4 animate-pulse space-y-3">
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/4" />
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-2/3" />
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/2" />
              <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded w-full" />
            </div>
          ))}
        </div>
      ) : activeTab === 'clinical' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
          {patients.map((p) => (
            <PatientCard key={p.id} patient={p} onClick={(patientId) => navigate(`/patient/${patientId}`)} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
          {patients.map((p) => (
            <FamilyCard key={p.id} patient={p} onClick={(patientId) => navigate(`/patient/${patientId}`)} />
          ))}
        </div>
      )}
    </div>
  );
}
