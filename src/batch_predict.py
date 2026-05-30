import json
import argparse
from pathlib import Path

from src.models.input import SessionLog
from src.engine import ReviewEngine

def main():
    parser = argparse.ArgumentParser(description="Run Review Engine on a directory of session logs.")
    parser.add_argument("input_dir", type=str, help="Directory containing JSON session files (e.g., data/train/sessions/)")
    parser.add_argument("output_file", type=str, help="Output JSONL file for predictions (e.g., predictions.jsonl)")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    output_path = Path(args.output_file)

    if not input_path.is_dir():
        print(f"ERROR: Directory {input_path} does not exist.")
        return

    engine = ReviewEngine()
    processed_count = 0

    print(f"Starting batch processing from: {input_path}")
    
    with open(output_path, "w", encoding="utf-8") as out_file:
        for json_file in sorted(input_path.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                
                session = SessionLog(**raw_data)
                
                verdict = engine.review_session(session)
                
                prediction_record = verdict.model_dump()
                
                out_file.write(json.dumps(prediction_record) + "\n")
                
                processed_count += 1
                print(f"Processed: {verdict.session_id: <15} -> {verdict.verdict: <10} (Rules triggered: {len(verdict.findings)})")
                
            except Exception as e:
                print(f"Failed to process {json_file.name}: {e}")

    print(f"\nBatch processing complete. Processed {processed_count} files.")
    print(f"Predictions strictly formatted for eval.py saved to: {output_path}")

if __name__ == "__main__":
    main()