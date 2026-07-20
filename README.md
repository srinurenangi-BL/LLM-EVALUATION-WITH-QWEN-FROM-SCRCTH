Local Student Code Language Detector & Evaluation Pipeline
An automated, offline evaluation system that ingests student data sheets, processes code submissions through a local Large Language Model (LLM) utilizing contextual problem statements, performs deep semantic validation, tracks execution in real-time, and generates augmented diagnostic reports.

🚀 Architectural Overview
Manually evaluating massive batches of student programming assignments to check code validity and structural correctness is tedious and prone to syntax oversight. This pipeline transitions that process into a fully automated, edge-computed workflow.

By leveraging Qwen 2.5 Coder 7B Instruct locally via Ollama, the script analyzes the Assignment Question and the Student Code Block side-by-side. This dual-context approach guarantees high accuracy, allowing the pipeline to determine the target language, pass judgment on correctness (binary validation), and extract precise technical reasons detailing why code succeeds or fails—without any cloud computing costs or data privacy risks.

📐 The 5-Step Pipeline Architecture
The program initializes from main() and flows sequentially through five distinct engineering layers:

1. Data Ingestion Layer
Dynamically identifies file extensions (.csv versus .xlsx/.xls) and utilizes high-performance pandas buffers to read local source files directly into an active memory DataFrame.

2. Structural Validation & Cleansing
Header Sanitation: Runs string trimming (.str.strip()) across all sheet headers to eliminate accidental leading or trailing white spaces.

Column Enforcement: Validates the absolute existence of four foundational columns: QSN No, User ID, Question, and Actual Code. If any are missing, execution stops safely.

Compute Optimization: Filters out and drops all empty rows, NaN values, or blank spaces within the Actual Code column to prevent wasting local LLM compute cycles on missing inputs.

3. Contextual Inference & Evaluation Engine
Constructs a deterministic system instruction set mapped against a compound evaluation prompt template. The engine locks LLM parameters to a temperature of 0.0 to force rigid, predictable classifications. The system forces the model to assess the code against the question text and return a multi-layered diagnostic verdict without using common LLM formatting noise like markdown code fences (```) or text wrappers.

4. Real-Time Telemetry & Log Loop
Iterates through records one by one. Instead of running silently, it functions like a live telemetry server dashboard, immediately outputting structured multi-line metric blocks containing the user's ID, problem number, language name, evaluation verdict (CORRECT / INCORRECT), and code analytics directly to the terminal the millisecond an item finishes processing.

5. Non-Destructive Multi-Column Export Layer
Compiles the structural results array into three distinct new dataset column fields:

Detected Language — The programming language identified.

Evaluation Verdict — Binary validation marker (CORRECT or INCORRECT).

Technical Explanation — Precise analysis outlining what the student wrote and where they made mistakes.

To protect core data integrity, it leaves your original file completely untouched and exports a fresh Excel/CSV file prefixed with Classified_, finishing up with a terminal-side summary tracking final distribution metrics.

🛠️ Project Stack & Package Breakdown
This project utilizes isolated virtual environment architecture (.venv) to lock dependencies:

pandas: Acts as the data manipulation engine, handling the heavy lifting of parsing, data cleaning, and multi-column dataset expansions.

openpyxl: The behind-the-scenes read/write engine that allows Python to speak fluently with modern Microsoft Excel (.xlsx) files.

requests: Handles the underlying local network handshake, transmitting payloads via HTTP POST directly to Ollama's local engine.

os & sys: Manages pathing checks, determines file existence safety nets, and processes environment state terminations.

⚙️ Initial Setup & Local Deployment
1. Environment Initialization
Clone the repository, enter the directory, and spin up your isolated environment:
# Create the virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install pandas openpyxl requests


2. Running the System Pipeline
Ensure your Ollama server is running locally with the target model pulled (ollama pull qwen2.5-coder:7b-instruct), drop your data sheet named sheet-2.xlsx into the root project directory, and fire it up:
python classify_code.py

