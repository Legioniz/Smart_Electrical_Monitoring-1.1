# Detection methods: catalog, theory, optimization, explainability

Contents: 1 Principles; 2 Evidence from recent literature; 3 Method catalog; 4 Build path; 5 Calibration and thresholds; 6 Optimization and tuning; 7 Explainability; 8 Evaluation; 9 Provenance and no fabricated alerts; 10 Status labels

## 1. Principles
- Real detection only: an alert exists because a detector ran on stored readings.
- Complexity must earn its place: add a method only if it beats the simpler baseline on the time-split synthetic benchmark and can be explained in plain words.
- Prefer methods that need no labeled theft data; real labels are scarce.
- Never claim "state of the art", and never present a paper's accuracy as this system's.

## 2. Evidence from recent literature (checked 2026-10-30; not exhaustive)
- Recent reviews of data-driven theft and anomaly detection (read as abstracts; venue and year not verified) group methods into supervised, unsupervised, deep, and hybrid. Common problems: missing data, class imbalance, scarce real theft labels, and privacy. Supervised methods degrade on attack types they have not seen; unsupervised methods can be slower or weaker on some attack types; hybrid approaches are reported as more promising.
- Recent proposals include autoencoder-based unsupervised detectors and TRANS-DEEP (PeerJ Computer Science, 2026), a deep pipeline built around a variational autoencoder, BiLSTM, and Transformer components that reports 94.66%, 96.34%, and 95.12% accuracy on three smart-meter datasets. Those numbers do not transfer to this system.
- Conformal prediction can calibrate a score threshold to a target false-alarm rate under exchangeability, which time series break. Recent work addresses this: an ICLR 2026 paper (IBM Research) uses adaptive, weighted conformal bounds with time-series foundation models to keep false-alarm control under distribution shift, and a 2026 paper at the Symposium on Conformal and Probabilistic Prediction (PMLR 329) notes that evaluation often suffers leakage from flawed thresholding and proposes conformal thresholds that avoid it.
Sources read on 2026-10-30: the TRANS-DEEP paper page, the ICLR 2026 paper page, and the PMLR 329 paper page; the review statements come from abstracts only.

## 3. Method catalog
| Method | Idea | Needs | Notes | MVP |
|---|---|---|---|---|
| Robust seasonal baseline | Expected value per hour and day type from past weeks; score z = (x - median) / (1.4826 x MAD) | A few weeks of history | Robust to outliers; explainable | Yes |
| CUSUM change detection | S_t = max(0, S_(t-1) + (x_t - mu - k)); alarm when S_t > h | A baseline mean | Catches sustained shifts such as a night-floor drop; PELT is an offline alternative | Yes |
| Isolation Forest | Isolates outliers by random partitioning on engineered features | Features | Point anomalies; unsupervised | Yes |
| Autoencoder (dense, CNN-LSTM, or VAE) | Reconstruction error over a window | Training on normal data | Pattern anomalies; choose one the team can explain | Yes (one) |
| Conformal calibration | Threshold = the (1 - alpha) quantile of scores on a nominal calibration window | Calibration data | Target false-alarm rate, not a guarantee | Recommended |
| Score fusion | Rank-average or max of calibrated scores, then tiers and persistence | Calibrated scores | Reduces single-model blind spots | Recommended |
| Seasonal-trend decomposition | Flag outliers in the residual after removing trend and seasonality | History | Simple, explainable | Optional |
| Matrix-profile discord search | Finds the most unusual subsequences without training | A library (Unknown) | Good for unusual shapes | Optional |
| Forecast intervals | Alert when actual falls outside a quantile prediction interval | A forecaster | A pretrained foundation model needs weights and may need a network (Unknown) | Optional |
| Supervised classifiers | Gradient boosting, deep nets, Transformers | Enough reviewed labels | Only after reviewed labels exist | Later |
| Federated learning | Train across sites without sharing raw data | Several sites | Out of scope in local mode | No |
| Appliance disaggregation | Estimate per-appliance load from the whole-home meter | Research-grade models | The Breakdown uses declared appliances; never claim disaggregation | No |

## 4. Build path (complexity ladder)
L1 robust baseline plus rule signatures (CUSUM); L2 Isolation Forest; L3 one autoencoder; L4 conformal calibration plus score fusion; L5 optional extras. Move up only after the previous level passes its tests and benchmark, and record each level's results.

## 5. Calibration and thresholds
- Choose a nonconformity score s (for example the fused anomaly score). On a calibration window of nominal data, set the threshold q to the ceil((n + 1)(1 - alpha)) / n quantile of the scores.
- Convert the rate: 96 intervals a day, so alpha = 0.001 means about 96 x 0.001 = 0.096 false alarms a day, or roughly one every 10.4 days, under exchangeability.
- Time series are autocorrelated and seasonal, so calibrate per hour-of-week bucket, recalibrate on a rolling window, and check the empirical false-alarm rate on a held-out nominal period. Treat alpha as a target.
- Keep flagged periods out of the calibration window. Persistence and cooldown reduce customer-facing alerts further.

## 6. Optimization and tuning
- Objective: maximize recall (or PR-AUC) at a capped false-alert rate per meter-week, or minimize expected cost c_fp x FP + c_fn x FN with documented costs (real costs are Unknown; label illustrative ones).
- Search: grid or random for a few settings; Bayesian optimization such as a tree-structured Parzen estimator when there are more than four (Likely; library Unknown). Use rolling-origin cross-validation, never random splits; nest the search so the test period stays unseen; fix seeds; report variance across seeds; stop when gains fall below noise.
- Computation: score in vectorized batches off the request path; compute features once and cache them; update rolling statistics incrementally (Welford's online mean and variance; a sorted window for rolling medians) (Likely); measure first (build.md section 11).

## 7. Explainability
- Store reason codes and the top contributing features per alert, using robust z-scores per feature.
- For Isolation Forest, per-feature attribution such as TreeSHAP can explain tree ensembles (Likely; verify with the chosen library). For autoencoders, show which intervals carry the reconstruction error.
- Turn attributions into plain sentences using fact-sheet numbers only, with counterfactual wording ("a usual evening is about X kWh") computed from the baseline.
- Use "could be" and "likely"; name appliances only through the declared-appliance rule (appliances-and-mysql.md section 5).

## 8. Evaluation
Rolling-origin splits; precision, recall, PR-AUC, false alerts per meter-week, and mean time to alert; injected anomalies with realistic magnitudes and durations, including stealthy low-magnitude ones; an ablation against the baseline; stress cases (missing data, vacations, a new meter with no history, drift); bootstrap confidence intervals over days and meters (Likely). Label every result synthetic.

## 9. Provenance and no fabricated alerts
- Every alert stores detector name and version, settings version, feature values, score, threshold, window, and data coverage.
- Only the pipeline creates alerts. Sample alerts in the prototype are labeled sample; demo alerts come from running the detector on the synthetic series.
- A test fails if an alert exists without provenance.
- When nothing is detected, the app says "No unusual activity detected".

## 10. Status labels
Verified: the literature points in section 2 and the exchangeability caveat. Likely: TreeSHAP for Isolation Forest, matrix profiles, Welford updates, Bayesian optimization libraries, bootstrap intervals. Unknown: library choices and available compute.
