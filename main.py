# import os
# from google import genai
# from dotenv import load_dotenv

# # 1. Load the environment variables
# load_dotenv()

# # 2. Initialize the new GenAI Client (it automatically finds your GEMINI_API_KEY)
# client = genai.Client()

# filename = "router_crossbar.v"
# try:
#     with open(filename, "r") as file:
#         verilog_code = file.read()
# except FileNotFoundError:
#     print("Error: router_crossbar.v file not found")
#     exit()

# # 3. The Prompt Engine
# prompt = f"""You are an expert Design Verification Engineer. You have to analyze the following verilog code and generate me 3 to 5 System Verilog Assertions (SVA) to check its basic protocol compliance (e.g. like handshake, valid/ready, clock, reset, etc).

# Only output System Verilog code with comments explaining each assertion. Do not include any other text or explanations.

# Here is your verilog code:
# {verilog_code}
# """

# print("Analyzing RTL and Generating assertions... Please wait...")

# # 4. Make the API Call using the new Client syntax
# response = client.models.generate_content(
#     model='gemini-3.5-flash', 
#     contents=prompt
# )

# print("\n=== AI GENERATED ASSERTIONS ===\n")
# print(response.text)


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

import os
import re   #IMPORTS PYTHON IN-BUILT "re" (REGULAR EXPRESSION) LIBRARY FOR TEXT SEARCHING
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

rtl_filename = "router_crossbar.v"
specs_folder = "specs"

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
    if not os.path.exists(specs_folder):
        print("Error: specs folder not found")
        return None
    for filename in os.listdir(specs_folder):
        if protocol_keyword in filename.lower():
            return os.path.join(specs_folder, filename)
    return None

def extract_code(ai_text):
    match = re.search(r'"""(?:systemverilog|sv|verilog)?\n(.*?)\n"""',ai_text,re.DOTALL | re.IGNORECASE)
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


try:
    with open(rtl_filename, "r") as file:
        verilog_code = file.read()

except FileNotFoundError:
    print("Error: rtl_filename file not found")
    exit()

detected_protocol = detect_protocol(verilog_code)
spec_file_path = None
uploaded_pdf = None
text_rules = ""

if detected_protocol:
    print(f"[*] Auto_detected Protocol: {detected_protocol.upper()}")
    spec_file_path =find_spec_file(detected_protocol)
prompt_contents = []

if spec_file_path:
    print(f"[*] Found spec file: {spec_file_path}")
    if spec_file_path.endswith(".pdf"):
        print("[*] Uploading PDF to Gemini File API...")
        uploaded_pdf = client.files.upload(file=spec_file_path)
        prompt_contents.append(uploaded_pdf)
    
    elif spec_file_path.endswith(".txt"):
        with open(spec_file_path, "r") as f:
            text_rules = f.read()
            prompt_contents.append(f"=== PROTOCOL RULES ===\n{text_rules}")
else:
    print("[!] No specific protocol document found. Generating standard SVAs.")

# D. Build the Final Prompt
text_prompt = f"""You are an expert Design Verification Engineer. 
I have provided the Verilog RTL below. If a protocol specification is attached or provided, 
generate strict SystemVerilog Assertions (SVA) that verify those specific rules. 
Otherwise, generate standard SVAs for basic digital logic checks (overflow, resets, etc.).

Only output System Verilog code with comments explaining each assertion. Do not include any other text.

=== VERILOG RTL ===
{verilog_code}
"""
prompt_contents.append(text_prompt)

print(f"\n[*] Analyzing {rtl_filename} and generating assertions... Please wait...")

MAX_RETRIES = 3
success = False
final_code = ""

for attempt in range(1, MAX_RETRIES + 1):
    # E. Make the API Call
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

print("\n=== AI GENERATED ASSERTIONS ===\n")

if success:
    print(final_code)
else:
    print("// AI failed to generate valid code after 3 attempts. Last output:")
    print(final_code if final_code else raw_response)







    