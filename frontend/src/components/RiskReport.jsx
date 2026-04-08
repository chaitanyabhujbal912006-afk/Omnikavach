import { ShieldAlert, BookOpen, Bot, CheckCircle2, AlertTriangle, XCircle, ClipboardList } from 'lucide-react';

const SEVERITY = {
  critical: {
    bar: 'bg-red-500',
    text: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20',
  },
  warning: {
    bar: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20',
  },
};

const SOURCE_COLORS = {
  protocol: 'text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-500/10 border-cyan-200 dark:border-cyan-500/20',
  dataset: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 border-violet-200 dark:border-violet-500/20',
  guideline: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20',
};

const AGENT_ICONS = {
  complete: <CheckCircle2 className="w-3 h-3 text-emerald-500 dark:text-emerald-400" />,
  flagged: <AlertTriangle className="w-3 h-3 text-amber-500 dark:text-amber-400" />,
  error: <XCircle className="w-3 h-3 text-red-500 dark:text-red-400" />,
};

export default function RiskReport({ synthesis, riskScore }) {
  if (!synthesis) return null;

  const riskColor = riskScore >= 75 ? 'text-red-600 dark:text-red-400' : riskScore >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400';
  const riskBar = riskScore >= 75 ? 'bg-red-500' : riskScore >= 50 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/40 rounded-2xl p-3 flex gap-3 shadow-sm dark:shadow-none">
        <ShieldAlert className="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-red-600 dark:text-red-400 text-[11px] font-bold uppercase tracking-wider mb-0.5">
            Decision Support Only
          </p>
          <p className="text-red-500/70 dark:text-red-300/70 text-[10px] leading-relaxed">
            Not a clinical diagnosis. All AI-generated outputs must be reviewed and validated by a licensed
            clinician before influencing any medical decision.
          </p>
        </div>
      </div>

      <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
        <div className="flex items-center justify-between mb-2">
          <p className="section-label">AI Composite Risk Score</p>
          <span className={`text-2xl font-black font-mono ${riskColor}`}>{riskScore}%</span>
        </div>
        <div className="h-2 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${riskBar}`}
            style={{ width: `${riskScore}%` }}
          />
        </div>
      </div>

      <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-2 mb-3">
          <Bot className="w-4 h-4 text-blue-600 dark:text-cyan-400" />
          <p className="section-label">Chief Agent Synthesis</p>
        </div>
        <p className="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed">{synthesis.chiefSummary}</p>
      </div>

      {synthesis.handoverSummary?.length > 0 && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <div className="mb-3 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
            <p className="section-label">Shift Handover</p>
          </div>
          <div className="space-y-2">
            {synthesis.handoverSummary.map((bullet, index) => (
              <div
                key={index}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] leading-relaxed text-slate-700 dark:border-slate-700/50 dark:bg-slate-900/25 dark:text-slate-300"
              >
                {bullet}
              </div>
            ))}
          </div>
        </div>
      )}

      {synthesis.outlierAlert?.isProbableLabError && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm dark:border-amber-500/20 dark:bg-amber-500/10 dark:shadow-none">
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-300" />
            <p className="section-label text-amber-700 dark:text-amber-300">Probable Lab Error Hold</p>
          </div>
          <p className="text-[11px] leading-relaxed text-amber-700/90 dark:text-amber-100/80">
            {synthesis.outlierAlert.message}
          </p>
          <p className="mt-2 text-[11px] font-medium text-amber-800 dark:text-amber-200">
            {synthesis.outlierAlert.actionRequired}
          </p>
        </div>
      )}

      {synthesis.riskFactors?.length > 0 && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <p className="section-label mb-3">Risk Factors Identified</p>
          <div className="space-y-2">
            {synthesis.riskFactors.map((rf, i) => {
              const s = SEVERITY[rf.severity];
              return (
                <div key={i} className={`flex items-center gap-2.5 border rounded-xl px-3 py-2 ${s.bg}`}>
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.bar}`} />
                  <span className={`text-[11px] font-medium ${s.text}`}>{rf.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {synthesis.guidelinesReferenced?.length > 0 && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-blue-600 dark:text-cyan-400" />
            <p className="section-label">Guidelines Referenced</p>
            <span className="ml-auto text-[9px] text-blue-500 dark:text-cyan-500 font-mono">Medical RAG</span>
          </div>
          <div className="space-y-2">
            {synthesis.guidelinesReferenced.map((g, i) => {
              const c = SOURCE_COLORS[g.type] ?? SOURCE_COLORS.guideline;
              return (
                <div key={i} className="flex items-start gap-2.5 py-2 border-b border-slate-100 dark:border-slate-700/30 last:border-0">
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider flex-shrink-0 mt-0.5 ${c}`}>
                    {g.type}
                  </span>
                  <div>
                    <p className="text-slate-800 dark:text-slate-200 text-[11px] font-medium leading-tight">{g.name}</p>
                    <p className="text-slate-400 dark:text-slate-500 text-[10px] mt-0.5">{g.source}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {synthesis.agentTrace?.length > 0 && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <p className="section-label mb-3">Agent Execution Trace</p>
          <div className="space-y-1.5">
            {synthesis.agentTrace.map((a, i) => (
              <div key={i} className="flex items-center gap-2.5">
                {AGENT_ICONS[a.status] ?? AGENT_ICONS.complete}
                <span className="text-[11px] font-mono text-slate-700 dark:text-slate-300 w-40">{a.agent}</span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate">{a.output}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
