# Local learning workspace

The application may keep **versioned model artifacts, synthetic training data, evaluation metrics, and human-reviewed configuration proposals** under `var/learning/`. This workspace is local to this installation and is excluded from version control.

## Safety boundary

- The application does not rewrite its Python, JavaScript, SQL, migrations, launcher, or security policy at runtime.
- Model training is a separate, explicit maintenance action. New artifacts are checksummed and versioned; a human must review and promote them before the live detector uses them.
- The live detector may use the currently consented account's stored readings transiently to establish that account's baseline and compute scores. It does not export those readings into the offline learning workspace or pool them across customers. Offline artifacts produced by the included training script use generated synthetic data only.
- No credentials, session tokens, consent records, raw customer identifiers, or free-text personal information belong in training artifacts.
- The optional local LLM is Ollama on loopback only. Its output is treated as untrusted, validated against computed facts, and falls back to deterministic templates.

This design permits the analytics to improve without giving generated model output permission to execute code or alter access controls.
