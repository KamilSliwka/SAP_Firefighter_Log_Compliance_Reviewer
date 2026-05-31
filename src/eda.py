import json
from collections import Counter, defaultdict
from pathlib import Path

def main():
    labels_path = Path("data/train/labels.jsonl")

    if not labels_path.exists():
        print(f"ERROR: File {labels_path} not found. Please ensure the path is correct.")
        return

    verdicts = Counter()
    rules_counter = Counter()
    
    r010_evidence = set()
    r002_evidence = set()
    unknown_rules = defaultdict(list)

    with open(labels_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            data = json.loads(line)
            verdicts[data.get("verdict", "UNKNOWN")] += 1
            
            for finding in data.get("findings", []):
                rule_id = finding.get("rule_id", "UNKNOWN")
                rules_counter[rule_id] += 1
                
                evidence_text = f"Evidence: {finding.get('evidence', '')} | Desc: {finding.get('description', '')}"
                
                if rule_id == "R-010":
                    r010_evidence.add(evidence_text)
                elif rule_id == "R-002":
                    r002_evidence.add(evidence_text)
                elif rule_id not in [f"R-{i:03d}" for i in range(1, 11)]:
                    unknown_rules[rule_id].append(finding.get("description", ""))


    print("=" * 60)
    print("EDA REPORT: Exploratory Data Analysis (labels.jsonl)")
    print("=" * 60)
    
    print("\n1. VERDICT DISTRIBUTION:")
    for v, count in verdicts.items():
        print(f"  - {v}: {count}")
        
    print("\n2. RULE FREQUENCY (Gold Labels):")
    for r, count in rules_counter.most_common():
        print(f"  - {r}: {count}")
        
    print("\n3. HIDDEN RULES (Outside baseline R-001 to R-010):")
    if not unknown_rules:
        print("  None! All rules are within the R-001 to R-010 range.")
    else:
        for r, desc_list in unknown_rules.items():
            print(f"  [ALERT] Undocumented rule detected: {r}")
            print(f"          Example description: {desc_list[0]}")

    print("\n4. R-010 INVESTIGATION (Which SoD pairs were tested?):")
    if not r010_evidence:
        print("  No R-010 examples found in this dataset.")
    for ev in r010_evidence:
        print(f"  - {ev}")

    print("\n5. R-002 INVESTIGATION (Which module conflicts did our LLM miss?):")
    if not r002_evidence:
        print("  No R-002 examples found in this dataset.")
    for ev in r002_evidence:
        print(f"  - {ev}")

if __name__ == "__main__":
    main()