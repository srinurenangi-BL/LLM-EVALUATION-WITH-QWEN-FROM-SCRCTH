# Local Student Code Language Detector Pipeline

An automated, offline evaluation system that ingests student data sheets, processes code submissions through a local Large Language Model (LLM) utilizing contextual problem statements, tracks execution in real-time, and generates augmented data reports.

## 🚀 Architectural Overview

Manually evaluating massive batches of student programming assignments to check language compliance is tedious and prone to syntax oversight. This pipeline transitions that process into a fully automated, edge-computed workflow. 

By leveraging **Qwen 2.5 Coder 7B Instruct** locally via **Ollama**, the script analyzes both the **Assignment Question** and the **Student Code Block** side-by-side. This dual-context approach guarantees high classification accuracy for structurally ambiguous code fragments (such as differentiating between C and C++ or SQL sub-dialects) without any cloud computing costs or data privacy risks.

---

## 📐 The 5-Step Pipeline Architecture

The program initializes from `main()` and flows sequentially through five distinct engineering layers:

### 1. Data Ingestion Layer
Dynamically identifies file extensions (`.csv` versus `.xlsx`/`.xls`) and utilizes high-performance `pandas` buffers to read local files directly into an active memory DataFrame.

### 2. Structural Validation & Cleansing
*   **Header Sanitation:** Runs string trimming (`.str.strip()`) across all sheet headers to eliminate accidental leading or trailing white spaces.
*   **Column Enforcement:** Validates the absolute existence of four foundational columns: `QSN No`, `User ID`, `Question`, and `Actual Code`. If any are missing, execution stops safely.
*   **Compute Optimization:** Filters out and drops all empty rows, `NaN` values, or blank spaces within the `Actual Code` column to prevent wasting local LLM compute cycles on missing inputs.

### 3. Contextual Inference Engine
Constructs a deterministic system instruction set mapped against a dual-input prompt template. The engine sets LLM parameters to a temperature of `0.0` to force rigid, predictable classifications, while explicitly stripping out common LLM formatting noise like markdown code fences (\`\`\`) or surrounding quotation marks.

### 4. Real-Time Logging & Augmentation Loop
Iterates through the records one-by-one. Instead of running silently, it functions like a live server log, outputting a structured telemetry block directly to your terminal terminal window the millisecond a query resolves. 

### 5. Non-Destructive Export Layer
Compiles the structural results array into a brand new dataset column (`Detected Language`). To protect core data integrity, it leaves the original file untouched and compiles a fresh Excel file prefixed with `Classified_`. It then generates a terminal-side distribution summary tracking metrics for total language submissions.

---

## 🛠️ Project Stack & Package Breakdown

This project utilizes isolated virtual environment architecture (`.venv`) to lock dependencies:

*   **`pandas`**: Acts as the data manipulation engine, handling the heavy lifting of parsing, data cleaning, and dataset transformation.
*   **`openpyxl`**: The behind-the-scenes read/write engine that allows Python to speak fluently with modern Microsoft Excel (`.xlsx`) files.
*   **`requests`**: Handles the underlying local network handshake, transmitting payloads via HTTP POST directly to Ollama's local engine.
*   **`os` & `sys`**: Manages pathing checks, determines file existence safety nets, and processes environment state terminations.

---

## ⚙️ Initial Setup & Local Deployment

### 1. Environment Initialization
Clone the repository, enter the directory, and spin up your isolated environment:
```bash
# Create the virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install pandas openpyxl requests