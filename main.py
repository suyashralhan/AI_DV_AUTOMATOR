import os
from google import genai
from dotenv import load_dotenv

# 1. Load the environment variables
load_dotenv()

# 2. Initialize the new GenAI Client (it automatically finds your GEMINI_API_KEY)
client = genai.Client()

filename = "router_crossbar.v"
try:
    with open(filename, "r") as file:
        verilog_code = file.read()
except FileNotFoundError:
    print("Error: router_crossbar.v file not found")
    exit()

# 3. The Prompt Engine
prompt = f"""You are an expert Design Verification Engineer. You have to analyze the following verilog code and generate me 3 to 5 System Verilog Assertions (SVA) to check its basic protocol compliance (e.g. like handshake, valid/ready, clock, reset, etc).

Only output System Verilog code with comments explaining each assertion. Do not include any other text or explanations.

Here is your verilog code:
{verilog_code}
"""

print("Analyzing RTL and Generating assertions... Please wait...")

# 4. Make the API Call using the new Client syntax
response = client.models.generate_content(
    model='gemini-3.5-flash', 
    contents=prompt
)

print("\n=== AI GENERATED ASSERTIONS ===\n")
print(response.text)