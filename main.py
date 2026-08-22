# =====================================================
# 1. ENVIRONMENT STEUP & DEPENDENCIES
# =====================================================

import os                       #USED FOR DIRECTORY SCANNING AND FILE PATH MANAGEMENT               
import re                       #IMPORTS PYTHON IN-BUILT "re" (REGULAR EXPRESSION) LIBRARY USED TO EXTRACT RAW CODE FROM AI TEXT
from google import genai        #GOOGLE GEMINI API CLIENT FOR AI TEXT GENERATION
from dotenv import load_dotenv  #SECURELY LOADS API KEYS FROM HIDDEN .ENV FILE 

#SECURELYY LOAD ENVIRONMENT VARIABLES FROM HIDDEN .ENV FILE 
#THIS ENSURES API KEYS ARE NEVER HARDCODED OR EXPOSED IN THE SOURCE CODE
load_dotenv()

#INITIALIZE THE GEMINI AI CLIENT INSTANCE
#IT AUTOMATICALLY DETECTS THE API KEY LOADED BY load_dontenv() TO AUTHENTICATE OUR CONNECTION
client = genai.Client()

#THIS DEFINE STANDARD DIRECTORY PATHS FOR THE BATCH PROCESSING PIPELINE
RTL_DIR = "rtl"             #INPUT FOLDER CONTAINING RAW VERILOG/SYSTEMVERILOG FILES
OUTPUT_DIR = "output_svas"  #OUTPUT FOLDER FOR THE GENERATED ASSERTIONS
SPECS_DIR = "specs"         #FOLDER CONTAINING PROTOCOL SPECIFICATIONS PDFs/TEXT FILES

#SAFETY CHECK: AUTOMATICALLY CREATE THE OUTPUT DIRECTORY IF IT DOESN'T EXIST TO PREVENT CRASHES
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

#=========================================================
# 2. THE AUTO-ROUTER ENGINE
#===========================================================

def detect_protocol(rtl_code):
    """PARSES RAW RTL CODE FOR INDUSTRY STANDARD SIGNAL NAMES TO AUTO-DETECT THE HARDWARE PROTOCOL."""
    code = rtl_code.upper()
    if "AWVALID" in code or "ARVALID" in code or "AWADDR" in code: # DETECT AMBA AXI SIGNALS (VALID/ADDRESS CHANNELS)
        return "axi"
    elif "HTRANS" in code or "HREADY" in code or "HADDR" in code:   # DETECT AMBA AHB SIGNALS (TRANSFER/READY/ADDRESS PHASES)
        return "ahb"
    elif "PSEL" in code or "PENABLE" in code: # DETECT AMBA APB SIGNALS (SELECT/ENABLE PINS)
        return "apb" 
    elif "WR_EN" in code or "RD_EN" in code or "FIFO_DATA" in code: # DETECT GENERIC SYNCHRONOUS/ASYNCHRONOUS FIFO INTERFACES
        return "fifo"
    return None

def find_spec_file(protocol_keyword):
    """SEARCHES THE SPECS DIRECTORY TO DYNAMICALLY LINK THE DETECTED PROTOCOL TO ITS OFFICIAL DOCUMENTATION."""
    # SAFETY CHECK TO ENSURE THE SPECS FORLDER EXISTS BEFORE SEARCHING
    if not os.path.exists(SPECS_DIR):
        print("Error: specs folder not found")
        return None
    # SCAN THE FOLDER FOR A PDF OR TEXT FILE THAT MATCHES THE DETECTED PROTOCOL NAME
    for filename in os.listdir(SPECS_DIR):
        if protocol_keyword in filename.lower():
            # CONSTRUCT AND RETURN THE FULL, SAFE PATH TO THE SPECIFICATION FILE
            return os.path.join(SPECS_DIR, filename)
    return None

#===============================================================
# 3. THE AUTO-HEALING ENGINE (LINTER & PARSER)
#===============================================================

