# =====================================================================
# AI_DV_AUTOMATOR - Enterprise SystemVerilog Assertion & UVM Generator
# =====================================================================

import os                         # Handles file path navigation and directory operations
import subprocess                 # Executes local CLI tools (slang.exe) from Python
import re                         # Regular expressions for robust code extraction
import time                       # Manages backoff delays during API rate limits / busy server responses
from google import genai          # Official Google GenAI SDK client
from dotenv import load_dotenv    # Loads environment variables from the local .env file

# ---------------------------------------------------------------------
# 1. ENVIRONMENT CONFIGURATION & DIRECTORY SETUP
# ---------------------------------------------------------------------

# Load the secret environment variables (e.g., GEMINI_API_KEY) into system memory
load_dotenv()

# Initialize the Gemini client; automatically picks up the API key from the environment
client = genai.Client()

# Define project directories for inputs, specifications, and generated outputs
RTL_DIR    = "rtl"               # Input directory storing RTL design files (.v, .sv)
SPECS_DIR  = "specs"             # Reference directory for protocol specs (PDF/TXT), style guides, and SVA patterns
OUTPUT_DIR = "output_svas"       # Output directory for verified SystemVerilog Assertions
UVM_DIR    = "output_uvm"        # Output directory for generated UVM Sequence Items

# Automatically create output directories if they do not exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

if not os.path.exists(UVM_DIR):
    os.makedirs(UVM_DIR)

# ---------------------------------------------------------------------
# 2. PROMPT TEMPLATES (PHASE 1 SVA & PHASE 2 UVM)
# ---------------------------------------------------------------------

# Phase 2 Template: Instructs the LLM to generate production-ready UVM sequence items with CRV constraints
UVM_PROMPT_TEMPLATE = """You are an expert Design Verification Engineer specializing in UVM and SystemVerilog.
Your task is to analyze the provided RTL module and generate a production-ready `uvm_sequence_item`.

Follow these strict methodology rules:
1. Class Setup: Name the class `{module_name}_seq_item` and extend it from `uvm_sequence_item`.
2. Variables: Declare all input ports from the RTL as `rand` bit/logic variables. Do not include clock ('clk') or output ports.
3. Factory Registration: Include standard `uvm_object_utils` or `uvm_object_param_utils` (if parameterized).
4. Constructor: Provide a standard `new(string name = "{module_name}_seq_item")` function.
5. Constraints: Generate intelligent, protocol-aware `constraint` blocks:
   - Use soft constraints to keep active-low resets (rst_n / reset_n) de-asserted by default.
   - Constrain data and control signals using realistic distributions (dist blocks) for corner-case coverage.
6. Output Format: Output ONLY valid SystemVerilog code wrapped in ```systemverilog markdown. Do not include conversational text.

RTL Code:
{rtl_code}
"""

# ---------------------------------------------------------------------
# 3. PROTOCOL AUTO-ROUTING ENGINE
# ---------------------------------------------------------------------

def detect_protocol(rtl_code):
    """Scans RTL signal names to auto-detect the interface protocol."""
    code = rtl_code.upper()
    if "AWVALID" in code or "ARVALID" in code or "AWADDR" in code:
        return "axi"              # Matches ARM AMBA AXI signals
    elif "HTRANS" in code or "HREADY" in code or "HADDR" in code:
        return "ahb"              # Matches ARM AMBA AHB signals
    elif "PSEL" in code or "PENABLE" in code:
        return "apb"              # Matches ARM AMBA APB signals
    elif "WR_EN" in code or "RD_EN" in code or "FIFO_DATA" in code:
        return "fifo"             # Matches Synchronous / Asynchronous FIFO signals
    return None

def find_spec_file(protocol_keyword):
    """Searches the specs folder for documentation matching the detected protocol."""
    if not os.path.exists(SPECS_DIR):
        print(f"[!] Warning: '{SPECS_DIR}' directory not found.")
        return None
    for filename in os.listdir(SPECS_DIR):
        if protocol_keyword in filename.lower():
            return os.path.join(SPECS_DIR, filename)
    return None

