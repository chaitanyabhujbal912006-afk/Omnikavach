# OmniKavach Hackathon Demo Pack

## Quick Start

From the project root:

```powershell
npm run demo:start
```

Open:

```text
http://127.0.0.1:5173/login
```

Demo accounts:

```text
admin@omnikavach.local / Admin@123
doctor@omnikavach.local / Doctor@123
```

Stop the demo:

```powershell
npm run demo:stop
```

## 2-Minute Pitch

OmniKavach is an ICU decision-support platform built to reduce clinical delay caused by fragmented data. In a real ICU, vitals, labs, nursing notes, and external reports often live in separate places, making it hard to detect deterioration quickly and safely.

Our system brings those inputs together into one agentic workflow. It parses unstructured notes, organizes temporal lab trends, generates a diagnostic risk view for clinicians, and produces a family-friendly explanation in plain language. It also includes a safety-first outlier detector that refuses to silently revise the diagnosis when a contradictory lab result appears likely to be an error.

The result is a prototype that helps clinicians act faster, communicate better, and avoid dangerous false alarms.

## Demo Flow

1. Sign in as doctor or admin.
2. Show the ward dashboard and explain that patients are ranked by risk.
3. Open one patient and show the three panels:
   - note parser feed
   - temporal trajectory
   - AI synthesis
4. Type a new bedside note.
5. Upload a report or clinical photo.
6. Delete an unnecessary uploaded note and explain that removed notes no longer affect future analysis.
7. Run `Agent Analysis`.
8. Show the clinical synthesis tab.
9. Switch to `Family Communication` and show English + Hindi summaries.
10. Point out the outlier safety logic: if a lab result sharply contradicts prior days of stable data, the system flags probable lab error and holds diagnosis revision pending redraw.

## Judge Highlights

- Multi-input ingestion: typed notes, device uploads, and photos.
- Safety layer: outlier hold instead of silent hallucinated diagnosis updates.
- Dual audience output: clinician-facing risk synthesis and family-facing explanation.
- Authentication: doctor/admin login for protected flows.
- Real workflow feel: dashboard, patient detail, live note management, and report ingestion.

## Crisp Answers

### What problem are you solving?
ICU deterioration is often missed because the data is fragmented and cognitively expensive to assemble quickly.

### Why is this different from a normal dashboard?
It is not only visualizing data. It interprets unstructured notes, reasons over temporal change, generates actionable synthesis, and adds a family communication layer.

### What makes it safe?
We explicitly flag probable lab errors, avoid silently incorporating anomalous values, and present the output as decision support rather than autonomous diagnosis.

### Is this production ready?
No. This is a hackathon prototype designed to demonstrate workflow, safety concepts, and human-centered communication.

### What would you build next?
- stronger OCR for scanned PDFs
- real hospital auth and audit logs
- multilingual support beyond Hindi
- clinician approval workflow before family communication is shared
- stronger provenance/citation for every generated conclusion
