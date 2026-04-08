import { User, Clock, Trash2 } from 'lucide-react';

const ROLE_STYLES = {
  Attending:    'text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-500/10 border-cyan-200 dark:border-cyan-500/25',
  'ICU Nurse':  'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 border-violet-200 dark:border-violet-500/25',
  Nephrologist: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/25',
  Resident:     'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/25',
};

const FALLBACK_ROLE = 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700/50 border-slate-200 dark:border-slate-600/40';

/** Split text into plain/highlighted segments using a regex */
function buildSegments(text, words) {
  if (!words?.length) return [{ plain: true, content: text }];
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escaped.join('|')})`, 'gi');
  return text.split(regex).map((part, i) => ({
    plain: !words.some((w) => w.toLowerCase() === part.toLowerCase()),
    content: part,
    key: i,
  }));
}

export default function PatientNote({ note, highlightedWords = [], onDelete, deleting = false }) {
  const segments = buildSegments(note.text, highlightedWords);
  const roleStyle = ROLE_STYLES[note.role] ?? FALLBACK_ROLE;

  return (
    <div className="panel rounded-2xl p-4 hover:border-slate-300 dark:hover:border-slate-600/60 transition-colors animate-fade-in shadow-sm dark:shadow-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-2xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
            <User className="w-3.5 h-3.5 text-slate-400" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 leading-none mb-1">{note.author}</p>
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border uppercase tracking-wider ${roleStyle}`}>
              {note.role}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-slate-400 dark:text-slate-500">
          {note.canDelete && (
            <button
              type="button"
              onClick={() => onDelete?.(note.id)}
              disabled={deleting}
              className="mr-2 rounded-lg p-1 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500 disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
              title="Delete this uploaded note"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <Clock className="w-3 h-3" />
          <span className="text-[11px] font-mono">{note.time}</span>
        </div>
      </div>

      {/* Body with keyword highlights */}
      <p className="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed">
        {segments.map((seg) =>
          seg.plain ? (
            <span key={seg.key}>{seg.content}</span>
          ) : (
            <mark
              key={seg.key}
              className="bg-blue-100 dark:bg-cyan-500/20 text-blue-700 dark:text-cyan-300 border-b border-blue-300 dark:border-cyan-400/50 rounded-sm px-0.5 not-italic font-semibold"
            >
              {seg.content}
            </mark>
          )
        )}
      </p>
    </div>
  );
}