# ---------------------------------------------------------------------
# 4. COMPILER INTEGRATION & SYNTAX VALIDATION (SLANG ENGINE)
# ---------------------------------------------------------------------

def extract_code(ai_text):
    """Extracts raw SystemVerilog code from markdown blocks and strips rogue backticks."""
    # Match code inside standard ```systemverilog ... ``` blocks across multiple lines
    match = re.search(r'```(?:systemverilog|sv|verilog|v)?\s*(.*?)```', ai_text, re.DOTALL | re.IGNORECASE)
    if match:
        clean_code = match.group(1).strip()
    else:
        clean_code = ai_text.strip()

    # Failsafe cleanup: Remove any residual markdown fence artifacts that could trip compiler macros
    clean_code = clean_code.replace("```systemverilog", "")
    clean_code = clean_code.replace("```sv", "")
    clean_code = clean_code.replace("```verilog", "")
    clean_code = clean_code.replace("```", "")
    return clean_code.strip()

def validate_sva(code, rtl_filepath):
    """Compiles the generated SVA against the RTL module using Slang to catch IEEE 1800 syntax violations."""
    temp_filename = "temp_sva.sv"

    # Write the SVA to a temporary file
    with open(temp_filename, "w") as f:
        f.write(code)

    try:
        # Run Slang passing BOTH the RTL file and the SVA file to resolve port lists and bind statements
        result = subprocess.run(
            [r".\slang.exe", rtl_filepath, temp_filename],
            capture_output=True,
            text=True
        )

        # Check compiler exit status
        if result.returncode != 0:
            error_output = result.stderr if result.stderr else result.stdout
            error_lines = error_output.strip().split('\n')
            short_error = "\n".join(error_lines[:10])  # Capture top 10 compiler error lines
            return False, f"SystemVerilog compilation error:\n{short_error}"

        return True, "No syntax error detected."

    except FileNotFoundError:
        return False, "[SYSTEM ERROR] slang.exe not found in working directory."
    finally:
        # Guarantee cleanup of temporary testbench files
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

# ---------------------------------------------------------------------
# 5. MASTER EXECUTION PIPELINE
# ---------------------------------------------------------------------

if not os.path.exists(RTL_DIR):
    print(f"[!] Error: '{RTL_DIR}' directory not found. Please create it and add RTL files.")
    exit()

rtl_files = [f for f in os.listdir(RTL_DIR) if f.endswith('.v') or f.endswith('.sv')]

if not rtl_files:
    print(f"[!] No Verilog/SystemVerilog files found in '{RTL_DIR}'.")
    exit()

print(f"[*] Found {len(rtl_files)} files to process. Starting batch execution...\n")

