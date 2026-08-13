# AI DV Automator

An AI-powered Design Verification tool that automatically generates SystemVerilog Assertions (SVAs) from standard Verilog RTL.

## Features
* Parses Verilog RTL (e.g., standard FIFOs, router crossbars).
* Integrates with Google Gemini API to analyze protocol compliance.
* Generates commented SystemVerilog Assertions.

## Setup Instructions
1. Create a virtual environment and activate it:
   `python -m venv venv`
   `.\venv\Scripts\activate`
2. Install the dependencies:
   `pip install google-genai python-dotenv pyverilog`
3. Create a `.env` file in the root directory and add your API key:
   `GEMINI_API_KEY=your_api_key_here`

## Usage
1. Place your target Verilog file in the root directory.
2. Run the main script:
   `python main.py`