def extract_code(ai_text):
    """STRIPS MARKDOWN FORMATTING FROM THE AI RESPONSE TO EXTRACT RAW, COMPILABLE CODE."""
    # USES REGEX TO FIND CODE BLOCKS MARKED BY '''SYSTEMVERILOG, '''SV, '''VERILOG
    # re.DOTALL ALLOWS THE SEARCH TO SPAN ACROSS MULTIPLE LINES OF CODE
    match = re.search(r'"""(?:systemverilog|sv|verilog)?\n(.*?)\n"""', ai_text, re.DOTALL | re.IGNORECASE) 
    if match:
        return match.group(1) # RETURN ONLY THE RAW CODE FOUND INSIDE THE BACKTICKS
    return ai_text # FALLBACK: RETURN THE ORIGINAL TEXT IF NO MARKDOWN WAS USED

def validate_sva(code):
    """A LIGHTWEIGHT SYNTAX LINTER THAT SIMULATES AN EDA COMPILER TO CATCH COMMON AI MISTAKES."""
    errors = []

    # CHECK 1: ENSURE ALL OPEN PARENTHESES ARE PROPERLY CLOSED
    # CRITICAL FOR SYSTEMVERILOG ASSERTIONS WHICH RELY ON COMPLEX NESTED LOGIC
    if code.count('(') != code.count(')'):
        errors.append("Syntax Error: Unbalanced parantheses '()'.")

    # CHECK 2: SCAN LINE BY LINE FOR MISSING SEMICOLONS AT THE END OF ASSERTIONS
    lines = code.split('\n')
    for i, line in enumerate(lines):
        clean_line = line.strip() # REMOVE LEADING/TRAILING WHITESPACE

    
        if clean_line.startswith("assert property") and not clean_line.endswith(";"):
            if "(" in clean_line and clean_line.endswith(")"):
                errors.append(f"Line {i+1}: Missing semicolon after assertion.")

    # RETURN FALSE AND THE ACCUMULATED ERROR MESSAGES TO TRIGGER THE AI REFLECTION LOOP
    if errors:
        return False, " ".join(errors)

    #IF NO ERRORS WERE FOUND, THE CODE IS COMPILER-READY
    return True, "No syntax error detected."


#=============================================================
# 4. BATCH EXECUTION FLOW
#=============================================================
# CHECK: ENSURE INPUT DIRECTORY EXISTS BEFORE STARTING
if not os.path.exists(RTL_DIR):
    print(f"[!] Error: '{RTL_DIR}' Directory not found. Please create it and add your .v files.")
    exit()


# USE A LIST COMPREHENSION TO SCAN THE DIRECTORY AND FILTER FOR VERILOG/SYSTEMVERILOG FILES ONLY
rtl_files = [f for f in os.listdir(RTL_DIR) if f.endswith('.v') or f.endswith('.sv')]

# EXIT IF THE FOLDER IS EMPTY TO PREVENT CRASHES
if not rtl_files:
    print(f"[!] No Verilog files found in '{RTL_DIR}'.")
    exit()

print(f"[*] Found {len(rtl_files)} files to process. Starting Batch Execution..\n")

#THE MASTER LOOP: PROCESS EACH RTL FILE AUTONOMOUSLY, ONE BY ONE
for filename in rtl_files:
    rtl_filepath = os.path.join(RTL_DIR, filename) # CONSTRUCRT SAFE FILE PATH

    print("="*60)
    print(f"[*] PROCESSING: {filename}")
    print("="*60)

    # READ RAW VERILOG SOURCE CODE INTO MEMORY
    with open(rtl_filepath, "r") as file:
        verilog_code = file.read()

    # TRIGGER AUTO-ROUTER ENGINE TO INDENTIFY THE IP BLOCK
    detected_protocol = detect_protocol(verilog_code)
    spec_file_path = None
    prompt_contents = []

    if detected_protocol:
        print(f"[*] Auto_detected Protocol: {detected_protocol.upper()}")
        spec_file_path = find_spec_file(detected_protocol) # FIND THE MATCHING OFFICIAL INDUSTRY RULEBOOK FOR THE DESIGN

    if spec_file_path:
        print(f"[*] Found spec file: {spec_file_path}")
        if spec_file_path.endswith(".pdf"):
            print("[*] Uploading PDF to Gemini File API...")
            uploaded_pdf = client.files.upload(file=spec_file_path) # LEVERAGE GOOGLE'S FILE API TO HANDLE MASSIVE, MULTI-PAGE PDF'S
            prompt_contents.append(uploaded_pdf)
        elif spec_file_path.endswith(".txt"):
            with open(spec_file_path, "r") as file:
                text_rules = file.read()
                prompt_contents.append(f"=== PROTOCOL RULES ===\n{text_rules}") # INJECT RAW TEXT RULES DIRECLTY INTO THE PROMPT CONTEXT
    else:
        print("[!] No specific protocol document found. Generating standard SVAs.")

