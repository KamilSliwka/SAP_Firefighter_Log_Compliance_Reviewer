import json
import argparse
import sys
from pathlib import Path

from src.models.input import SessionLog
from src.engine import ReviewEngine

def main():
    parser = argparse.ArgumentParser(description="SAP Firefighter Log AI Reviewer")
    parser.add_argument("input_file", type=str, help="Path to the session log JSON file (e.g., data/train/sessions/FF-TRAIN-0001.json)")
    args = parser.parse_args()

    file_path = Path(args.input_file)
    
    if not file_path.exists():
        print(f"ERROR: File {file_path} does not exist.")
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        session = SessionLog(**raw_data)
        
    except json.JSONDecodeError:
        print("ERROR: The file is not a valid JSON file.")
        sys.exit(1)
    except Exception as e:
        print(f"PYDANTIC VALIDATION ERROR: Missing required fields or invalid data.\nDetails: {e}")
        sys.exit(1)

    engine = ReviewEngine()
    verdict = engine.review_session(session)

    print(verdict.model_dump_json(indent=2))

if __name__ == "__main__":
    main()