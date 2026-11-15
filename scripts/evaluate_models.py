"""
Run evaluation on Model 1 (FrequencyCNN) and Model 2 (EfficientNet-B4) on the real test split.
Outputs clean formatted metrics.
"""

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

models = [
    {
        "name": "FrequencyCNN (Frequency Domain)",
        "config": "ml/configs/_train_real_frequency_cnn.yaml",
        "weights": "checkpoints/frequency_cnn_best.pt",
        "output": "checkpoints/eval_real_frequency_cnn.json"
    },
    {
        "name": "EfficientNet-B4 (Spatial Domain)",
        "config": "ml/configs/_train_real_efficientnet_b4.yaml",
        "weights": "checkpoints/efficientnet_b4_best.pt",
        "output": "checkpoints/eval_real_efficientnet_b4.json"
    }
]

results = {}

for m in models:
    print(f"\nEvaluating {m['name']}...")
    cmd = [
        str(PYTHON), "-m", "ml.evaluate",
        "--config", m["config"],
        "--weights", m["weights"],
        "--device", "cpu",
        "--output", m["output"]
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error evaluating {m['name']}:\n{res.stderr}")
    else:
        print(f"Evaluation finished for {m['name']}.")
        with open(ROOT / m["output"], "r") as f:
            data = json.load(f)
            results[m["name"]] = data
            print(f"  Accuracy:  {data.get('accuracy', 0):.4f}")
            print(f"  AUC-ROC:   {data.get('auc_roc', 0):.4f}")
            print(f"  Precision: {data.get('precision', 0):.4f}")
            print(f"  Recall:    {data.get('recall', 0):.4f}")
            print(f"  F1 Score:  {data.get('f1', 0):.4f}")

with open(ROOT / "checkpoints" / "eval_real_summary.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSummary saved to checkpoints/eval_real_summary.json")