# INSTRUCT THE AI TO ACT AS DV ENGINEER AND STRICLTY FOLLOW THE PROTOCOL SPECIFICATIONS
    text_prompt = f"""You are an expert Design Verification Engineer.
I have provided the Verilog RTL below. If a protocol specification is attached or provided,
generate strict SystemVerilog Assertions (SVA) that verify those specific rules.
Otherwise, generate standard SVAs for basic digital logic checks (overflow, resets, etc.).

Only output System Verilog code with comments explaining each assertion. Do not include any other text.

=== VERILOG RTL ===
{verilog_code}
"""
    prompt_contents.append(text_prompt)

    print(f"\n[*] Analyzing {filename} and generating assertions... Please wait...")

    # AUTO-HEALING LOOP
    MAX_RETRIES = 3 # PREVENT INFINITE LOOPS; GIVE AI 3 CHNACES TO FIX SYNTAX ERRORS
    success = False
    final_code = ""
    raw_response = ""

    for attempt in range(1, MAX_RETRIES + 1):
        # CALL THE GEMINI MODEL WITH THE FULL CONTEXT (RTL + SPECS + PROMPT + ERROR HISTORHY)
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt_contents
        )
        raw_response = response.text
        # STRIP AWAY THE CONVERSATIONAL FILTER TO ISOLATE THE SYSTEMVERILOG CODE
        extracted_code = extract_code(raw_response)

        #-------- DEMO SABOTAGE ------------
        # ARTIFICIALLY REMOVES THE FIRST SEMICOLON IN ATTEMPT 1 TO TRIGGER THE AUTO HEALER
        if attempt == 1:
            extracted_code = extracted_code.replace(")","",1)
        #--------------------------------------------

        # RUN THE EXTRACTED CODE THROUGH OUR CUSTOM EDA SYNTAX LINTER
        is_valid, error_msg = validate_sva(extracted_code)

        if is_valid:
            print(f"[*] Attempt {attempt}: Success! Code passed syntax validation")
            final_code = extracted_code
            success = True
            break #EXIT LOOP IMMEDIATELY UPON SUCCESS

        # ERROR FEEDBACK INJECTION
        print(f"[!] Attempt {attempt} Failed Syntax check: {error_msg}")
        print("[*] Sending Error back to AI for Correction....")

        # APPEND THE SPECIFIC COMPILER ERROR BACK INTO THE AI's CONTEXT WINDOW SO IT LEARNS ND ADAPTS
        error_feedback = f"The previous code had the following syntax error: {error_msg}. Please fix it."
        prompt_contents.append(error_feedback)

    # AUTOMATED OUTPUT ROUTING
    # DYNAMICALLY GENERATE THE OUTPUT FILENAME
    output_filename = f"{filename.split('.')[0]}_sva.sv"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    # OPEN THE TARGET FILE IN WRITE MODE
    with open(output_filepath, "w") as out_file:
        if success:
            # SAVE THE VALIDATED, PRODUCTION-READY ASSERTIONS
            out_file.write(final_code)
            print(f"[*] Wrote valid assertions to: {output_filepath}\n")
        else:
            # FALLBACK: SAVE THE FAILED ATTEMPT FOR MANUAL DEBUGGING
            out_file.write("// AI Failed to generate valid code after 3 attemps. Last output:\n")
            out_file.write(final_code if final_code else raw_response )
            print(f"[!] Wrote failed attempt to: {output_filepath}\n")
    


