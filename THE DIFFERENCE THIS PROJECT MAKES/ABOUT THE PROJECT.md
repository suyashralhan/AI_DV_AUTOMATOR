1. Current Architecture & Capabilities (What is built so far)
   The tool is an agentic, closed-loop Design Verification IP generator powered by Python and Google's Gemini API. It currently operates in two primary phases:

   Dynamic Protocol Detection & RAG (Retrieval-Augmented Generation): The script parses raw Verilog/SystemVerilog RTL and auto-detects standard interfaces
   (AXI, AHB, APB, FIFO). It then dynamically injects context from a local specs repository, including formal protocol PDFs, Accellera SVA Cookbooks, and
   strict UVM Enterprise Style Guides, ensuring the AI writes industry-compliant code.

Phase 1: SystemVerilog Assertion (SVA) Generation: The AI maps RTL signals to standard enterprise assertion templates (e.g., mutually exclusive signals,   
         valid/ready handshakes) rather than inventing unverified temporal logic.

Phase 2: UVM Sequence Item Generation: The engine parses RTL inputs, ignores clocks/outputs, and generates parameterized uvm_sequence_item classes. It 
         automatically creates protocol-aware soft constraints (using dist blocks) and adheres to strict UVM macros (uvm_object_utils, uvm_info).

  Agentic Self-Healing Loop: The script integrates the open-source MikePopoloski slang.exe compiler. Instead of just saving the AI's first output, it compiles   the code. If the AI hallucinates bad syntax (e.g., uncast default assignments, missing endproperty), Slang throws an IEEE-1800 standard error. The script   
  intercepts this error and feeds it back to the AI for up to 3 autonomous correction attempts before saving the final production-ready file.

2. Immediate Roadmap (What you are adding next)

Phase 3: Full UVM Boilerplate Generation: Expanding the pipeline to automatically architect the complete scaffolding for a verification environment. By
         reading the RTL, the tool will generate the Driver, Monitor, Agent, and Environment classes in a single execution, saving days of manual VIP setup    
         time.
