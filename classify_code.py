import sys
import io
import re
import requests
import os
import pandas as pd
import json
import statistics
from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound

SEMESTER_LANGUAGE = "Java"
MODEL_MAX_CONTEXT = 4096
BORDERLINE_SCORE_LOW = 6.0
BORDERLINE_SCORE_HIGH = 9.0
BORDERLINE_RECHECK_RUNS = 3
SCORE_VARIANCE_FLAG_THRESHOLD = 2.5
MAX_RETRIES = 2

LANGUAGE_SIGNATURES = {
    "java": [
        (r"\bpublic\s+class\s+\w+", 3),
        (r"\bpublic\s+static\s+void\s+main\s*\(", 3),
        (r"\bSystem\.out\.println\s*\(", 3),
        (r"^\s*import\s+java\.", 2),
        (r"\bnew\s+\w+\s*\(", 1),
    ],
    "python": [
        (r"^\s*def\s+\w+\s*\(.*\)\s*:", 3),
        (r"^\s*import\s+\w+\s*$", 1),
        (r"\bprint\s*\(", 2),
        (r"\bself\b", 2),
        (r":\s*$", 1), 
    ],
    "cpp": [
        (r"#include\s*<iostream>", 3),
        (r"\bstd::", 3),
        (r"\bcout\s*<<", 3),
        (r"\busing\s+namespace\s+std", 2),
        (r"\bint\s+main\s*\(", 1),
    ],
    "c": [
        (r"#include\s*<stdio\.h>", 3),
        (r"\bprintf\s*\(", 2),
        (r"\bscanf\s*\(", 2),
        (r"\bint\s+main\s*\(", 1),
    ],
    "csharp": [
        (r"\busing\s+System\s*;", 3),
        (r"\bConsole\.WriteLine\s*\(", 3),
        (r"\bnamespace\s+\w+", 2),
        (r"\bclass\s+\w+", 1),
    ],
    "javascript": [
        (r"\bconsole\.log\s*\(", 3),
        (r"\bfunction\s+\w+\s*\(", 2),
        (r"=>", 2),
        (r"\b(let|const|var)\b", 1),
    ],
    "typescript": [
        (r":\s*(string|number|boolean|any)\b", 3),
        (r"\binterface\s+\w+", 3),
        (r"\bconsole\.log\s*\(", 1),
    ],
}

LANGUAGE_ALIASES = {
    "java": "java",
    "python": "python",
    "c++": "cpp",
    "cpp": "cpp",
    "c": "c",
    "c#": "csharp",
    "csharp": "csharp",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
}

MIN_CONFIDENCE_THRESHOLD = 2

def _score_against_signatures(code: str) -> dict:
    scores = {}
    for lang_key, patterns in LANGUAGE_SIGNATURES.items():
        total = 0
        for pattern, weight in patterns:
            if re.search(pattern, code, re.MULTILINE):
                total += weight
        scores[lang_key] = total
    return scores


def _pygments_fallback_guess(code: str) -> str:
    try:
        lexer = guess_lexer(code)
        name = lexer.name.lower()
    except ClassNotFound:
        return "unknown"
    except Exception:
        return "unknown"
    
    if "java" in name and "script" not in name:
        return "java"
    if "python" in name:
        return "python"
    if "c++" in name:
        return "cpp"
    if name == "c":
        return "c"
    if "c#" in name or "csharp" in name:
        return "csharp"
    if "typescript" in name:
        return "typescript"
    if "javascript" in name:
        return "javascript"
    return "unknown"


def detect_language_deterministic(code: str) -> tuple:
    sig_scores = _score_against_signatures(code)
    sorted_scores = sorted(sig_scores.items(), key=lambda x: x[1], reverse=True)
    top_lang, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    if top_score >= MIN_CONFIDENCE_THRESHOLD and top_score > second_score:
        return top_lang, top_score, "regex_signature"

    pygments_guess = _pygments_fallback_guess(code)
    if pygments_guess != "unknown":
        return pygments_guess, top_score, "pygments_fallback"
    return "unknown", top_score, "inconclusive"


def languages_match_deterministic(expected: str, code: str) -> tuple:
    expected_key = LANGUAGE_ALIASES.get(expected.strip().lower(), expected.strip().lower())
    detected_key, confidence, method = detect_language_deterministic(code)

    if detected_key == "unknown":
        return False, "Unknown/Ambiguous", True
    
    is_match = (detected_key == expected_key)
    return is_match, detected_key, False

def determine_expected_language(question: str) -> str:

    return SEMESTER_LANGUAGE

