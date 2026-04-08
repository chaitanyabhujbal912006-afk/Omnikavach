import { useEffect, useState } from 'react';
import { HeartHandshake, Languages, Mail, MessageCircleMore, Send } from 'lucide-react';
import { sendFamilyCommunicationEmail } from '../services/api';

export default function FamilyCommunication({ familyCommunication, patientId, patientName }) {
  const [recipientEmail, setRecipientEmail] = useState('');
  const [status, setStatus] = useState({ kind: 'idle', message: '' });
  const [sending, setSending] = useState(false);
  const translations = familyCommunication?.translations?.length
    ? familyCommunication.translations
    : familyCommunication?.regional
    ? [
        {
          code: (familyCommunication.regionalLanguage || 'hi').slice(0, 2).toLowerCase(),
          label: familyCommunication.regionalLanguage || 'Hindi',
          text: familyCommunication.regional,
        },
      ]
    : [];
  const [selectedLanguageCode, setSelectedLanguageCode] = useState(translations[0]?.code || '');

  useEffect(() => {
    setSelectedLanguageCode(translations[0]?.code || '');
  }, [familyCommunication]);

  if (!familyCommunication) {
    return (
      <div className="panel rounded-2xl p-5 text-center shadow-sm dark:shadow-none">
        <MessageCircleMore className="mx-auto mb-3 h-5 w-5 text-slate-400 dark:text-slate-500" />
        <p className="text-sm font-semibold text-slate-800 dark:text-white">Family communication not ready yet</p>
        <p className="mt-2 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          Run agent analysis to generate a compassionate update that can be shared with family members.
        </p>
      </div>
    );
  }

  const handleSend = async () => {
    if (!recipientEmail.trim()) {
      setStatus({ kind: 'error', message: 'Enter a family email address first.' });
      return;
    }

    setSending(true);
    setStatus({ kind: 'info', message: 'Sending family communication email...' });

    try {
      await sendFamilyCommunicationEmail(patientId, recipientEmail.trim());
      setStatus({ kind: 'success', message: `Family update sent for ${patientName}.` });
      setRecipientEmail('');
    } catch (error) {
      setStatus({ kind: 'error', message: error.message || 'Unable to send email.' });
    } finally {
      setSending(false);
    }
  };

  const selectedTranslation =
    translations.find((translation) => translation.code === selectedLanguageCode) || translations[0] || null;

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="rounded-2xl border border-pink-200 bg-pink-50 p-4 shadow-sm dark:border-pink-500/20 dark:bg-pink-500/10 dark:shadow-none">
        <div className="mb-2 flex items-center gap-2">
          <HeartHandshake className="h-4 w-4 text-pink-600 dark:text-pink-300" />
          <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-pink-700 dark:text-pink-300">
            Family Communication
          </p>
        </div>
        <p className="text-[11px] leading-relaxed text-pink-700/90 dark:text-pink-100/80">
          This view is written for family members in plain language and should be used alongside direct clinician conversation.
        </p>
      </div>

      <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
        <div className="mb-3 flex items-center gap-2">
          <Mail className="h-4 w-4 text-blue-600 dark:text-cyan-400" />
          <p className="section-label">Send By Email</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            type="email"
            value={recipientEmail}
            onChange={(event) => setRecipientEmail(event.target.value)}
            placeholder="family@example.com"
            className="note-input h-11"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={sending}
            className="note-action-primary h-11 sm:w-[180px]"
          >
            {sending ? <Send className="h-4 w-4 animate-pulse" /> : <Send className="h-4 w-4" />}
            <span>Send Email</span>
          </button>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          Resend onboarding mode may only allow delivery to your verified account email until you verify a sender domain.
        </p>
        {status.message && (
          <div
            className={`mt-3 rounded-2xl border px-4 py-3 text-[11px] leading-relaxed ${
              status.kind === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300'
                : status.kind === 'error'
                ? 'border-rose-200 bg-rose-50 text-rose-600 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300'
                : 'border-blue-200 bg-blue-50 text-blue-600 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-300'
            }`}
          >
            {status.message}
          </div>
        )}
      </div>

      <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
        <div className="mb-3 flex items-center justify-between">
          <p className="section-label">English</p>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-mono text-slate-500 dark:border-slate-700 dark:bg-slate-900/30 dark:text-slate-400">
            {familyCommunication.updatedWindow}
          </span>
        </div>
        <p className="text-[12px] leading-relaxed text-slate-700 dark:text-slate-300">{familyCommunication.english}</p>
      </div>

      {selectedTranslation && (
        <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Languages className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <p className="section-label">Local Language</p>
            </div>
            <select
              value={selectedLanguageCode}
              onChange={(event) => setSelectedLanguageCode(event.target.value)}
              className="note-input h-11 min-w-[180px] appearance-none"
            >
              {translations.map((translation) => (
                <option key={translation.code} value={translation.code}>
                  {translation.label}
                </option>
              ))}
            </select>
          </div>
          <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
            {selectedTranslation.label}
          </p>
          <p className="text-[12px] leading-relaxed text-slate-700 dark:text-slate-300">{selectedTranslation.text}</p>
        </div>
      )}
    </div>
  );
}
