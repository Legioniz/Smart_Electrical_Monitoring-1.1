# Adaptive intelligence and optional weather context

## Implemented in this build

- **Robust household baseline:** median and median absolute deviation (MAD), using adequately covered days only.
- **EWMA:** exponentially weighted smoothing of recent daily usage.
- **CUSUM:** one-sided accumulation of positive standardized deviations.
- **Candidate change-point scan:** chronological comparison of five preceding valid days against the following three valid days. It reports a candidate transition, not a confirmed cause.
- **Bayesian evidence estimate:** posterior under an explicitly stated illustrative 2% prior and a broad 3x-scale anomaly likelihood. This is not a calibrated real-world probability and must not be used as an enforcement or billing decision.
- **Evidence score:** a transparent weighted score from robust deviation, CUSUM, and an upward candidate change point. It is a prioritization score, not a validated probability.
- **Short-range forecast:** next-day median based on historical matching weekdays when at least three examples exist; otherwise a trailing-week median. The range is a robust empirical interval, not a calibrated confidence interval.
- **Existing ML support:** Isolation Forest and PCA-based daily profile reconstruction remain supplementary detectors. They do not replace deterministic rules or explainable evidence.

The API exposes this result as `intelligence` in `/api/customer/overview`. At least eight adequately covered days are required; insufficient history returns `cold_start` rather than fabricating a forecast.

## Optional location and weather workflow

1. On each authenticated customer app launch, the UI asks whether to use the device's current location for weather context.
2. The browser's Geolocation API is invoked only after the user selects **Use my location**. The user can choose **Not now**, deny permission, or let the request time out; none blocks the meter dashboard.
3. Coordinates remain in page memory and are sent directly from the browser to Open-Meteo over HTTPS. The app does not send them to its FastAPI backend or save them in local storage/database.
4. The app requests current weather and the previous seven days of hourly temperature, apparent temperature, humidity, precipitation, cloud cover, and wind context. The weather panel compares daily mean temperature with daily meter usage only when at least five matching days have adequate meter coverage.
5. Correlation is labeled exploratory and explicitly not causal. High temperature may be consistent with cooling demand, but does not prove an air-conditioner is present or explain an anomaly.

The browser controls the operating-system permission prompt. The app can display its own consent prompt every launch, but cannot force the browser to show its native permission dialog repeatedly after a prior grant. Geolocation requires a secure context; loopback localhost/127.0.0.1 is treated as secure by modern browsers. The `Permissions-Policy` allows geolocation for the same origin and CSP permits only the Open-Meteo API as the additional remote connection target.

Weather attribution: Open-Meteo (https://open-meteo.com/). Weather is an optional online enrichment; if offline, denied, unavailable, or timed out, all meter features continue without it.

## Deliberately not claimed as implemented

- A fully calibrated Bayesian online change-point detector is not implemented; the current chronological robust regime scan is a lightweight candidate detector.
- SARIMA/Prophet or a trained quantile-forecasting model is not implemented; the current weekday/rolling-median forecast is deliberately simple and auditable.
- NILM appliance disaggregation is not implemented. Fifteen-minute aggregate readings do not support reliable identification of many individual appliance signatures.
- Grid graph/GNN anomaly analysis is not implemented. It requires verified transformer/meter topology and synchronized feeder measurements.
- A budget optimizer is not activated because no user-confirmed tariff, monthly budget, or controllable-appliance schedule is configured. It would be misleading to invent electricity rates or guaranteed savings.
- Weather is not used to suppress or raise security/theft-related alerts. It is displayed as contextual evidence only until real weather-meter calibration and evaluation exist.

## Validation boundaries

Synthetic tests verify deterministic calculations and edge handling; they do not establish field accuracy. The browser geolocation flow and live Open-Meteo network request could not be exercised in the restricted browser environment. Target-device checks must verify permission UX, HTTPS/localhost behavior, network timeout/offline behavior, and the weather provider's current API availability before demo day.

## V2.13 deeper intelligence hardening

The deeper intelligence pass supersedes the original one-sided v1.0 description above:

- Intelligence engine version is now `sme-intelligence-v2.0`.
- Daily input is validated for finite/non-negative energy, valid ISO dates, coverage threshold, duplicate dates, and calendar gaps. Quality diagnostics are returned with the result.
- Robust baselines prefer the latest contiguous calendar window. A historical fallback is explicitly labeled when that window is too short.
- Change-point candidates require five preceding plus three following **calendar-contiguous** days, including continuity across the split. A missing date cannot be silently treated as consecutive.
- EWMA exposes a standardized shift. CUSUM is two-sided and resets at calendar gaps; when a candidate change point exists, the drift reference is taken from its pre-change window so the new regime does not immediately normalize itself.
- Forecasts expose an empirical absolute-error envelope and explicitly state that the interval is not probabilistically calibrated. Rolling-origin backtesting is required before relying on it operationally.
- Evidence aggregation exposes its component scores. It is direction-aware and remains a prioritization score, not a validated probability.
- Recommendations are tied to detected direction and data-quality limitations. A drop prompts checks for occupancy and data completeness rather than an automatic fault diagnosis.
- Weather comparison adds full-day hourly coverage checks and exploratory cooling-degree-day context using a 24 °C reference. It also validates coordinates and weather values, warns when reported GPS accuracy is coarser than 10 km, and keeps all coordinates in browser memory only.
- The weather/usage comparison remains unadjusted. Weekday, occupancy, tariff, and appliance changes can confound it; no causal inference is made.

### New regression coverage

Added tests for calendar-gap change-point isolation, sustained downward shifts, duplicate-date handling, non-finite readings, rank correlation, and the expanded output contract. The current backend suite reports 59 passing tests in this authoring environment.