def get_base_prompt(language: str, ques_ans_content_with_inst: str, summary_gen_flag: bool) -> str:

    INDIVIDUAL_PART = f"""
            The submitted programming language is:

            {language}

            Below are the question-answer pairs submitted by the user.

            Each item may optionally contain SPECIFIC INSTRUCTIONS.
            These instructions represent additional constraints,
            expected approaches, edge cases, evaluation criteria,
            or implementation requirements for that particular question.

            While evaluating each answer:
            - Carefully follow the SPECIFIC INSTRUCTIONS if present
            - Evaluate whether the submitted answer satisfies them
            - Include violations or missed requirements in the feedback

            Submitted Question–Answer Data:

            {ques_ans_content_with_inst}

            Tasks:

            ------------------------------------------------------------
            1. REVIEW EACH QUESTION–ANSWER INDIVIDUALLY
            ------------------------------------------------------------

            For each item:

            - Analyze correctness
            - Identify bugs
            - Evaluate readability
            - Evaluate efficiency
            - Validate adherence to SPECIFIC INSTRUCTIONS (if present)
            - Merge correctness assessment AND improvement suggestions into
              correctness_feedback as exactly 2 sentences.
              Sentence 1: assess correctness.
              Sentence 2: a genuine improvement if one exists, or confirm the
              code is optimal. Do not invent suggestions.
            - Do NOT output improvement_suggestions as a separate key.

            Scoring (ALL SCORES MUST BE OUT OF 10):
            - completeness_score
            - code_quality_score
            - approach_taken_score
            - overall_score

            overall_score formula:
            (0.5 * completeness_score)
            + (0.3 * code_quality_score)
            + (0.2 * approach_taken_score)"""
        
    SUMMARY_PART = """------------------------------------------------------------
        2. SUMMARY REVIEW
        ------------------------------------------------------------

        Provide:
        - overall_quality_label
        - common mistakes
        - strengths
        - weaknesses
        - recommendations

        overall_quality_label mapping:
        - 9–10 → Excellent
        - 7.5–8.9 → Good
        - 6–7.4 → Average
        - 4–5.9 → Poor
        - below 4 → Critical"""

    SCORE_PART = """------------------------------------------------------------
        3. OUTPUT FORMAT
        ------------------------------------------------------------

        Return this exact JSON schema:

        {
            "individual_reviews": [],
            "summary_review": {
                "overall_average_score": 0.0,
                "overall_quality_label": "",
                "common_errors": "",
                "strengths": "",
                "weaknesses": "",
                "recommendations": ""
            }
        }

        Rules:
        - Output ONLY valid JSON
        - Do not include markdown or explanations outside JSON
        """

    SCORE_WITHOUT_SUMM_PART = """------------------------------------------------------------
        3. OUTPUT FORMAT
        ------------------------------------------------------------

        Return this exact JSON schema:

        {
            "individual_reviews": [
                {
                    "question_text": "",
                    "correctness_feedback": "",
                    "scores": {
                        "completeness_score": 0.0,
                        "code_quality_score": 0.0,
                        "approach_taken_score": 0.0,
                        "overall_score": 0.0
                    }
                }
            ],
            "summary_review": "None"
        }

        Rules:
        - All scores must be between 0 and 10
        - Output ONLY valid JSON
        - Do not include markdown
        - Do not include explanations outside JSON
        - Do not include improvement_suggestions in the output
        - Base analysis strictly on the submitted code
        """
    if summary_gen_flag:
        return SUMMARY_PART + SCORE_PART
    else:
        return INDIVIDUAL_PART + SCORE_WITHOUT_SUMM_PART

INDIVIDUAL_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "individual_reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_text": {"type": "string"},
                    "correctness_feedback": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "properties": {
                            "completeness_score": {"type": "number"},
                            "code_quality_score": {"type": "number"},
                            "approach_taken_score": {"type": "number"},
                            "overall_score": {"type": "number"},
                        },
                        "required": ["completeness_score", "code_quality_score", "approach_taken_score", "overall_score"],
                    },
                },
                "required": ["question_text", "correctness_feedback", "scores"],
            },
        }
    },
    "required": ["individual_reviews"],
}

SUMMARY_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_review": {
            "type": "object",
            "properties": {
                "overall_average_score": {"type": "number"},
                "overall_quality_label": {"type": "string"},
                "common_errors": {"type": "string"},
                "strengths": {"type": "string"},
                "weaknesses": {"type": "string"},
                "recommendations": {"type": "string"},
            },
            "required": ["overall_quality_label", "common_errors", "strengths", "weaknesses", "recommendations"],
        }
    },
    "required": ["summary_review"],
}


def _call_ollama(prompt_content: str, schema: dict, host: str = "http://localhost:11434") -> dict:
    url = f"{host}/api/chat"
    payload = {
        "model": "qwen2.5-coder:7b-instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a precise grading assistant. Return ONLY a valid JSON object matching the requested schema layout. Never wrap response in markdown code blocks."
            },
            {
                "role": "user",
                "content": prompt_content
            }
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0.0, "num_ctx": MODEL_MAX_CONTEXT}
    }
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return json.loads(response.json().get("message", {}).get("content", "").strip())


