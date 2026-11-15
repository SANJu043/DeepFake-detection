"""
Train Model 1 (FrequencyCNN) and Model 2 (EfficientNet-B4) on real data.
Runs sequentially to avoid CPU resource contention.
"""
import subprocess
import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
os.chdir(PROJECT_ROOT)
os.environ["PYTHONPATH"] = PROJECT_ROOT

def run_training(config_name, model_label):
    print(f"\n{'='*60}")
    print(f"  TRAINING {model_label}")
    print(f"  Config: {config_name}")
    print(f"  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n", flush=True)
    
    start = time.time()
    result = subprocess.run(
        [PYTHON, "-m", "ml.train", "--config", config_name, "--device", "cpu"],
        cwd=PROJECT_ROOT,
        env=os.environ,
        capture_output=False,  # Let output flow to stdout/stderr
    )
    elapsed = time.time() - start
    
    print(f"\n{'='*60}")
    print(f"  {model_label} FINISHED")
    print(f"  Exit code: {result.returncode}")
    print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"{'='*60}\n", flush=True)
    
    return result.returncode

# ---- Train FrequencyCNN ----
rc1 = run_training("ml/configs/_train_real_frequency_cnn.yaml", "MODEL 1: FrequencyCNN")

# ---- Train EfficientNet-B4 ----
rc2 = run_training("ml/configs/_train_real_efficientnet_b4.yaml", "MODEL 2: EfficientNet-B4")

print(f"\n{'='*60}")
print(f"  ALL TRAINING COMPLETE")
print(f"  FrequencyCNN exit code: {rc1}")
print(f"  EfficientNet-B4 exit code: {rc2}")
print(f"{'='*60}")

