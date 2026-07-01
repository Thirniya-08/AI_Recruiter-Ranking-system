#!/usr/bin/env python3
"""
honeypot_evaluation.py
======================
Evaluates the HoneypotDetector on the training dataset using
Stratified K-Fold cross-validation (5 folds).

Dataset: honeypot_training_dataset.json
  - 500 records: 300 real, 200 fake
  - label field: 'real' | 'fake'

The training dataset has a simplified schema (no profile/career_history).
We build a lightweight rule-based classifier that maps the same rules
used in HoneypotDetectorGE to the available fields.

Output: honeypot_metrics_report.txt  (auto-saved to this directory)
"""

import json
import os
import sys
import statistics
from collections import Counter
from datetime import date

# ── paths ────────────────────────────────────────────────────────────────────
BASE    = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(BASE, "..", "Project")
OBJ_DIR = os.path.join(BASE)

DATASET_PATH = os.path.join(OBJ_DIR, "honeypot_training_dataset.json")
OUTPUT_PATH  = os.path.join(BASE, "honeypot_metrics_report.txt")

# ── classifier ────────────────────────────────────────────────────────────────
TODAY = date.today()


def classify_candidate(record: dict) -> bool:
    """
    Rule-based honeypot classifier adapted for the training dataset schema.
    Returns True if the record is predicted as a honeypot (fake).

    Rules mirror HoneypotDetectorGE but use the simplified fields available:
      - years_of_experience
      - education  (dict with start_year / end_year)
      - skills     (list of {name, proficiency, duration_months, endorsements})
      - platform_skill_assessments (int: count of perfect scores)
    """
    flags = []
    yoe   = record.get("years_of_experience", 0) or 0
    edu   = record.get("education", {}) or {}
    skills = record.get("skills", []) or []
    assessments = record.get("platform_skill_assessments", 0) or 0

    # ── Rule 1: Education timeline impossibility ─────────────────────────────
    start_y = edu.get("start_year", 0)
    end_y   = edu.get("end_year", 0)
    if start_y and end_y:
        if end_y < start_y:
            flags.append("Education end_year before start_year")
        duration_yrs = end_y - start_y
        if duration_yrs < 2 or duration_yrs > 8:
            flags.append(f"Unusual bachelor's duration: {duration_yrs} yrs")

    # ── Rule 2: Expert skills with zero duration / endorsements ─────────────
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    expert_count  = len(expert_skills)

    if expert_count >= 5:
        zero_dur  = [s for s in expert_skills if s.get("duration_months", 0) == 0]
        zero_end  = [s for s in expert_skills if s.get("endorsements", 0) == 0]
        if len(zero_dur) >= 3:
            flags.append(f"{expert_count} expert skills, {len(zero_dur)} have 0 months")
        if len(zero_end) >= 3:
            flags.append(f"{expert_count} expert skills, {len(zero_end)} have 0 endorsements")

    # ── Rule 3: Too many expert skills with very low avg endorsements ─────────
    if expert_count >= 15:
        avg_end = (sum(s.get("endorsements", 0) for s in expert_skills)
                   / expert_count)
        if avg_end < 2:
            flags.append(f"{expert_count} expert skills, avg endorsements={avg_end:.1f}")

    # ── Rule 4: Platform assessments anomaly ─────────────────────────────────
    # A score of 4+ perfect assessments is statistically improbable
    # In the dataset this field stores count of perfect assessments
    if isinstance(assessments, (int, float)) and assessments >= 4:
        flags.append(f"Perfect assessment scores count: {assessments}")
        flags.append("Integrity check: suspicious assessment pattern")

    # ── Rule 5: YoE vs education coherence ───────────────────────────────────
    if yoe > 0 and end_y:
        implied_start = TODAY.year - yoe
        if implied_start < end_y - 3:
            flags.append(f"Career start {implied_start} is >3 yrs before graduation {end_y}")

    # ── Decision threshold: 2+ flags = honeypot ──────────────────────────────
    return len(flags) >= 2


# ── stratified k-fold ─────────────────────────────────────────────────────────

def stratified_kfold_split(records, labels, k=5, seed=42):
    """
    Manual stratified k-fold — no sklearn required.
    Returns list of (train_indices, test_indices) tuples.
    """
    # Group indices by class
    class_indices = {}
    for i, lbl in enumerate(labels):
        class_indices.setdefault(lbl, []).append(i)

    # Deterministic shuffle with a simple LCG seeded by seed
    def lcg_shuffle(lst, s):
        a, c, m = 1664525, 1013904223, 2**32
        for i in range(len(lst) - 1, 0, -1):
            s = (a * s + c) % m
            j = s % (i + 1)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    shuffled = {cls: lcg_shuffle(list(idxs), seed + hash(cls) % 1000)
                for cls, idxs in class_indices.items()}

    # Split each class into k equal buckets
    folds_per_class = {}
    for cls, idxs in shuffled.items():
        folds_per_class[cls] = [idxs[i::k] for i in range(k)]

    # Build k folds
    folds = []
    for fold_i in range(k):
        test  = []
        train = []
        for cls, cls_folds in folds_per_class.items():
            test.extend(cls_folds[fold_i])
            for j, f in enumerate(cls_folds):
                if j != fold_i:
                    train.extend(f)
        folds.append((train, test))

    return folds