for filename in rtl_files:
    rtl_filepath = os.path.join(RTL_DIR, filename)

    print("=" * 60)
    print(f"[*] PROCESSING: {filename}")
    print("=" * 60)

    # Read design source code
    with open(rtl_filepath, "r") as file:
        verilog_code = file.read()

    # Detect protocol and build prompt context
    detected_protocol = detect_protocol(verilog_code)
    spec_file_path = None
    prompt_contents = []

    if detected_protocol:
        print(f"[*] Auto-detected Protocol: {detected_protocol.upper()}")
        spec_file_path = find_spec_file(detected_protocol)

    if spec_file_path:
        print(f"[*] Found spec file: {spec_file_path}")
        if spec_file_path.endswith(".pdf"):
            print("[*] Uploading PDF specification to Gemini File API...")
            uploaded_pdf = client.files.upload(file=spec_file_path)
            prompt_contents.append(uploaded_pdf)
        elif spec_file_path.endswith(".txt"):
            with open(spec_file_path, "r") as file:
                text_rules = file.read()
            prompt_contents.append(f"=== PROTOCOL RULES ===\n{text_rules}")
    else:
        print("[!] No specific protocol document found. Generating standard SVAs.")

    # Phase 1 SVA System Prompt
    text_prompt = f"""You are an expert Design Verification Engineer.
I have provided the Verilog RTL below. If a protocol specification is attached or provided,
generate strict SystemVerilog Assertions (SVA) that verify those specific rules.
Otherwise, generate standard SVAs for basic digital logic checks (overflow, resets, etc.).

Only output SystemVerilog code with comments explaining each assertion. Do not include any other text.

=== VERILOG RTL ===
{verilog_code}
"""
    prompt_contents.append(text_prompt)

    # -----------------------------------------------------------------
    # PHASE 1: SELF-HEALING ASSERTION GENERATION LOOP
    # -----------------------------------------------------------------
    print(f"\n[*] Analyzing {filename} and generating assertions... Please wait...")

    MAX_RETRIES = 3
    success = False
    final_code = ""
    raw_response = ""

    for attempt in range(1, MAX_RETRIES + 1):
        # Resilient API call loop to absorb server congestion (503/429) without losing retry attempts
        while True:
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=prompt_contents
                )
                raw_response = response.text
                break
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    print("[!] Gemini API is busy. Waiting 10 seconds before retrying...")
                    time.sleep(10)
                else:
                    raise e

        # Extract code and clean backticks
        extracted_code = extract_code(raw_response)

        # Validate with Slang (cross-referencing the RTL file)
        is_valid, error_msg = validate_sva(extracted_code, rtl_filepath)

        if is_valid:
            print(f"[*] Attempt {attempt}: Success! Code passed syntax validation.")
            final_code = extracted_code
            success = True
            break

        print(f"[!] Attempt {attempt} Failed Syntax check: {error_msg}")
        print("[*] Sending compiler error back to AI for autonomous correction...")

        # Feedback loop: Append compiler diagnostics back into the conversation context
        error_feedback = f"The previous code had the following syntax error:\n{error_msg}\nPlease fix it."
        prompt_contents.append(error_feedback)

    # Save Phase 1 SVA output
    output_filename = f"{filename.split('.')[0]}_sva.sv"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    with open(output_filepath, "w") as out_file:
        if success:
            out_file.write(final_code)
            print(f"[*] Wrote valid assertions to: {output_filepath}\n")
        else:
            out_file.write("// AI Failed to generate valid code after 3 attempts. Last output:\n")
            out_file.write(final_code if final_code else raw_response)
            print(f"[!] Wrote failed attempt to: {output_filepath}\n")

    # -----------------------------------------------------------------
    # PHASE 2: UVM SEQUENCE ITEM & CONSTRAINT GENERATION
    # -----------------------------------------------------------------
    print(f"[*] Generating UVM Sequence Item with constraints for {filename}...")

    uvm_prompt = UVM_PROMPT_TEMPLATE.format(
        module_name=filename.split('.')[0],
        rtl_code=verilog_code
    )

    MAX_API_RETRIES = 3
    uvm_response = None

    for api_attempt in range(1, MAX_API_RETRIES + 1):
        try:
            uvm_response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=uvm_prompt
            )
            break
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                print(f"[!] Gemini API is busy. Retrying UVM Generation in 10s... (Attempt {api_attempt}/{MAX_API_RETRIES})")
                time.sleep(10)
                if api_attempt == MAX_API_RETRIES:
                    print("[!] API completely unavailable. Skipping UVM generation for this file.")
            else:
                raise e

    if uvm_response:
        uvm_code = extract_code(uvm_response.text)
        uvm_filename = f"{filename.split('.')[0]}_seq_item.sv"
        uvm_filepath = os.path.join(UVM_DIR, uvm_filename)

        with open(uvm_filepath, "w") as f:
            f.write(uvm_code)

        print(f"[*] Wrote UVM Sequence Item to: {uvm_filepath}\n")