#  OmniKavach: Agentic ICU Diagnostic Assistant

> **Built for the Ignisia 24-Hour National Level AI Hackathon at MIT World Peace University.**

##  The Problem: The ICU Data Bottleneck
In fast-paced ICU environments, patient deterioration is often missed not because data is lacking, but because it is fragmented. Shifting lab results, unstructured clinical notes, and continuous vitals overwhelm the cognitive capacity of on-shift clinicians. Delayed intervention in these environments costs lives.

##  Our Solution
**OmniKavach** is a multi-agent orchestration platform that processes temporal clinical data in parallel. It acts as an autonomous clinical shield that ingests complex ICU histories, maps disease progression chronologically, and cross-references patterns against medical guidelines to generate actionable, safety-first Diagnostic Risk Reports.

## Demo Features

- Doctor/admin sign-in for protected clinical workflows
- Typed notes, report upload, and clinical photo ingestion
- AI diagnostic synthesis for clinicians
- Family Communication mode with plain-language English + Hindi summaries
- Statistical outlier guardrails that hold diagnosis revision pending redraw

## Demo Run

From the project root:

```powershell
npm run demo:start
```

Then open:

```text
http://127.0.0.1:5173/login
```

Demo accounts:

```text
admin@omnikavach.local / Admin@123
doctor@omnikavach.local / Doctor@123
```

To stop the demo:

```powershell
npm run demo:stop
```

---

##  Core Architecture (The Agentic Pipeline)

Our system leverages a multi-agent LLM pipeline, with each agent assigned a strictly defined, non-overlapping clinical role:

1. **The Note Parser Agent** Extracts critical symptom histories and behavioral observations from messy, unstructured nursing and physician notes.
2. **The Temporal Lab Mapper** Ingests raw vitals and lab anomalies (WBC counts, lactate levels), mapping them into a unified chronological timeline to visualize disease trajectory.
3. **The Medical RAG Agent** Cross-references identified clinical patterns against a curated vector database of established medical guidelines (e.g., MIMIC-III Sepsis Protocols), ensuring all AI inferences are backed by cited medical literature.
4. **The Chief Synthesis Agent & Outlier Detector** Integrates all agent outputs into a final Diagnostic Risk Report.
   
**Safety First:** Includes a statistical outlier detection module. If a new lab result contradicts previous temporal data, the system flags it as a *probable lab error* and pauses the diagnostic calculation pending a confirmed redraw, preventing false panics.
