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

# E. Make the API Call
response = client.models.generate_content(
    model='gemini-3.5-flash', 
    contents=prompt_contents
)

print("\n=== AI GENERATED ASSERTIONS ===\n")
print(response.text)





    