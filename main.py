import os
import re   #IMPORTS PYTHON IN-BUILT "re" (REGULAR EXPRESSION) LIBRARY FOR TEXT SEARCHING
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

RTL_DIR = "rtl"
OUTPUT_DIR = "output_svas"
SPECS_DIR = "specs"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def detect_protocol(rtl_code):
    code = rtl_code.upper()
    if "AWVALID" in code or "ARVALID" in code or "AWADDR" in code:
        return "axi"
    elif "HTRANS" in code or "HREADY" in code or "HADDR" in code:
        return "ahb"
    elif "PSEL" in code or "PENBLE" in code:
        return "apb"
    elif "WR_EN" in code or "RD_EN" in code or "FIFO_DATA" in code:
        return "fifo"
    return None

def find_spec_file(protocol_keyword):
    if not os.path.exists(SPECS_DIR):
        print("Error: specs folder not found")
        return None
    for filename in os.listdir(SPECS_DIR):
        if protocol_keyword in filename.lower():
            return os.path.join(SPECS_DIR, filename)
    return None

def extract_code(ai_text):
    match = re.search(r'"""(?:systemverilog|sv|verilog)?\n(.*?)\n"""', ai_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return ai_text

def validate_sva(code):
    errors = []

    if code.count('(') != code.count(')'):
        errors.append("Syntax Error: Unbalanced parantheses '()'.")

    lines = code.split('\n')
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if clean_line.startswith("assert property") and not clean_line.endswith(";"):
            if "(" in clean_line and clean_line.endswith(")"):
                errors.append(f"Line {i+1}: Missing semicolon after assertion.")

    if errors:
        return False, " ".join(errors)
    return True, "No syntax error detected."


if not os.path.exists(RTL_DIR):
    print(f"[!] Error: '{RTL_DIR}' Directory not found. Please create it and add your .v files.")
    exit()

rtl_files = [f for f in os.listdir(RTL_DIR) if f.endswith('.v') or f.endswith('.sv')]

if not rtl_files:
    print(f"[!] No Verilog files found in '{RTL_DIR}'.")
    exit()

print(f"[*] Found {len(rtl_files)} files to process. Starting Batch Execution..\n")

for filename in rtl_files:
    rtl_filepath = os.path.join(RTL_DIR, filename)

    print("="*60)
    print(f"[*] PROCESSING: {filename}")
    print("="*60)

    with open(rtl_filepath, "r") as file:
        verilog_code = file.read()

    detected_protocol = detect_protocol(verilog_code)
    spec_file_path = None
    prompt_contents = []

    if detected_protocol:
        print(f"[*] Auto_detected Protocol: {detected_protocol.upper()}")
        spec_file_path = find_spec_file(detected_protocol)

    if spec_file_path:
        print(f"[*] Found spec file: {spec_file_path}")
        if spec_file_path.endswith(".pdf"):
            print("[*] Uploading PDF to Gemini File API...")
            uploaded_pdf = client.files.upload(file=spec_file_path)
            prompt_contents.append(uploaded_pdf)
        elif spec_file_path.endswith(".txt"):
            with open(spec_file_path, "r") as file:
                text_rules = f.read()
                prompt_contents.append(f"=== PROTOCOL RULES ===\n{text_rules}")
    else:
        print("[!] No specific protocol document found. Generating standard SVAs.")

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

    MAX_RETRIES = 3
    success = False
    final_code = ""
    raw_response = ""

    for attempt in range(1, MAX_RETRIES + 1):
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt_contents
        )
        raw_response = response.text
        extracted_code = extract_code(raw_response)
        is_valid, error_msg = validate_sva(extracted_code)

        if is_valid:
            print(f"[*] Attempt {attempt}: Success! Code passed syntax validation")
            final_code = extracted_code
            success = True
            break

        print(f"[!] Attempt {attempt} Failed Syntax check: {error_msg}")
        print("[*] Sending Error back to AI for Correction....")

        error_feedback = f"The previous code had the following syntax error: {error_msg}. Please fix it."
        prompt_contents.append(error_feedback)

    output_filename = f"{filename.split('.')[0]}_sva.sv"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    with open(output_filepath, "w") as out_file:
        if success:
            out_file.write(final_code)
            print(f"[*] Wrote valid assertions to: {output_filepath}\n")
        else:
            out_file.write("// AI Failed to generate valid code after 3 attemps. Last output:\n")
            out_file.write(final_code if final_code else raw_response )
            print(f"[!] Wrote failed attempt to: {output_filepath}\n")
    


    