import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from 'recharts';
import { AlertTriangle } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const unitByName = {
    Lactate: ' mmol/L',
    'Heart Rate': ' bpm',
    WBC: ' K/uL',
    Creatinine: ' mg/dL',
  };
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600/50 rounded-xl p-3 shadow-xl text-[11px]">
      <p className="text-slate-500 dark:text-slate-400 font-mono mb-2 border-b border-slate-200 dark:border-slate-700 pb-1">T + {label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: entry.color }} />
          <span className="text-slate-500 dark:text-slate-400">{entry.name}:</span>
          <span className="font-bold font-mono" style={{ color: entry.color }}>
            {entry.value}
            {unitByName[entry.name] || ''}
          </span>
        </div>
      ))}
    </div>
  );
};

const LactateDot = (props) => {
  const { cx, cy, payload } = props;
  if (payload.isOutlier) {
    return (
      <g key={`outlier-dot-${cx}`}>
        <circle cx={cx} cy={cy} r={16} fill="rgba(245,158,11,0.08)" stroke="rgba(245,158,11,0.25)" strokeWidth={1} />
        <circle cx={cx} cy={cy} r={8} fill="rgba(245,158,11,0.15)" stroke="#f59e0b" strokeWidth={1.5} />
        <circle cx={cx} cy={cy} r={4} fill="#f59e0b" />
        <text x={cx} y={cy - 24} textAnchor="middle" fill="#d97706" fontSize="9" fontWeight="700">
          OUTLIER
        </text>
      </g>
    );
  }
  return (
    <circle
      key={`dot-${cx}`}
      cx={cx}
      cy={cy}
      r={3}
      fill="#06b6d4"
      stroke="#0e7490"
      strokeWidth={1}
    />
  );
};

function EmptyMetricCard({ title, unit, message }) {
  return (
    <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">{title}</p>
        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">{unit} | 72h</span>
      </div>
      <div className="flex h-[160px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 text-center dark:border-slate-700 dark:bg-slate-900/25">
        <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">{message}</p>
      </div>
    </div>
  );
}

