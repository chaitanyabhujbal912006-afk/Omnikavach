import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { addPatientNote, deletePatientNote, getPatientData, runAgentAnalysis, uploadPatientDocument } from '../services/api';
import FamilyCommunication from '../components/FamilyCommunication';
import PatientNote from '../components/PatientNote';
import PatientTimeline from '../components/PatientTimeline';
import RiskReport from '../components/RiskReport';
import {
  ArrowLeft, User, Cpu, CheckCircle2, Loader2, AlertTriangle,
  FileText, TrendingUp, Brain, Send, Upload, Camera, FileUp, MessageCircleMore,
} from 'lucide-react';

const STATUS_COLOR = {
  critical: 'text-red-600 dark:text-red-400',
  warning: 'text-amber-600 dark:text-amber-400',
  stable: 'text-emerald-600 dark:text-emerald-400',
};

export default function PatientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analysis, setAnalysis] = useState('idle');
  const [noteText, setNoteText] = useState('');
  const [noteCategory, setNoteCategory] = useState('Physician');
  const [uploadFile, setUploadFile] = useState(null);
  const [intakeState, setIntakeState] = useState({ status: 'idle', message: '' });
  const [deletingNoteId, setDeletingNoteId] = useState(null);
  const [activeInsightTab, setActiveInsightTab] = useState('clinical');

  const loadPatient = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPatientData(id);
      setPatient(res.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const refreshPatient = async () => {
    try {
      const res = await getPatientData(id);
      setPatient(res.data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadPatient();
  }, [id]);

  const handleAnalysis = async () => {
    setAnalysis('running');
    try {
      await runAgentAnalysis(id);
      await loadPatient();
      setAnalysis('complete');
    } catch {
      setAnalysis('idle');
    }
  };

  const handleTypedNoteSubmit = async (event) => {
    event.preventDefault();
    if (!noteText.trim()) return;

    setIntakeState({ status: 'saving', message: 'Saving typed note...' });
    try {
      await addPatientNote(id, {
        text: noteText.trim(),
        category: noteCategory,
      });
      setNoteText('');
      await refreshPatient();
      setIntakeState({ status: 'success', message: 'Typed note saved to the patient feed.' });
    } catch (err) {
      setIntakeState({ status: 'error', message: err.message || 'Unable to save note.' });
    }
  };

  const handleFileUpload = async () => {
    if (!uploadFile) return;

    setIntakeState({ status: 'saving', message: 'Uploading document for extraction...' });
    try {
      const res = await uploadPatientDocument(id, uploadFile);
      setUploadFile(null);
      await refreshPatient();
      setIntakeState({
        status: 'success',
        message: `${res.data.category || 'Document'} processed and added to the note parser feed.`,
      });
    } catch (err) {
      setIntakeState({ status: 'error', message: err.message || 'Unable to process upload.' });
    }
  };

  const handleDeleteNote = async (noteId) => {
    setDeletingNoteId(noteId);
    setIntakeState({ status: 'saving', message: 'Removing note from the analysis feed...' });
    try {
      await deletePatientNote(id, noteId);
      await refreshPatient();
      setIntakeState({ status: 'success', message: 'Note removed. Future analysis will ignore it.' });
    } catch (err) {
      setIntakeState({ status: 'error', message: err.message || 'Unable to delete note.' });
    } finally {
      setDeletingNoteId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full px-6">
        <div className="glass-panel rounded-3xl px-8 py-10 text-center">
          <Loader2 className="w-8 h-8 text-blue-500 dark:text-cyan-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-500 dark:text-slate-400 text-sm">Loading patient data...</p>
        </div>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="flex items-center justify-center h-full px-6">
        <div className="glass-panel rounded-3xl px-8 py-10 text-center">
          <AlertTriangle className="w-8 h-8 text-red-500 dark:text-red-400 mx-auto mb-3" />
          <p className="text-red-600 dark:text-red-400 font-semibold text-sm">Patient data unavailable</p>
          <button
            onClick={() => navigate('/')}
            className="mt-3 text-xs text-slate-400 hover:text-blue-600 dark:hover:text-cyan-400 transition-colors"
          >
            Return to Ward
          </button>
        </div>
      </div>
    );
  }

  const sc = STATUS_COLOR[patient.status];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 px-4 pt-4 pb-3 sm:px-6">
        <div className="glass-panel rounded-[24px] px-4 py-4 sm:px-5 sm:py-4 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3 min-w-0">
            <button
              onClick={() => navigate('/')}
              className="p-2 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all flex-shrink-0"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="w-10 h-10 rounded-2xl bg-slate-200 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-slate-500 dark:text-slate-400" />
            </div>
            <div className="min-w-0">
              <p className="section-label mb-1">Patient Focus View</p>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{patient.name}</h2>
                <span className={`text-[10px] font-mono font-bold ${sc}`}>Status {patient.status.toUpperCase()}</span>
              </div>
              <div className="flex items-center gap-x-2 gap-y-1 text-[10px] text-slate-400 dark:text-slate-500 font-mono flex-wrap mt-1">
                <span>{patient.bed}</span>
                <span>|</span>
                <span>{patient.age} yrs</span>
                <span>|</span>
                <span>{patient.mrn}</span>
                <span>|</span>
                <span>Admitted {patient.admitDate}</span>
                <span>|</span>
                <span>{patient.physician}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 xl:flex-shrink-0">
            <div className="hidden lg:flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-200/60 dark:bg-slate-700/40 border border-slate-300/60 dark:border-slate-600/40">
              <span className="text-[10px] text-slate-500 dark:text-slate-400">Condition</span>
              <span className="text-[10px] font-semibold text-slate-800 dark:text-white">{patient.condition}</span>
              <span className="ml-2 text-[10px] text-slate-400 dark:text-slate-500">Risk</span>
              <span className={`text-sm font-black font-mono ${sc}`}>{patient.riskScore}%</span>
            </div>

            <button
              id="btn-run-analysis"
              onClick={handleAnalysis}
              disabled={analysis === 'running'}
              className={`flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border transition-all
                ${analysis === 'complete'
                  ? 'bg-emerald-50 dark:bg-emerald-500/15 border-emerald-300 dark:border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
                  : analysis === 'running'
                  ? 'bg-blue-50 dark:bg-cyan-500/10 border-blue-200 dark:border-cyan-500/30 text-blue-500 dark:text-cyan-400 cursor-not-allowed'
                  : 'bg-blue-50 dark:bg-cyan-500/15 border-blue-200 dark:border-cyan-500/40 text-blue-600 dark:text-cyan-400 hover:bg-blue-100 dark:hover:bg-cyan-500/25'
                }`}
            >
              {analysis === 'running' && <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Running Agents...</>}
              {analysis === 'complete' && <><CheckCircle2 className="w-3.5 h-3.5" /> Analysis Complete</>}
              {analysis === 'idle' && <><Cpu className="w-3.5 h-3.5" /> Run Agent Analysis</>}
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 px-4 pb-4 sm:px-6 sm:pb-6">
        <div className="grid h-full min-h-0 grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="glass-panel rounded-[24px] min-h-[320px] overflow-hidden flex flex-col">
            <div className="col-header">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 dark:bg-cyan-400 flex-shrink-0" />
              <FileText className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
              <span className="col-header-title">Raw Feed | Note Parser</span>
              <span className="ml-auto text-[9px] font-mono text-slate-400 dark:text-slate-600">{patient.notes.length} notes</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="panel rounded-2xl p-4 shadow-sm dark:shadow-none">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="section-label mb-1">Intake Console</p>
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Add typed notes or upload reports</h3>
                  </div>
                  <div className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-blue-600 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-300">
                    Live Input
                  </div>
                </div>

                <form className="space-y-3" onSubmit={handleTypedNoteSubmit}>
                  <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
                    <textarea
                      value={noteText}
                      onChange={(event) => setNoteText(event.target.value)}
                      rows={5}
                      placeholder="Type bedside findings, assessment updates, medication response, or anything you want the note parser to consider..."
                      className="note-input min-h-[132px] resize-none"
                    />
                    <div className="space-y-3">
                      <select
                        value={noteCategory}
                        onChange={(event) => setNoteCategory(event.target.value)}
                        className="note-input h-11"
                      >
                        <option value="Physician">Physician</option>
                        <option value="Nursing">Nursing</option>
                        <option value="External Report">External Report</option>
                        <option value="Radiology">Radiology</option>
                        <option value="Lab Review">Lab Review</option>
                      </select>
                      <button
                        type="submit"
                        disabled={intakeState.status === 'saving' || !noteText.trim()}
                        className="note-action-primary"
                      >
                        {intakeState.status === 'saving' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        <span>Save Typed Note</span>
                      </button>
                    </div>
                  </div>
                </form>

                <div className="mt-4 rounded-2xl border border-dashed border-slate-300/80 bg-slate-50/80 p-4 dark:border-slate-700/70 dark:bg-slate-900/25">
                  <div className="mb-3 flex items-center gap-2">
                    <Upload className="h-4 w-4 text-amber-500" />
                    <p className="text-xs font-semibold text-slate-800 dark:text-white">Upload a report, scan, or clinical photo</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <label className="note-upload min-w-0">
                      <input
                        type="file"
                        accept=".pdf,.txt,image/*"
                        className="hidden"
                        onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
                      />
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-sm dark:bg-slate-950/40 dark:text-cyan-300">
                          {uploadFile?.type?.startsWith('image/') ? <Camera className="h-4 w-4" /> : <FileUp className="h-4 w-4" />}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800 dark:text-white">
                            {uploadFile ? uploadFile.name : 'Choose PDF, text report, or photo'}
                          </p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            Photos are OCR-extracted, PDFs are parsed, and the text is added to the note feed.
                          </p>
                        </div>
                      </div>
                    </label>
                    <button
                      type="button"
                      onClick={handleFileUpload}
                      disabled={intakeState.status === 'saving' || !uploadFile}
                      className="note-action-secondary w-full sm:w-auto"
                    >
                      {intakeState.status === 'saving' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                      <span>Upload</span>
                    </button>
                  </div>
                </div>

                {intakeState.message && (
                  <div
                    className={`mt-4 rounded-2xl border px-4 py-3 text-[11px] leading-relaxed ${
                      intakeState.status === 'error'
                        ? 'border-rose-200 bg-rose-50 text-rose-600 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300'
                        : intakeState.status === 'success'
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300'
                        : 'border-blue-200 bg-blue-50 text-blue-600 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-300'
                    }`}
                  >
                    {intakeState.message}
                  </div>
                )}
              </div>

              {patient.notes.map((note) => (
                <PatientNote
                  key={note.id}
                  note={note}
                  highlightedWords={patient.highlightedWords}
                  onDelete={handleDeleteNote}
                  deleting={deletingNoteId === note.id}
                />
              ))}
            </div>
          </div>

          <div className="glass-panel rounded-[24px] min-h-[320px] overflow-hidden flex flex-col">
            <div className="col-header">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 dark:bg-amber-400 flex-shrink-0" />
              <TrendingUp className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
              <span className="col-header-title">Temporal Trajectory | 72h</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <PatientTimeline data={patient.timeline} />
            </div>
          </div>

          <div className="glass-panel rounded-[24px] min-h-[320px] overflow-hidden flex flex-col">
            <div className="col-header">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 dark:bg-red-400 flex-shrink-0" />
              <Brain className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
              <span className="col-header-title">Diagnostic Synthesis | AI</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="mb-4 inline-flex rounded-2xl border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900/30 dark:shadow-none">
                <button
                  type="button"
                  onClick={() => setActiveInsightTab('clinical')}
                  className={`rounded-2xl px-4 py-2 text-xs font-semibold transition-colors ${
                    activeInsightTab === 'clinical'
                      ? 'bg-blue-600 text-white dark:bg-cyan-500 dark:text-slate-950'
                      : 'text-slate-500 hover:text-blue-600 dark:text-slate-400 dark:hover:text-cyan-300'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <Brain className="h-3.5 w-3.5" />
                    Clinical
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInsightTab('family')}
                  className={`rounded-2xl px-4 py-2 text-xs font-semibold transition-colors ${
                    activeInsightTab === 'family'
                      ? 'bg-pink-600 text-white dark:bg-pink-500 dark:text-white'
                      : 'text-slate-500 hover:text-pink-600 dark:text-slate-400 dark:hover:text-pink-300'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <MessageCircleMore className="h-3.5 w-3.5" />
                    Family Communication
                  </span>
                </button>
              </div>

              {activeInsightTab === 'clinical' ? (
                <RiskReport synthesis={patient.aiSynthesis} riskScore={patient.riskScore} />
              ) : (
                <FamilyCommunication
                  familyCommunication={patient.aiSynthesis?.familyCommunication}
                  patientId={patient.id}
                  patientName={patient.name}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