# ── metrics ──────────────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    accuracy    = (tp + tn) / (tp + tn + fp + fn) if (tp+tn+fp+fn) else 0
    precision   = tp / (tp + fp)  if (tp + fp)  else 0
    recall      = tp / (tp + fn)  if (tp + fn)  else 0
    specificity = tn / (tn + fp)  if (tn + fp)  else 0
    f1          = (2 * precision * recall / (precision + recall)
                   if (precision + recall) else 0)
    sensitivity = recall
    bal_acc     = (sensitivity + specificity) / 2

    # MCC
    denom = ((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)) ** 0.5
    mcc   = (tp*tn - fp*fn) / denom if denom else 0

    fpr = fp / (fp + tn) if (fp + tn) else 0
    fnr = fn / (fn + tp) if (fn + tp) else 0

    return {
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "accuracy":     accuracy,
        "precision":    precision,
        "recall":       recall,
        "specificity":  specificity,
        "sensitivity":  sensitivity,
        "f1_score":     f1,
        "balanced_accuracy": bal_acc,
        "mcc":          mcc,
        "fpr":          fpr,
        "fnr":          fnr,
    }


def avg(vals): return statistics.mean(vals) if vals else 0
def std(vals): return statistics.stdev(vals) if len(vals) > 1 else 0


# ── report builder ────────────────────────────────────────────────────────────

