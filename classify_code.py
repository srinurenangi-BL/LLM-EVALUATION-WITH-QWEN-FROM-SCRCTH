import sys
import io
import requests
import os
import pandas as pd

def detect_language_from_context(question: str, code: str, host: str = "http://localhost:11434") -> str:
    url = f"{host}/api/chat"
    user_prompt = f"Question Context / Assignment Prompt:\n{question}\n\nStudent's Code Snippet:\n{code}"

    payload = {
        "model": "qwen2.5-coder:7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert programming language detector. Analyze the given question context "
                    "and the code snippet, then return ONLY the name of the programming language. "
                    "Do not include any explanation, introductory text, markdown formatting, or extra characters. "
                    "Examples of valid outputs: 'Python', 'JavaScript', 'C++', 'Java', 'HTML', 'SQL', 'Rust'. "
                    "If you are completely unsure, return 'Unknown'."
                )
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.0  
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        language = result.get("message", {}).get("content", "").strip()
        language = language.replace("`", "").replace("'", "").replace('"', '')
        return language

    except requests.exceptions.ConnectionError:
        return "ERROR: Couldn't Connect To Ollama"
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out."
    except Exception as e:
        return f"ERROR: {type(e).__name__}"

    
def main():
    TARGET_FILE = "Practice App-API Testing Report.xlsx"
    
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Error: The file '{TARGET_FILE}' was not found in this folder.")
        return
    
    try:
        if TARGET_FILE.endswith('.csv'):
           df = pd.read_csv(TARGET_FILE)
        else:
           df = pd.read_excel(TARGET_FILE) 
        print("✅ Data sheet successfully loaded!")
    except Exception as e:
       print(f"❌ Error reading file: {e}")
       return
    
    df.columns = df.columns.str.strip()
    required_cols = ["QSN No", "User ID", "Question", "Actual Code"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Error: Missing required columns in sheet: {missing_cols}")
        return
    print("✅ All target columns verified successfully!")

    filtered_df = df[required_cols].copy()
    filtered_df = filtered_df.dropna(subset=["Actual Code"])
    filtered_df = filtered_df[filtered_df["Actual Code"].astype(str).str.strip() != ""]
    
    final_count = len(filtered_df)
    print(f"📊 Rows with valid code snippets to process: {final_count}")

    detected_languages = []
    current_count = 0

    print("\n--- Running Language Detection")
    for idx, row in filtered_df.iterrows():
        current_count += 1 

        user_id = row["User ID"]
        question_text = str(row["Question"])
        code_snippet = str(row["Actual Code"])

        print(f"🤖 Processing row {current_count}/{final_count} (User: {user_id})...", end="\r")

        detected_lang = detect_language_from_context(question_text, code_snippet)
        detected_languages.append(detected_lang)
        
    filtered_df["Detected Language"] = detected_languages
    print(" " * 70, end="\r") 
    print("✅ All spreadsheet rows successfully analyzed!")
    output_file = f"Classified_{TARGET_FILE}"
    
    try:
        if output_file.endswith('.csv'):
            filtered_df.to_csv(output_file, index=False)
        else:
            filtered_df.to_excel(output_file, index=False)
        print(f"💾 File successfully saved as: {output_file}")
    except Exception as e:
        print(f"❌ Failed to save output file: {e}")
        return
    
    print("\n📊 --- Language Distribution Metrics ---")
    summary = filtered_df["Detected Language"].value_counts()
    for lang, count in summary.items():
        print(f"   🔹 {lang}: {count} submissions")
    print("-" * 50)

if __name__ == "__main__":
    main()