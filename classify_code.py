import sys
import io
import requests
import os
import pandas as pd

def evaluate_student_submission(question: str, code: str, host: str = "http://localhost:11434") -> str:
    url = f"{host}/api/chat"
    user_prompt = f"Question Context / Assignment Prompt:\n{question}\n\nStudent's Code Snippet:\n{code}"

    payload = {
        "model": "qwen2.5-coder:7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert automated computer science teaching assistant and code evaluator.\n"
                    "Analyze the given question context and the student's code snippet. You must evaluate the work "
                    "and provide your complete response EXACTLY in the following structured format without using any "
                    "markdown ticks, wrappers, thinking blocks, or conversational filler lines:\n\n"
                    "LANGUAGE: [Identified programming language.\n"
                    "VERDICT: [CORRECT or INCORRECT]\n"
                    "EXPLANATION: [A brief, clear analysis explaining what the student wrote, whether it is right or wrong, "
                    "and precisely where they made a mistake if any errors exist.]"
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

    default_result = {"Language": "Unknown", "Verdict": "Unknown", "Explanation": "Failed to extract text."}

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        raw_content = result.get("message", {}).get("content", "").strip()


        parsed_data = {}
        for line in raw_content.split('\n'):
            if line.startswith("LANGUAGE:"):
                parsed_data["Language"] = line.replace("LANGUAGE:", "").strip()
            elif line.startswith("VERDICT:"):
                parsed_data["Verdict"] = line.replace("VERDICT:", "").strip()
            elif line.startswith("EXPLANATION:"):
                parsed_data["Explanation"] = line.replace("EXPLANATION:", "").strip()

        final_output = {
            "Language": parsed_data.get("Language", "Unknown"),
            "Verdict": parsed_data.get("Verdict", "Unknown"),
            "Explanation": parsed_data.get("Explanation", raw_content)
        }
        return final_output

    except requests.exceptions.ConnectionError:
        return {"Language": "ERROR", "Verdict": "ERROR", "Explanation": "Couldn't Connect To Ollama"}
    except requests.exceptions.Timeout:
        return {"Language": "ERROR", "Verdict": "ERROR", "Explanation": "Request timed out."}
    except Exception as e:
        return {"Language": "ERROR", "Verdict": "ERROR", "Explanation": f"Error: {type(e).__name__}"}

    
def main():
    TARGET_FILE = "sheet-1.xlsx"
    
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
    evaluation_verdicts = []
    evaluation_explanations = []
    current_count = 0

    print("\n--- Running Language Detection")
    for idx, row in filtered_df.iterrows():
        current_count += 1 

        user_id = row["User ID"]
        qsn_no = row["QSN No"]
        question_text = str(row["Question"])
        code_snippet = str(row["Actual Code"])

        eval_metrics = evaluate_student_submission(question_text, code_snippet)
        detected_languages.append(eval_metrics["Language"])
        evaluation_verdicts.append(eval_metrics["Verdict"])
        evaluation_explanations.append(eval_metrics["Explanation"])

        print(f"📝 [Record {current_count}/{final_count}]")
        print(f"   👤 User ID      : {user_id}")
        print(f"   ❓ QSN No       : {qsn_no}")
        print(f"   🚀 Language     : {eval_metrics['Language']}")
        print(f"   ⚖️  Verdict      : {eval_metrics['Verdict']}")
        print(f"   📖 Explanation  : {eval_metrics['Explanation']}")
        print("-" * 60)
        
    filtered_df["Detected Language"] = detected_languages
    filtered_df["Evaluation Verdict"] = evaluation_verdicts
    filtered_df["Technical Explanation"] = evaluation_explanations

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