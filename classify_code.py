import sys
import io
import requests
import os
import pandas as pd
import json

def evaluate_student_submission(question: str, code: str, host: str = "http://localhost:11434") -> dict:
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
                    "and return a raw JSON object matching the exact schema below. Do not include any thinking blocks, "
                    "markdown ticks (like ```json), conversational text, or extra characters.\n\n"
                    "JSON Schema:\n"
                    "{\n"
                    "  \"Language\": \"Name of programming language\",\n"
                    "  \"Syntax_Score\": 0-30,\n"
                    "  \"Logic_Score\": 0-50,\n"
                    "  \"Efficiency_Score\": 0-20,\n"
                    "  \"Error_Category\": \"Syntax Error\" or \"Logical Fallacy\" or \"Edge-Case Failure\" or \"Optimal Code\",\n"
                    "  \"Explanation\": \"A brief, clear analysis explaining what the student wrote, whether it is right or wrong, and precisely where they made a mistake if any errors exist.\"\n"
                    "}"
                )
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "stream": False,
        "format": "json",  
        "options": {
            "temperature": 0.0  
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        raw_content = result.get("message", {}).get("content", "").strip()
        
        parsed_json = json.loads(raw_content)
        
        s_score = int(parsed_json.get("Syntax_Score", 0))
        l_score = int(parsed_json.get("Logic_Score", 0))
        e_score = int(parsed_json.get("Efficiency_Score", 0))
        
        return {
            "Language": parsed_json.get("Language", "Unknown"),
            "Syntax_Score": s_score,
            "Logic_Score": l_score,
            "Efficiency_Score": e_score,
            "Total_Grade": s_score + l_score + e_score,
            "Error_Category": parsed_json.get("Error_Category", "Unknown"),
            "Explanation": parsed_json.get("Explanation", "No context provided.")
        }

    except requests.exceptions.ConnectionError:
        return {"Language": "ERROR", "Syntax_Score": 0, "Logic_Score": 0, "Efficiency_Score": 0, "Total_Grade": 0, "Error_Category": "Pipeline Failure", "Explanation": "Couldn't Connect To Ollama"}
    except requests.exceptions.Timeout:
        return {"Language": "ERROR", "Syntax_Score": 0, "Logic_Score": 0, "Efficiency_Score": 0, "Total_Grade": 0, "Error_Category": "Pipeline Failure", "Explanation": "Request timed out."}
    except Exception as e:
        return {"Language": "ERROR", "Syntax_Score": 0, "Logic_Score": 0, "Efficiency_Score": 0, "Total_Grade": 0, "Error_Category": "Pipeline Failure", "Explanation": f"JSON Error: {type(e).__name__}"}

    
def main():
    TARGET_FILE = "Stage-1.xlsx"
    
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
    syntax_scores = []
    logic_scores = []
    efficiency_scores = []
    total_grades = []
    error_categories = []
    evaluation_explanations = []
    
    current_count = 0

    print("\n--- Running Deep Code Evaluation Loop")
    for idx, row in filtered_df.iterrows():
        current_count += 1 

        user_id = row["User ID"]
        qsn_no = row["QSN No"]
        question_text = str(row["Question"])
        code_snippet = str(row["Actual Code"])
        
        eval_metrics = evaluate_student_submission(question_text, code_snippet)
        
        detected_languages.append(eval_metrics["Language"])
        syntax_scores.append(eval_metrics["Syntax_Score"])
        logic_scores.append(eval_metrics["Logic_Score"])
        efficiency_scores.append(eval_metrics["Efficiency_Score"])
        total_grades.append(eval_metrics["Total_Grade"])
        error_categories.append(eval_metrics["Error_Category"])
        evaluation_explanations.append(eval_metrics["Explanation"])
        
        print(f"📝 [Record {current_count}/{final_count}]")
        print(f"   👤 User ID      : {user_id}")
        print(f"   ❓ QSN No       : {qsn_no}")
        print(f"   🚀 Language     : {eval_metrics['Language']}")
        print(f"   ⚖️  Total Grade  : {eval_metrics['Total_Grade']}/100 ({eval_metrics['Syntax_Score']}/{eval_metrics['Logic_Score']}/{eval_metrics['Efficiency_Score']})")
        print(f"   🏷️  Error Class  : {eval_metrics['Error_Category']}")
        print(f"   📖 Explanation  : {eval_metrics['Explanation']}")
        print("-" * 60)
        
    filtered_df["Detected Language"] = detected_languages
    filtered_df["Syntax Score (Max 30)"] = syntax_scores
    filtered_df["Logic Score (Max 50)"] = logic_scores
    filtered_df["Efficiency Score (Max 20)"] = efficiency_scores
    filtered_df["Total Grade (Max 100)"] = total_grades
    filtered_df["Error Category"] = error_categories
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

    print("\n🏷️ --- Error Category Breakdown Analytics ---")
    error_summary = filtered_df["Error Category"].value_counts()
    for category, count in error_summary.items():
        print(f"   🔸 {category}: {count} occurrences")
    print("-" * 50)

if __name__ == "__main__":
    main()