export default function PatientTimeline({ data }) {
  const { isDark } = useTheme();

  if (!data) return null;

  const chartData = data.labels.map((label, i) => ({
    time: label,
    lactate: data.lactate[i],
    heartRate: data.heartRate[i],
    wbc: data.wbc?.[i] ?? 0,
    creatinine: data.creatinine?.[i] ?? 0,
    isOutlier: i === data.lactateOutlierIndex,
  }));

  const hasOutlier = data.lactateOutlierIndex >= 0 && data.lactateOutlierIndex < data.lactate.length;
  const outlierValue = hasOutlier ? data.lactate[data.lactateOutlierIndex] : null;
  const outlierLabel = hasOutlier ? data.labels[data.lactateOutlierIndex] : null;

  // Check if we have any meaningful data
  const hasLactateData = data.lactate.some((v) => v > 0);
  const hasHRData = data.heartRate.some((v) => v > 0);
  const hasWBCData = (data.wbc || []).some((v) => v > 0);
  const hasCreatinineData = (data.creatinine || []).some((v) => v > 0);

  const gridStroke = isDark ? '#1e293b' : '#e2e8f0';
  const axisStroke = isDark ? '#334155' : '#cbd5e1';
  const tickFill = isDark ? '#64748b' : '#94a3b8';

  const sharedAxis = {
    tick: { fill: tickFill, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    axisLine: { stroke: axisStroke },
    tickLine: false,
  };

  const maxLactate = Math.max(...data.lactate.filter((v) => v > 0), 4);
  const maxHR = Math.max(...data.heartRate.filter((v) => v > 0), 100);
  const minWBC = hasWBCData ? Math.min(...data.wbc.filter((v) => v > 0)) : 4;
  const maxWBC = Math.max(...(data.wbc || []).filter((v) => v > 0), 12);
  const maxCreatinine = Math.max(...(data.creatinine || []).filter((v) => v > 0), 1.5);

  return (
    <div className="space-y-4">
      {/* Dynamic BS Detector Alert — only shows when an outlier is detected */}
      {hasOutlier && (
        <div className="bg-amber-50 dark:bg-amber-500/8 border border-amber-200 dark:border-amber-500/30 rounded-2xl p-3 flex gap-3 shadow-sm dark:shadow-none">
          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-700 dark:text-amber-400 text-[11px] font-bold mb-0.5">B.S. Detector | Lab Outlier Flagged</p>
            <p className="text-amber-600/70 dark:text-amber-200/60 text-[10px] leading-relaxed">
              Lactate of <span className="font-bold text-amber-700 dark:text-amber-400">{outlierValue} mmol/L</span> at T+{outlierLabel} is
              statistically anomalous. Probable hemolyzed sample or lab processing error.
              <strong className="text-amber-800 dark:text-amber-300"> Repeat STAT lactate recommended immediately.</strong>
            </p>
          </div>
        </div>
      )}

      {!hasLactateData && !hasHRData && !hasWBCData && !hasCreatinineData && (
        <div className="flex items-center justify-center h-32">
          <p className="text-slate-400 dark:text-slate-500 text-xs text-center">
            No timeline data available. This patient may not have vitals or lab trends recorded.
          </p>
        </div>
      )}

      {hasLactateData && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Serum Lactate</p>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">mmol/L | 72h</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData} margin={{ top: 20, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="time" {...sharedAxis} />
              <YAxis domain={[0, Math.ceil(maxLactate * 1.2)]} {...sharedAxis} />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine
                y={data.normalLactateMax}
                stroke="#10b981"
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                label={{ value: 'Normal Max', fill: '#10b981', fontSize: 9, position: 'insideTopRight' }}
              />
              <Line
                type="monotone"
                dataKey="lactate"
                name="Lactate"
                stroke="#06b6d4"
                strokeWidth={2}
                dot={<LactateDot />}
                activeDot={{ r: 5, fill: '#06b6d4' }}
              />
            </LineChart>
          </ResponsiveContainer>
          {hasOutlier && (
            <div className="mt-2 flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-[10px] text-amber-600 dark:text-amber-400/80 font-mono">Amber dot = Probable Lab Error (B.S. Detector)</span>
            </div>
          )}
        </div>
      )}

      {hasHRData && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Heart Rate</p>
            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">bpm | 72h</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="time" {...sharedAxis} />
              <YAxis domain={[Math.max(0, Math.floor(Math.min(...data.heartRate.filter(v => v > 0)) * 0.85)), Math.ceil(maxHR * 1.1)]} {...sharedAxis} />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine
                y={100}
                stroke="#f59e0b"
                strokeDasharray="4 4"
                strokeOpacity={0.4}
                label={{ value: 'Tachycardia', fill: '#f59e0b', fontSize: 9, position: 'insideTopRight' }}
              />
              <Line
                type="monotone"
                dataKey="heartRate"
                name="Heart Rate"
                stroke="#f43f5e"
                strokeWidth={2}
                dot={{ r: 3, fill: '#f43f5e', stroke: '#9f1239', strokeWidth: 1 }}
                activeDot={{ r: 5, fill: '#f43f5e' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {hasWBCData ? (
            <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">WBC Trend</p>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">K/uL | 72h</span>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="time" {...sharedAxis} />
                  <YAxis domain={[Math.max(0, Math.floor(minWBC * 0.8)), Math.ceil(maxWBC * 1.15)]} {...sharedAxis} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine
                    y={11}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                    strokeOpacity={0.4}
                    label={{ value: 'Upper Normal', fill: '#f59e0b', fontSize: 9, position: 'insideTopRight' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="wbc"
                    name="WBC"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#8b5cf6', stroke: '#6d28d9', strokeWidth: 1 }}
                    activeDot={{ r: 5, fill: '#8b5cf6' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyMetricCard
              title="WBC Trend"
              unit="K/uL"
              message="No WBC measurements were recorded for this patient in the current timeline window."
            />
          )}

          {hasCreatinineData ? (
            <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Creatinine Trend</p>
                <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">mg/dL | 72h</span>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="time" {...sharedAxis} />
                  <YAxis domain={[0, Math.ceil(maxCreatinine * 1.2)]} {...sharedAxis} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine
                    y={1.2}
                    stroke="#10b981"
                    strokeDasharray="4 4"
                    strokeOpacity={0.45}
                    label={{ value: 'Normal Max', fill: '#10b981', fontSize: 9, position: 'insideTopRight' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="creatinine"
                    name="Creatinine"
                    stroke="#14b8a6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#14b8a6', stroke: '#0f766e', strokeWidth: 1 }}
                    activeDot={{ r: 5, fill: '#14b8a6' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyMetricCard
              title="Creatinine Trend"
              unit="mg/dL"
              message="No creatinine measurements were recorded for this patient in the current timeline window."
            />
          )}
      </div>
    </div>
  );
}
