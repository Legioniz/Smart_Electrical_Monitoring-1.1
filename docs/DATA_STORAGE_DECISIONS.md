# Data storage and learning boundaries

## Appliances: database is the source of truth

Do not create one loose `.txt` file per appliance and use file deletion to remove it. That duplicates the database, creates stale copies, breaks concurrent updates, and makes restore/history unreliable. MySQL remains the canonical store for appliance records. `ApplianceVersion` preserves history; `AuditEvent` records create/update/retire/restore actions. The app's export endpoint can generate a human-readable export when requested, but the app does not read that export back as live state.

## Learning artifacts

The app's online detector uses computed meter features and optional scikit-learn models; energy stories and suggestions use deterministic templates unless a verified local Ollama model is explicitly enabled. The Ollama model manifest is hashed from disk and checked against the configured SHA-256 before inference. A separate `scripts/train_synthetic_baseline.py` command can train a review-only Isolation Forest using generated synthetic readings and save the artifact, checksum, and metrics under `var/learning/`. It never uses customer data and never edits source code. The live app does not automatically load newly trained artifacts. Human review and a measured acceptance test are required before a model is promoted.

## Self-improvement safety

Runtime self-modification of source files, security rules, permissions, migrations, launcher code, or dependencies is intentionally not allowed. The supported growth path is: collect approved synthetic/evaluation data, train an isolated model artifact, validate it, record its version/checksum, review the change, and deploy through a normal update. This preserves reproducibility and prevents model output from executing arbitrary code.
