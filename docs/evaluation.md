# DeepAuth — Model Evaluation Methodology

> This document describes how DeepAuth's detection models are evaluated, the datasets used, expected (aspirational) performance targets, and how to reproduce evaluation results. All numerical targets are aspirational figures for a university project; actual results depend on training data, hyperparameters, hardware, and implementation quality.

---

## Table of Contents

1. [Evaluation Datasets](#1-evaluation-datasets)
2. [Evaluation Metrics](#2-evaluation-metrics)
3. [Performance Targets](#3-performance-targets)
4. [Cross-Dataset Generalisation](#4-cross-dataset-generalisation)
5. [Confusion Matrix Interpretation](#5-confusion-matrix-interpretation)
6. [Threshold Sweep and Operating Points](#6-threshold-sweep-and-operating-points)
7. [Running the Evaluation](#7-running-the-evaluation)
8. [GradCAM Visualisation](#8-gradcam-visualisation)
9. [Limitations and Known Failure Modes](#9-limitations-and-known-failure-modes)

---

## 1. Evaluation Datasets

### 1.1 FaceForensics++ (FF++)

| Attribute | Value |
|-----------|-------|
| **Paper** | Rössler et al., ICCV 2019 |
| **Videos** | ~1,000 original + manipulated variants per method |
| **Manipulation methods** | Deepfakes (DF), Face2Face (F2F), FaceSwap (FS), NeuralTextures (NT) |
| **Compression** | Raw (c0), low (c23), high (c40) quality variants |
| **Split** | Official train/val/test (720/140/140 videos) |
| **Why used** | Standard benchmark; covers multiple manipulation methods; well-understood baseline |

Download requires academic license: [https://github.com/ondyari/FaceForensics](https://github.com/ondyari/FaceForensics)

---

### 1.2 Deepfake Detection Challenge (DFDC)

| Attribute | Value |
|-----------|-------|
| **Paper** | Dolhansky et al., 2020 |
| **Videos** | ~100,000 clips (train) + 10,000 (test) |
| **Diversity** | Multiple ethnic backgrounds, ages, lighting conditions, compression levels |
| **Manipulation methods** | Undisclosed proprietary methods; more diverse than FF++ |
| **Why used** | Largest public deepfake dataset; diverse demographics; harder generalisation target |

Dataset: [https://ai.meta.com/datasets/dfdc/](https://ai.meta.com/datasets/dfdc/)

---

### 1.3 Celeb-DF v2

| Attribute | Value |
|-----------|-------|
| **Paper** | Li et al., CVPR 2020 |
| **Videos** | 590 real + 5,639 deepfake (celebrities) |
| **Generation method** | Improved face-swap pipeline with refined temporal consistency |
| **Why used** | High visual quality fakes; known to defeat older detectors; good upper-bound difficulty |

Dataset: [https://github.com/yuezunli/celeb-deepfakeforensics](https://github.com/yuezunli/celeb-deepfakeforensics)

---

### 1.4 Dataset Splits

For cross-dataset evaluation, models are trained on one dataset and tested on another:

```
Training set  →  Test set           (Evaluation type)
─────────────────────────────────────────────────────
FF++ (c23)    →  FF++ (c23/c40)     In-distribution
FF++ (c23)    →  Celeb-DF v2        Cross-dataset
FF++ (c23)    →  DFDC               Cross-dataset
DFDC          →  Celeb-DF v2        Cross-dataset
```

---

## 2. Evaluation Metrics

### 2.1 Primary Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| **AUC-ROC** | Area under ROC curve | Threshold-independent; primary ranking metric |
| **Accuracy** | (TP + TN) / N | At default threshold (0.50) |
| **Precision** | TP / (TP + FP) | Positive class = manipulated |
| **Recall (Sensitivity)** | TP / (TP + FN) | Fraction of fakes caught |
| **F1-Score** | 2 × (P × R) / (P + R) | Harmonic mean of precision and recall |
| **EER** | Equal Error Rate (FPR = FNR) | Lower is better |

### 2.2 Verdict-Level Metrics

Since DeepAuth outputs three verdict labels (not just binary), we additionally report:

| Metric | Description |
|--------|-------------|
| **3-class accuracy** | Fraction of samples where the verdict label matches ground truth bin |
| **INCONCLUSIVE rate** | Fraction of samples landing in the 0.30–0.70 band |
| **False-safe rate** | P(verdict = NO_MANIPULATION_DETECTED \| ground truth = fake) |
| **False-alarm rate** | P(verdict = LIKELY_MANIPULATED \| ground truth = real) |

---

## 3. Performance Targets

> [!IMPORTANT]
> The figures below are **aspirational targets** for a university-scale project. They represent reasonable expectations based on published results for similar architectures. Actual performance depends on training data quality, fine-tuning, and implementation details.

### 3.1 Individual Model Targets (In-Distribution: FF++ c23)

| Model | AUC-ROC | Accuracy | F1-Score | EER |
|-------|---------|----------|----------|-----|
| EfficientNet-B4 (spatial) | ≥ 0.97 | ≥ 93% | ≥ 0.93 | ≤ 7% |
| FrequencyCNN (frequency) | ≥ 0.93 | ≥ 89% | ≥ 0.89 | ≤ 10% |
| TemporalBiGRU (temporal) | ≥ 0.90 | ≥ 86% | ≥ 0.86 | ≤ 12% |
| **Weighted Ensemble** | **≥ 0.98** | **≥ 95%** | **≥ 0.95** | **≤ 5%** |

### 3.2 Cross-Dataset Targets

| Train → Test | Model | Target AUC-ROC | Target Accuracy |
|-------------|-------|----------------|----------------|
| FF++ → Celeb-DF v2 | Ensemble | ≥ 0.80 | ≥ 75% |
| FF++ → DFDC | Ensemble | ≥ 0.75 | ≥ 70% |
| DFDC → Celeb-DF v2 | Ensemble | ≥ 0.78 | ≥ 73% |

### 3.3 Per-Manipulation Targets (FF++ c23)

| Manipulation Type | Target AUC-ROC |
|------------------|----------------|
| Deepfakes (DF) | ≥ 0.97 |
| Face2Face (F2F) | ≥ 0.96 |
| FaceSwap (FS) | ≥ 0.95 |
| NeuralTextures (NT) | ≥ 0.93 |

### 3.4 Compression Robustness

| Compression | Target AUC-ROC |
|-------------|----------------|
| Raw (c0) | ≥ 0.99 |
| Low (c23) | ≥ 0.97 |
| High (c40) | ≥ 0.85 |

> [!NOTE]
> FrequencyCNN performance degrades most with high compression (c40), since JPEG/H.264 artefacts can mask frequency-domain manipulation signatures.

---

## 4. Cross-Dataset Generalisation

Cross-dataset evaluation is the most reliable indicator of real-world performance, since it tests whether a model has learned genuine manipulation artefacts rather than dataset-specific biases.

### Common generalisation failure modes

| Failure Mode | Cause | Mitigation |
|-------------|-------|-----------|
| Background texture bias | Model memorises dataset-specific backgrounds | Random crop + colour jitter augmentation |
| Face detector mismatch | Different face sizes/poses not seen in training | Multi-scale face detection; align augmentation |
| Compression-domain overfit | Only seen one codec | Train with mixed compression; online H.264 encoding augmentation |
| Identity leakage | Model memorises celebrity faces | Stratify splits by identity; blur identity features in ablation |

### Recommended evaluation protocol

1. Train **only** on the designated training split.
2. Use the **validation split** for threshold tuning and early stopping.
3. Report numbers on the **held-out test split** (run once).
4. For cross-dataset, use the **entire target dataset** as the test set without any fine-tuning.

---

## 5. Confusion Matrix Interpretation

For the binary classification task (real vs. fake) at the default threshold (0.50):

```
                   Predicted
                 Real    Fake
Actual  Real  [  TN   |  FP  ]  ← False alarms
        Fake  [  FN   |  TP  ]  ← Missed fakes
```

**Interpreting results for deepfake detection:**

- **High false-negative rate (FN / (FN + TP) is high):**
  - Many fakes are missed. The system under-detects. Dangerous for trust applications.
  - Consider lowering the LIKELY_MANIPULATED threshold or retraining.

- **High false-positive rate (FP / (FP + TN) is high):**
  - Authentic videos are incorrectly flagged. Erodes user trust.
  - Consider raising the threshold or improving precision.

- **Wide INCONCLUSIVE band (0.30–0.70):**
  - The system appropriately declines to commit on ambiguous inputs.
  - Target: INCONCLUSIVE rate ≤ 20% on in-distribution data; higher cross-dataset is acceptable.

### Example confusion matrix (aspirational, FF++ c23, ensemble)

```
              Predicted Real    Predicted Fake
Actual Real        1,350              50        (3.6% FPR)
Actual Fake           40           1,360        (97.1% TPR)
```

---

## 6. Threshold Sweep and Operating Points

The ensemble produces a continuous score ∈ [0, 1]. The verdicts are determined by configurable thresholds (`LOW_THRESHOLD`, `HIGH_THRESHOLD`):

| Configuration | LOW_THRESHOLD | HIGH_THRESHOLD | Use Case |
|--------------|--------------|----------------|----------|
| Default | 0.30 | 0.70 | General use |
| High precision | 0.20 | 0.85 | Minimise false alarms (media organisations) |
| High recall | 0.40 | 0.60 | Maximise fake detection (content moderation) |

### How to run a threshold sweep

```bash
python -m ml.evaluate \
  --config configs/eval_ffpp.yaml \
  --threshold-sweep \
  --sweep-min 0.1 \
  --sweep-max 0.9 \
  --sweep-steps 50 \
  --output-dir results/threshold_sweep/
```

This produces a CSV with precision, recall, F1, and accuracy at each threshold, and plots the ROC curve.

---

## 7. Running the Evaluation

### 7.1 Prerequisites

```bash
pip install -r requirements-eval.txt
# Requires: torch, torchvision, scikit-learn, matplotlib, seaborn, facenet-pytorch
```

### 7.2 Prepare datasets

```bash
# FaceForensics++
python -m ml.data.prepare_ffpp \
  --raw-dir /data/FaceForensics++ \
  --output-dir /data/processed/ffpp \
  --compression c23

# Celeb-DF v2
python -m ml.data.prepare_celebdf \
  --raw-dir /data/Celeb-DF-v2 \
  --output-dir /data/processed/celebdf

# DFDC
python -m ml.data.prepare_dfdc \
  --raw-dir /data/DFDC \
  --output-dir /data/processed/dfdc
```

### 7.3 Run standard evaluation

```bash
# Evaluate ensemble on FF++ c23 test split
python -m ml.evaluate \
  --config configs/eval_ffpp_c23.yaml \
  --checkpoint checkpoints/ensemble_v2.pt \
  --split test \
  --output-dir results/ffpp_c23/

# Evaluate each individual model
python -m ml.evaluate \
  --config configs/eval_ffpp_c23.yaml \
  --model efficientnet_b4 \
  --checkpoint checkpoints/efficientnet_b4_v2.pt \
  --split test \
  --output-dir results/ffpp_c23/effnet/

python -m ml.evaluate \
  --config configs/eval_ffpp_c23.yaml \
  --model frequency_cnn \
  --checkpoint checkpoints/frequency_cnn_v1.pt \
  --split test \
  --output-dir results/ffpp_c23/freqcnn/

python -m ml.evaluate \
  --config configs/eval_ffpp_c23.yaml \
  --model temporal_bigru \
  --checkpoint checkpoints/temporal_bigru_v1.pt \
  --split test \
  --output-dir results/ffpp_c23/bigru/
```

### 7.4 Cross-dataset evaluation

```bash
# Train on FF++, test on Celeb-DF v2
python -m ml.evaluate \
  --config configs/eval_cross.yaml \
  --train-dataset ffpp \
  --test-dataset celebdf \
  --checkpoint checkpoints/ensemble_v2.pt \
  --output-dir results/cross_ffpp_celebdf/

# Train on FF++, test on DFDC
python -m ml.evaluate \
  --config configs/eval_cross.yaml \
  --train-dataset ffpp \
  --test-dataset dfdc \
  --checkpoint checkpoints/ensemble_v2.pt \
  --output-dir results/cross_ffpp_dfdc/
```

### 7.5 Output files

Each evaluation run produces:

```
results/<run_name>/
├── metrics.json          # AUC-ROC, accuracy, F1, EER, etc.
├── confusion_matrix.png  # Confusion matrix heatmap
├── roc_curve.png         # ROC curve with AUC annotation
├── score_distribution.png  # Histogram of scores (real vs fake)
├── per_method_metrics.json  # (FF++ only) metrics per manipulation type
└── predictions.csv       # video_id, true_label, score, verdict
```

### 7.6 Evaluation configuration file

Example `configs/eval_ffpp_c23.yaml`:

```yaml
dataset:
  name: ffpp
  root: /data/processed/ffpp
  compression: c23
  split: test

model:
  type: ensemble
  efficientnet_b4:
    checkpoint: checkpoints/efficientnet_b4_v2.pt
    weight: 0.4
  frequency_cnn:
    checkpoint: checkpoints/frequency_cnn_v1.pt
    weight: 0.3
  temporal_bigru:
    checkpoint: checkpoints/temporal_bigru_v1.pt
    weight: 0.3

inference:
  batch_size: 32
  num_frames: 32
  face_detector: retinaface
  device: cuda

thresholds:
  low: 0.30
  high: 0.70

output:
  dir: results/ffpp_c23/
  save_predictions: true
```

---

## 8. GradCAM Visualisation

GradCAM highlights which regions of a frame contributed most to the ensemble's decision, aiding interpretability and debugging.

### 8.1 Generate GradCAM heatmaps

```bash
# Single video
python -m ml.explain.gradcam \
  --video /path/to/video.mp4 \
  --checkpoint checkpoints/efficientnet_b4_v2.pt \
  --model efficientnet_b4 \
  --target-layer features.8 \
  --output-dir results/gradcam/

# Batch over evaluation set
python -m ml.explain.gradcam \
  --config configs/eval_ffpp_c23.yaml \
  --checkpoint checkpoints/efficientnet_b4_v2.pt \
  --n-samples 100 \
  --output-dir results/gradcam_batch/
```

### 8.2 Output format

For each video, the script produces:
- `frame_<N>_original.png` — original frame
- `frame_<N>_heatmap.png` — GradCAM activation overlaid on frame
- `frame_<N>_overlay.png` — blended composite (alpha = 0.4)

### 8.3 Interpreting GradCAM output

| Activation pattern | Interpretation |
|-------------------|----------------|
| Concentrated around facial boundaries / jaw | Typical face-swap artefact localisation |
| Uniform activation over face | Model using global texture cues |
| Activation on background / hair | Possible dataset bias; check if model is using spurious features |
| No clear pattern | Model is uncertain; often correlates with INCONCLUSIVE verdict |

> [!TIP]
> Use GradCAM during development to verify that the model is attending to face regions rather than dataset-specific background cues (e.g., green-screen studios in some datasets).

---

## 9. Limitations and Known Failure Modes

### 9.1 Generalisation to New Generation Methods

Models trained on FF++/DFDC/Celeb-DF may not generalise to deepfakes produced by methods released after the training data was collected (e.g., diffusion-based methods, one-shot face reenactment). Periodic retraining with new data is required.

### 9.2 Compressed Video Degradation

| Compression Level | Expected AUC Drop vs. Raw |
|------------------|--------------------------|
| Low (c23) | ~ 2–5 percentage points |
| High (c40) | ~ 10–20 percentage points |

FrequencyCNN is most affected; EfficientNet-B4 is more robust to compression due to its spatial focus.

### 9.3 Low Face Coverage

Videos with:
- Faces < 64×64 pixels (after crop)
- Face present in < 20% of sampled frames
- Severe occlusion (masks, sunglasses)

...will have fewer valid frames for inference, increasing variance of the ensemble score. Such videos are more likely to land in the INCONCLUSIVE band.

### 9.4 Non-Face Deepfakes

The pipeline is optimised for **face-swap** and **face reenactment** deepfakes. It is not designed to detect:
- Body puppetry / full-body synthesis
- Background scene manipulation
- Audio deepfakes
- Text or document forgeries

### 9.5 Adversarial Robustness

The models are **not adversarially trained by default**. A white-box adversarial attack (e.g., PGD with ℓ∞ ε = 4/255) can be expected to significantly reduce detection accuracy. Adversarial training (Madry et al.) would improve robustness at some cost to clean accuracy.

### 9.6 Temporal Model Limitations

TemporalBiGRU requires a sequence of face crops. For short clips (< 8 valid frames after face detection), the temporal model is bypassed and the ensemble falls back to a 2-model average (EfficientNet-B4 + FrequencyCNN only), which may reduce accuracy.
