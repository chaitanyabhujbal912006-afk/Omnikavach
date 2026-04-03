import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv, dotenv_values
from tools import detect_lab_anomalies
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Fallback parser for .env files with BOM or non-standard formatting.
if not os.getenv("GROQ_API_KEY"):
    env_values = dotenv_values(ENV_PATH)
    for key, value in env_values.items():
        normalized_key = key.replace("\ufeff", "") if key else ""
        if normalized_key == "GROQ_API_KEY" and value:
            os.environ["GROQ_API_KEY"] = value.strip().strip('"').strip("'")
            break

# Backward compatibility: reuse existing GOOGLE_API_KEY slot if user stored Groq key there.
if not os.getenv("GROQ_API_KEY") and os.getenv("GOOGLE_API_KEY"):
    os.environ["GROQ_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Initialize the LLM
# Temperature 0 is critical for medical data to prevent hallucinations
if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file.")

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ==========================================
# 1. NOTE PARSER AGENT
# ==========================================
def run_note_parser(clinical_notes: str) -> str:
    """Extracts symptom history from unstructured text."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert ICU Clinical Note Parser. 
        Your sole job is to read messy, unstructured doctor and nurse notes and extract a chronological history of symptoms, critical events, and medical interventions.
        
        RULES:
        1. DO NOT diagnose the patient.
        2. ONLY extract facts, timelines, and symptoms.
        3. Format your output as a clear, structured list with timestamps/dates if available."""),
        
        ("user", "Here are the patient's recent clinical notes:\n\n{notes}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"notes": clinical_notes})
    return response.content

# Test block
if __name__ == "__main__":
    sample_note = "Patient admitted at 0800. Complains of chills. 1000: Nurse noted patient sweating profusely. BP dropping slightly."
    print("--- Note Parser Output ---")
    print(run_note_parser(sample_note))

# ==========================================
# 2. TEMPORAL LAB MAPPER AGENT
# ==========================================
def run_lab_mapper(lab_results: str) -> str:
    """Maps shifting lab anomalies into a chronological timeline."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Clinical Data Structurer. 
        Your job is to take raw, messy lab results and vitals over time and map them into a strict chronological timeline.
        
        RULES:
        1. Identify the timestamp/date for each lab reading.
        2. Group readings by time.
        3. Note the trend (e.g., 'WBC Count: 12.0 -> 15.5 (Trending Up)').
        4. Output as clean, structured markdown text. DO NOT diagnose."""),
        
        ("user", "Here are the raw lab results:\n\n{labs}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"labs": lab_results})
    return response.content

# Update your test block at the bottom to test both!
if __name__ == "__main__":
    # Test Note Parser
    sample_note = "Patient admitted at 0800. Complains of chills. 1000: Nurse noted patient sweating profusely. BP dropping slightly."
    print("--- Note Parser Output ---")
    print(run_note_parser(sample_note))
    
    # Test Lab Mapper
    sample_labs = "10/23 08:00 WBC 12.5, Lactate 1.2. 10/24 08:00 WBC 15.0, Lactate 2.4. 10/25 08:00 WBC 18.2, Lactate 4.1."
    print("\n--- Temporal Lab Mapper Output ---")
    print(run_lab_mapper(sample_labs))

# ==========================================
# 3. CHIEF ORCHESTRATOR AGENT
# ==========================================
def run_chief_agent(raw_notes: str, raw_labs_text: str, wbc_array: list[float]) -> str:
    """Orchestrates the entire pipeline and outputs a final JSON report."""
    
    # 1. Run the base agents (Parallel processing conceptually)
    parsed_notes = run_note_parser(raw_notes)
    mapped_labs = run_lab_mapper(raw_labs_text)
    
    # 2. Run the hardcoded math safety check
    wbc_flags = detect_lab_anomalies(wbc_array)
    is_wbc_dangerous = any(wbc_flags) # True if any value was flagged
    
    # 3. Chief Synthesis
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Chief ICU Diagnostic AI.
        Synthesize the patient history and labs into a Diagnostic Risk Report.
        
        RULES:
        1. If the Math Anomaly Detector says TRUE, you MUST include a severe warning in 'safety_caveat'.
        2. OUTPUT STRICTLY VALID JSON. No markdown blocks, just the JSON object.
        
        JSON SCHEMA:
        {{
            "timeline_summary": "Short 2 sentence summary",
            "key_risks": ["Risk 1", "Risk 2"],
            "safety_caveat": "Warning text or null"
        }}"""),
        
        ("user", "Parsed Notes:\n{notes}\n\nMapped Labs:\n{labs}\n\nMath Anomaly Detector (WBC Spike): {wbc_spike}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "notes": parsed_notes,
        "labs": mapped_labs,
        "wbc_spike": is_wbc_dangerous
    })
    
    # Clean up output in case the LLM wraps it in markdown like ```json ... ```
    return response.content.replace('```json', '').replace('```', '').strip()

# Update your test block!
if __name__ == "__main__":
    test_notes = "Patient admitted at 0800 complaining of chills. 1000: Sweating profusely, BP dropping."
    test_labs_text = "10/23 WBC 12.0. 10/24 WBC 12.5. 10/25 WBC 25.0."
    test_wbc_array = [12.0, 12.5, 25.0]
    
    print("--- GENERATING CHIEF REPORT... ---")
    final_report = run_chief_agent(test_notes, test_labs_text, test_wbc_array)
    print(final_report)