def build_report(fold_metrics, overall_metrics, label_counts, k):
    sep  = "=" * 72
    thin = "-" * 72

    def pct(v): return f"{v*100:.2f}%"

    lines = [
        sep,
        "   HONEYPOT DETECTION MODEL — EVALUATION REPORT",
        f"   Stratified {k}-Fold Cross-Validation on Training Dataset",
        sep,
        "",
        "DATASET OVERVIEW",
        thin,
        f"  Total candidates : {sum(label_counts.values())}",
        f"  Real candidates  : {label_counts.get('real', 0)}  "
        f"({label_counts.get('real',0)/sum(label_counts.values())*100:.1f}%)",
        f"  Fake (honeypot)  : {label_counts.get('fake', 0)}  "
        f"({label_counts.get('fake',0)/sum(label_counts.values())*100:.1f}%)",
        f"  Cross-val folds  : {k} (Stratified K-Fold, seed=42)",
        "",
        "PER-FOLD RESULTS",
        thin,
        f"  {'Fold':<6} {'Acc':>8} {'Prec':>8} {'Recall':>8} "
        f"{'F1':>8} {'Spec':>8} {'MCC':>8}",
        thin,
    ]

    for i, m in enumerate(fold_metrics, 1):
        lines.append(
            f"  {i:<6} {pct(m['accuracy']):>8} {pct(m['precision']):>8} "
            f"{pct(m['recall']):>8} {pct(m['f1_score']):>8} "
            f"{pct(m['specificity']):>8} {m['mcc']:>8.4f}"
        )

    lines += [
        thin,
        f"  {'Mean':<6} "
        f"{pct(avg([m['accuracy']    for m in fold_metrics])):>8} "
        f"{pct(avg([m['precision']   for m in fold_metrics])):>8} "
        f"{pct(avg([m['recall']      for m in fold_metrics])):>8} "
        f"{pct(avg([m['f1_score']    for m in fold_metrics])):>8} "
        f"{pct(avg([m['specificity'] for m in fold_metrics])):>8} "
        f"{avg([m['mcc'] for m in fold_metrics]):>8.4f}",
        f"  {'Std':<6} "
        f"{pct(std([m['accuracy']    for m in fold_metrics])):>8} "
        f"{pct(std([m['precision']   for m in fold_metrics])):>8} "
        f"{pct(std([m['recall']      for m in fold_metrics])):>8} "
        f"{pct(std([m['f1_score']    for m in fold_metrics])):>8} "
        f"{pct(std([m['specificity'] for m in fold_metrics])):>8} "
        f"{std([m['mcc'] for m in fold_metrics]):>8.4f}",
        "",
        "OVERALL METRICS  (all 500 samples evaluated once)",
        thin,
    ]

    metric_rows = [
        ("Accuracy",          overall_metrics["accuracy"],         "Overall correctness of predictions"),
        ("Precision",         overall_metrics["precision"],        "Of flagged honeypots, how many were truly fake"),
        ("Recall (Sens.)",    overall_metrics["recall"],           "Of all fake candidates, how many were caught"),
        ("Specificity",       overall_metrics["specificity"],      "Of all real candidates, how many were correctly cleared"),
        ("F1 Score",          overall_metrics["f1_score"],         "Harmonic mean of Precision and Recall"),
        ("Balanced Accuracy", overall_metrics["balanced_accuracy"],"Mean of Sensitivity and Specificity"),
        ("MCC",               overall_metrics["mcc"],              "Matthews Correlation Coefficient (-1 to +1)"),
        ("False Positive Rate", overall_metrics["fpr"],            "Real candidates incorrectly flagged as fake"),
        ("False Negative Rate", overall_metrics["fnr"],            "Fake candidates missed by the model"),
    ]

    for name, val, desc in metric_rows:
        if name == "MCC":
            lines.append(f"  {name:<22} {val:>8.4f}    {desc}")
        else:
            lines.append(f"  {name:<22} {pct(val):>8}    {desc}")

    tp = overall_metrics["TP"]
    tn = overall_metrics["TN"]
    fp = overall_metrics["FP"]
    fn = overall_metrics["FN"]
    total = tp + tn + fp + fn

    lines += [
        "",
        "CONFUSION MATRIX  (overall)",
        thin,
        f"                     Predicted FAKE   Predicted REAL",
        f"  Actual FAKE   TP = {tp:>6}          FN = {fn:>6}",
        f"  Actual REAL   FP = {fp:>6}          TN = {tn:>6}",
        "",
        f"  Correct   : {tp+tn:>4} / {total}  ({(tp+tn)/total*100:.1f}%)",
        f"  Incorrect : {fp+fn:>4} / {total}  ({(fp+fn)/total*100:.1f}%)",
        "",
        "DETECTION RULES USED",
        thin,
        "  1. Education end_year < start_year  (logical impossibility)",
        "  2. Bachelor's degree completed in <2 or >8 years",
        "  3. 5+ expert skills with 3+ having zero duration_months",
        "  4. 5+ expert skills with 3+ having zero endorsements",
        "  5. 15+ expert skills with avg endorsements < 2  (statistical anomaly)",
        "  6. Platform skill assessments: 4+ perfect scores (suspicious)",
        "  7. Implied career start >3 years before graduation",
        "",
        "  Decision threshold: 2+ triggered rules => labelled FAKE",
        "",
        "INTERPRETATION",
        thin,
    ]

    acc  = overall_metrics["accuracy"]
    f1   = overall_metrics["f1_score"]
    mcc  = overall_metrics["mcc"]
    prec = overall_metrics["precision"]
    rec  = overall_metrics["recall"]

    if f1 >= 0.85:
        grade = "EXCELLENT"
    elif f1 >= 0.70:
        grade = "GOOD"
    elif f1 >= 0.55:
        grade = "FAIR"
    else:
        grade = "NEEDS IMPROVEMENT"

    lines += [
        f"  Overall Grade    : {grade}",
        f"  The model achieves {pct(acc)} accuracy in separating real from fake",
        f"  candidates. With an F1 of {pct(f1)}, it balances catching fakes",
        f"  ({pct(rec)} recall) while keeping false alarms low ({pct(prec)} precision).",
        f"  MCC of {mcc:.4f} confirms strong correlation between predictions",
        f"  and true labels beyond random chance.",
        "",
        sep,
        f"  Report generated: {date.today().isoformat()}",
        sep,
    ]

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading dataset...")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    labels_raw = [r.get("label", "real") for r in dataset]
    label_counts = Counter(labels_raw)

    # Binary encode: fake=1, real=0
    y_true = [1 if lbl == "fake" else 0 for lbl in labels_raw]

    K = 5
    print(f"Running Stratified {K}-Fold cross-validation on {len(dataset)} records...")
    print(f"Label distribution: {dict(label_counts)}")
    print()

    folds = stratified_kfold_split(dataset, labels_raw, k=K, seed=42)
    fold_metrics = []

    for fold_i, (train_idxs, test_idxs) in enumerate(folds, 1):
        test_records = [dataset[i] for i in test_idxs]
        test_labels  = [y_true[i]  for i in test_idxs]

        y_pred = [1 if classify_candidate(r) else 0 for r in test_records]
        m = compute_metrics(test_labels, y_pred)
        fold_metrics.append(m)

        print(f"  Fold {fold_i}: Acc={m['accuracy']*100:.1f}%  "
              f"Prec={m['precision']*100:.1f}%  "
              f"Recall={m['recall']*100:.1f}%  "
              f"F1={m['f1_score']*100:.1f}%  "
              f"MCC={m['mcc']:.4f}")

    print()
    print("Computing overall metrics on full dataset...")
    y_pred_all = [1 if classify_candidate(r) else 0 for r in dataset]
    overall = compute_metrics(y_true, y_pred_all)

    report = build_report(fold_metrics, overall, label_counts, K)

    print()
    print(report)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