def _validate_individual_response(data: dict) -> bool:
    try:
        reviews = data.get("individual_reviews", [])
        if not reviews:
            return False
        scores = reviews[0].get("scores", {})
        for key in ("completeness_score", "code_quality_score", "approach_taken_score"):
            val = float(scores.get(key, -1))
            if not (0 <= val <= 10):
                return False
        if not reviews[0].get("correctness_feedback", "").strip():
            return False
        return True
    except (KeyError, ValueError, TypeError, IndexError):
        return False


def _single_graded_attempt(prompt_content: str, host: str) -> dict:
    attempt_prompt = prompt_content
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = _call_ollama(attempt_prompt, INDIVIDUAL_REVIEW_SCHEMA, host)
            if _validate_individual_response(result):
                return result
            attempt_prompt = (
                prompt_content
                + "\n\nNOTE: Your previous response was invalid (missing fields, "
                  "empty feedback, or a score outside the 0-10 range). "
                  "Return a corrected, complete JSON response."
            )
        except Exception:
            attempt_prompt = prompt_content
    return None


def _median_merge(all_valid_results: list) -> dict:
    first_review_sets = [r.get("individual_reviews", [{}])[0] for r in all_valid_results]
    c_vals = [float(r.get("scores", {}).get("completeness_score", 0)) for r in first_review_sets]
    q_vals = [float(r.get("scores", {}).get("code_quality_score", 0)) for r in first_review_sets]
    a_vals = [float(r.get("scores", {}).get("approach_taken_score", 0)) for r in first_review_sets]

    med_c, med_q, med_a = statistics.median(c_vals), statistics.median(q_vals), statistics.median(a_vals)

    max_spread = max(
        max(c_vals) - min(c_vals),
        max(q_vals) - min(q_vals),
        max(a_vals) - min(a_vals),
    )
    high_variance = max_spread > SCORE_VARIANCE_FLAG_THRESHOLD

    closest_idx = min(range(len(c_vals)), key=lambda i: abs(c_vals[i] - med_c))
    representative_feedback = first_review_sets[closest_idx].get("correctness_feedback", "")

    if high_variance:
        representative_feedback = "[FLAGGED FOR MANUAL REVIEW — model gave inconsistent scores across passes] " + representative_feedback

    return {
        "individual_reviews": [{
            "question_text": first_review_sets[0].get("question_text", ""),
            "correctness_feedback": representative_feedback,
            "scores": {
                "completeness_score": med_c,
                "code_quality_score": med_q,
                "approach_taken_score": med_a,
                "overall_score": (0.5 * med_c) + (0.3 * med_q) + (0.2 * med_a),
            }
        }]
    }


def evaluate_via_local_llm(prompt_content: str, host: str = "http://localhost:11434") -> dict:
    first_result = _single_graded_attempt(prompt_content, host)
    if first_result is None:
        return {"error": "All grading attempts failed validation", "individual_reviews": [{}]}

    first_scores = first_result.get("individual_reviews", [{}])[0].get("scores", {})
    c = float(first_scores.get("completeness_score", 0))
    q = float(first_scores.get("code_quality_score", 0))
    a = float(first_scores.get("approach_taken_score", 0))
    first_overall = (0.5 * c) + (0.3 * q) + (0.2 * a)

    if not (BORDERLINE_SCORE_LOW <= first_overall <= BORDERLINE_SCORE_HIGH):
        return first_result
    all_valid_results = [first_result]
    for _ in range(BORDERLINE_RECHECK_RUNS - 1):
        extra = _single_graded_attempt(prompt_content, host)
        if extra is not None:
            all_valid_results.append(extra)

    if len(all_valid_results) == 1:
        return all_valid_results[0]

    return _median_merge(all_valid_results)

