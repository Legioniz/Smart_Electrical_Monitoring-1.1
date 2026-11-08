#!/usr/bin/env python3
"""Train an isolated, review-only ML artifact from synthetic readings only.

The saved artifact is not auto-loaded by the live detector. Promotion requires a
separate code review and benchmark; generated models cannot edit application code.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import timezone
from pathlib import Path
from datetime import datetime
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sme.paths import ensure_runtime_dirs, MODEL_DIR, LEARNING_DIR
from sme.services.synthetic import generate_meter_series

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-synthetic-only", action="store_true", help="required acknowledgement that no customer data is used")
    parser.add_argument("--seed", type=int, default=20261103)
    args = parser.parse_args()
    if not args.confirm_synthetic_only:
        print("Refusing to train: rerun with --confirm-synthetic-only. This tool uses synthetic data only.")
        return 2
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except ImportError as exc:
        print(f"Missing ML dependency: {exc}")
        return 2
    ensure_runtime_dirs()
    rows, _labels, meta = generate_meter_series(args.seed, 35)
    by_day: dict[str, list] = {}
    for row in rows:
        local = row.interval_start_utc.replace(tzinfo=timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Manila'))
        by_day.setdefault(local.date().isoformat(), []).append((local, float(row.energy_kwh), row.label_type))
    dates = sorted(by_day)
    train_dates, holdout_dates = dates[:14], dates[14:]
    def vector(item):
        local, energy, _label = item
        slot = local.hour + local.minute / 60
        return [energy, float(np.sin(2*np.pi*slot/24)), float(np.cos(2*np.pi*slot/24)), local.weekday(), int(local.weekday() >= 5)]
    train = np.asarray([vector(item) for day in train_dates for item in by_day[day]], dtype=float)
    holdout = np.asarray([vector(item) for day in holdout_dates for item in by_day[day]], dtype=float)
    model = IsolationForest(n_estimators=160, contamination=0.05, random_state=args.seed, n_jobs=1)
    model.fit(train)
    holdout_scores = -model.score_samples(holdout)
    cutoff = float(np.quantile(-model.score_samples(train), 0.95))
    flagged_mask = holdout_scores > cutoff
    flagged = int(flagged_mask.sum())
    holdout_labels = np.asarray([item[2] is not None for day in holdout_dates for item in by_day[day]], dtype=bool)
    true_positive = int(np.logical_and(flagged_mask, holdout_labels).sum())
    false_positive = int(np.logical_and(flagged_mask, ~holdout_labels).sum())
    false_negative = int(np.logical_and(~flagged_mask, holdout_labels).sum())
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    artifact = MODEL_DIR / f"synthetic-isolation-forest-{stamp}.joblib"
    joblib.dump(model, artifact)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "artifact": artifact.name, "sha256": digest, "model": "sklearn.ensemble.IsolationForest",
        "model_version": "sme-synthetic-baseline-v1", "data_source": "synthetic_only",
        "seed": args.seed, "generator": meta, "training_days": train_dates,
        "holdout_days": holdout_dates, "training_rows": int(len(train)),
        "holdout_rows": int(len(holdout)), "score_cutoff": cutoff, "threshold_percentile": 95,
        "holdout_flagged_rows": flagged, "holdout_flag_rate_pct": round(flagged / max(len(holdout), 1) * 100, 3),
        "synthetic_label_precision": round(precision, 4), "synthetic_label_recall": round(recall, 4),
        "synthetic_true_positive": true_positive, "synthetic_false_positive": false_positive,
        "synthetic_false_negative": false_negative,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "promotion_status": "review_required_not_loaded_by_application",
    }
    manifest_path = artifact.with_suffix('.manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    summary = LEARNING_DIR / 'latest-synthetic-training.json'
    summary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f"Saved review-only model: {artifact}")
    print(f"SHA-256: {digest}")
    print(f"Training rows: {len(train)}; holdout rows: {len(holdout)}; flagged holdout rows: {flagged}")
    print(f"Synthetic-only precision: {precision:.3f}; recall: {recall:.3f} (not real-world performance)")
    print("This artifact is not used by the running application until reviewed and deliberately promoted.")
    return 0
if __name__ == '__main__': raise SystemExit(main())
