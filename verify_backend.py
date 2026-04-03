import requests
import os
import glob
from pathlib import Path

# ANSI Color Codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
BOLD = '\033[1m'

def print_result(test_name, passed, details=""):
    if passed:
        print(f"[{GREEN}PASS{RESET}] {test_name} {details}")
    else:
        print(f"[{RED}FAIL{RESET}] {test_name} {details}")

def main():
    print(f"\n{BOLD}{BLUE}=== OmniKavach Backend Rapid Validation & Handoff Script ==={RESET}\n")

    BASE_URL = "http://localhost:8000"

    print(f"{BOLD}1. API Routing & Server Setup Checks{RESET}")
    
    # Task 1 & 3: GET /patients
    try:
        res = requests.get(f"{BASE_URL}/patients", timeout=5)
        passed = (res.status_code == 200) and isinstance(res.json(), list)
        print_result("GET /patients (Expected: 200 OK & List)", passed, f"- Status: {res.status_code}")
    except Exception as e:
        print_result("GET /patients (Expected: 200 OK & List)", False, f"- Error: {e}")

    # Task 1 & 3: POST /analyze/P-101
    try:
        res = requests.post(f"{BASE_URL}/analyze/P-101", timeout=5)
        passed = (res.status_code == 200)
        print_result("POST /analyze/P-101 (Mock Analysis)", passed, f"- Status: {res.status_code}")
    except Exception as e:
        print_result("POST /analyze/P-101 (Mock Analysis)", False, f"- Error: {e}")

    print(f"\n{BOLD}2. Error Handling Checks{RESET}")
    
    # Task 4: POST /analyze/INVALID_ID
    try:
        res = requests.post(f"{BASE_URL}/analyze/INVALID_ID", timeout=5)
        passed = (res.status_code == 404)
        print_result("POST /analyze/INVALID_ID (Expected: 404 Not Found)", passed, f"- Status: {res.status_code}")
    except Exception as e:
        print_result("POST /analyze/INVALID_ID (Expected: 404 Not Found)", False, f"- Error: {e}")

    print(f"\n{BOLD}3. Data Validation Check (MIMIC-III Local Folder){RESET}")
    
    found_mimic = False
    mimic_path = None
    
    # Search for folder with case-insensitive partial match
    for item in os.listdir('.'):
        if os.path.isdir(item) and "mimic iii v1.4" in item.lower():
            found_mimic = True
            mimic_path = item
            break
            
    if found_mimic:
        csv_files = glob.glob(os.path.join(mimic_path, "*.csv"))
        print_result("MIMIC-III Directory Found", True, f"({mimic_path})")
        print(f"       Found {len(csv_files)} .csv file(s) in the directory.")
        # List first few files to prove access
        for f in csv_files[:5]:
            print(f"       - {os.path.basename(f)}")
        if len(csv_files) > 5:
            print(f"       ... and {len(csv_files) - 5} more.")
    else:
        print_result("MIMIC-III Directory Found", False, "(Expected partial match for 'MIMIC III v1.4')")

    print(f"\n{BOLD}4. Member 3 AI Integration Handoff Check{RESET}")
    
    # Check if a placeholder file for Member 3's code exists
    ai_files = ['ai_engine.py', 'services/ai_pipeline.py', 'ai_pipeline.py']
    found_ai_file = any(os.path.exists(f) for f in ai_files)
    
    existing_file = next((f for f in ai_files if os.path.exists(f)), None)
    if found_ai_file:
        print_result("AI Integration Placeholder File", True, f"(Found {existing_file})")
    else:
        print_result("AI Integration Placeholder File", False, f"(Checked for {', '.join(ai_files)})")

    # AI Pipeline Integration Handoff Guide
    print(f"\n{YELLOW}===================================================================={RESET}")
    print(f"{YELLOW}          AI Pipeline Integration Handoff Guide for Member 3        {RESET}")
    print(f"{YELLOW}===================================================================={RESET}")
    print(f"""
{BOLD}Overview:{RESET} 
This guide details the integration point between the backend API 
and your AI analytical pipeline.

{BOLD}1. INPUT DELIVERED TO YOU:{RESET}
   The backend route will invoke your service function and pass 
   a single argument:
   
   - {GREEN}patient_id{RESET} (type: string)
     (e.g., "P-101")
   
   You will use this ID to query the MIMIC-III local data files 
   and execute your clinical analysis.

{BOLD}2. EXPECTED OUTPUT FROM YOUR PIPELINE:{RESET}
   Your pipeline must return a Python dictionary (or JSON object) 
   that EXACTLY matches the backend's AgentReport Pydantic schema:

   {{
       "risk_level": "High" | "Medium" | "Low",
       "flags": ["list", "of", "clinical", "flags", "as", "strings"],
       "guidelines_cited": ["Guideline 1", "Guideline 2"]
   }}
   
   {RED}CRITICAL:{RESET} Ensure the keys are named EXACTLY as above to 
   successfully pass the backend API validation.

{BOLD}Next Steps:{RESET}
- Start modifying the AI placeholder file.
- Verify your output against the AgentReport schema.
- Run this validation script again to ensure everything passes!
""")

if __name__ == "__main__":
    main()