def main():
    TARGET_FILE = "Stage-1.xlsx"
    
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Error: The file '{TARGET_FILE}' was not found.")
        return
    
    try:
        df = pd.read_csv(TARGET_FILE) if TARGET_FILE.endswith('.csv') else pd.read_excel(TARGET_FILE)
        print("✅ Data sheet successfully loaded!")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    df.columns = df.columns.str.strip()
    required_cols = ["QSN No", "User ID", "Question", "Actual Code"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Error: Missing required columns: {missing_cols}")
        return

    filtered_df = df[required_cols].copy().dropna(subset=["Actual Code"])
    filtered_df = filtered_df[filtered_df["Actual Code"].astype(str).str.strip() != ""]
    final_count = len(filtered_df)
    print(f"📊 Rows to process: {final_count}")
    print(f"🎯 Mandated Semester Language Constraints Locked To: {SEMESTER_LANGUAGE}")
    print("=" * 80)

    all_reviews_history = []
    current_count = 0

    print("\n🚀 STARTING LIVE MAP-EVALUATION LOOP\n")
    for idx, row in filtered_df.iterrows():
        current_count += 1
        user_id = row["User ID"]
        qsn_no = row["QSN No"]
        question_text = str(row["Question"])
        code_snippet = str(row["Actual Code"])
        
        expected_lang = determine_expected_language(question_text)
        is_match, detected_label, needs_manual_review = languages_match_deterministic(expected_lang, code_snippet)

        if needs_manual_review:
            feedback = (
                f"MANUAL REVIEW REQUIRED: Could not reliably determine the programming "
                f"language of this submission with sufficient confidence. Please review manually."
            )
            c_val, q_val, a_val, o_val = 0.0, 0.0, 0.0, 0.0
            status = "Manual Review Needed"
        elif not is_match:
            feedback = (
                f"CRITICAL FAILURE: Submitted solution is written in {detected_label}, "
                f"which violates the required semester exam language ({expected_lang})."
            )
            c_val, q_val, a_val, o_val = 0.0, 0.0, 0.0, 0.0
            status = "Language Mismatch"
        else:
            formatted_qa = f"Question Context: {question_text}\nStudent Answer Code:\n{code_snippet}"
            row_prompt = get_base_prompt(language=expected_lang, ques_ans_content_with_inst=formatted_qa, summary_gen_flag=False)

            response_data = evaluate_via_local_llm(row_prompt)
            reviews = response_data.get("individual_reviews", [{}])
            first_review = reviews[0] if len(reviews) > 0 else {}

            feedback = first_review.get("correctness_feedback", "No feedback content generated.")
            scores = first_review.get("scores", {})

            c_val = float(scores.get("completeness_score", 0.0))
            q_val = float(scores.get("code_quality_score", 0.0))
            a_val = float(scores.get("approach_taken_score", 0.0))

            o_val = (0.5 * c_val) + (0.3 * q_val) + (0.2 * a_val)
            status = "Optimal Code" if o_val >= 7.5 else "Needs Revision"

        all_reviews_history.append({
            "question_no": qsn_no,
            "user_id": user_id,
            "feedback": feedback,
            "overall_score": o_val
        })


        print(f"🔷 [RECORD {current_count} / {final_count}]")
        print(f"👤 Student User ID    : {user_id}")
        print(f"❓ Question Number    : {qsn_no}")
        print(f"🎯 Mandated Language  : {expected_lang}")
        print(f"📊 Evaluation Status  : {status}")
        print(f"💬 Correctness Feedback:\n   👉 {feedback}")
        print(f"🔢 Score Breakdown   :")
        print(f"   ├─ Completeness Score  : {c_val} / 10")
        print(f"   ├─ Code Quality Score  : {q_val} / 10")
        print(f"   └─ Approach Taken Score: {a_val} / 10")
        print(f"🏆 CALCULATED OVERALL GRADE: {o_val:.2f} / 10")
        print("=" * 80)


    print("\n⚡ RUNNING GLOBAL SEMESTER BATCH ANALYTICS PASS...\n")
    summary_input = json.dumps(all_reviews_history, indent=2)
    summary_prompt = get_base_prompt(language="Global Context", ques_ans_content_with_inst=summary_input, summary_gen_flag=True)
    
    try:
        global_response = _call_ollama(summary_prompt, SUMMARY_REVIEW_SCHEMA)
    except Exception as e:
        global_response = {"summary_review": {}}
        print(f"⚠️ Summary generation failed: {e}")
    summary_meta = global_response.get("summary_review", {})

    scores_list = [item["overall_score"] for item in all_reviews_history]
    avg_score = sum(scores_list) / len(scores_list) if scores_list else 0.0

    print("█" * 80)
    print("📋 MASTER BATCH EVALUATION SUMMARY REPORT")
    print("█" * 80)
    print(f"📈 Class Average Score      : {avg_score:.2f} / 10")
    print(f"🏷️  Overall Quality Label    : {summary_meta.get('overall_quality_label', 'Unknown')}")
    print(f"⚠️  Common Errors Identified : {summary_meta.get('common_errors', 'None recorded.')}")
    print(f"💪 Core Class Strengths     : {summary_meta.get('strengths', 'None recorded.')}")
    print(f"📉 Core Class Weaknesses    : {summary_meta.get('weaknesses', 'None recorded.')}")
    print(f"💡 Pedagogical Guidance     : {summary_meta.get('recommendations', 'None recorded.')}")
    print("█" * 80)

if __name__ == "__main__":
    main()