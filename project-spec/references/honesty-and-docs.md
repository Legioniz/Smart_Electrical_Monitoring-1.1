# Honesty, documentation, demo, and Git

Contents: 1 Claims guard; 2 Safe wordings; 3 README; 4 Demo script; 5 Judge Q&A; 6 Git habits; 7 Attribution

## 1. Claims guard
Before any submission also run the claims audit word search in foolproof.md section 5.
Never say or imply: that a method is state of the art or that a paper's accuracy applies to this system; that an alert or insight exists that the pipeline did not produce from stored readings; that results use real Meralco data; that Meralco endorses or partners with the project; that KPI targets were achieved; that precision or accuracy figures are real-world when they come from synthetic data; that the system detects theft (it flags leads for review); that the app complies with privacy law; that customers never see errors; that scale (12 million meters) was tested; that a feature works or tests pass unless it was run and the result seen.
Always: label simulated data and synthetic metrics; say "estimated" for appliance shares and "lead" for theft signals; list unmet acceptance items and missing deliverables.
Review output: table of Claim, Problem, Safer wording; if clean say "No overclaims found" and name what was checked.

## 2. Safe wordings
| Instead of | Say |
|---|---|
| "Detects electricity theft" | "Flags unusual patterns as leads for human review" |
| "99% accurate narratives" | "Narratives are validated against the fact sheet; measured on synthetic text" |
| "Works for 12 million meters" | "Designed to scale; not yet benchmarked" |
| "Compliant with the Data Privacy Act" | "Designed with its principles in mind; pending legal review" |
| "Customers never see an error" | "Falls back to template text if the LLM fails" |
| "Your aircon used 40% more" (from a total change) | "Your total usage rose about 40%; aircon is estimated at about 41% of it" |
| "Alerts are opt-in" | "Alerts are planned to be opt-in" |
| "Live customer portal" | "Design prototype with sample data" |
| "Secure" or "unhackable" | "Layered defenses designed in; not penetration-tested" |
| "Protected from DNS attacks" | "DNS protection is provider-level and planned; the demo runs locally" |
| "Blocks all bots" | "Rate limits and challenges reduce automated abuse" |
| "Immune to SQL injection" | "Uses bound queries and least-privilege access; tested on our own app with hostile-looking input" |
| "Locks itself against tampering" | "Enters a read-only safe mode on defined triggers; cannot detect every manipulation" |
| "AI explains your usage" | "A local model phrases numbers that were computed and checked first" |
| "Secure login" | "Sign-in with salted slow password hashes, sessions, and an admin second step; not penetration-tested" |

## 3. README
What it is and is not; the simulation disclaimer; requirements; install and launch commands that were actually run; how to run tests; structure; the model in brief; synthetic data notes; limitations; attributions; the decision log; a note that KPIs are targets.

## 4. Demo script (length unknown; ask the organizers, then scale)
1. Problem: bills arrive without explanation; losses are found late (30 s).
2. Explorer: the 15-minute chart on a phone-width screen (45 s).
3. Guardian: an injected anomaly gets flagged with a reason; tiers explained (60 s).
4. Storyteller: the fact sheet, the narrative, the validator rejecting a bad number, and the fallback with the LLM off (60 s).
5. Responsible use: theft signals stay internal; leads, not verdicts (30 s).
6. Limits: simulated data, synthetic metrics, what real deployment needs (30 s).
If the working app is not ready, walk through the design prototype (prototype.md) and say clearly that it is a static prototype.

## 5. Judge Q&A (the team must answer without notes)
Where does the data come from and what is simulated? How are anomalies found, and how do the two models differ? How do you limit false positives? How does the LLM avoid wrong numbers? What happens if the LLM is down? How is customer privacy protected, and what leaves the system? How are theft signals handled? What is measured versus targeted? How would it scale to many meters, and what is unproven? What do you need from Meralco? Why not just use thresholds? What would you build next?
Coaching: ask one question at a time, wait for the answer, then say what was correct, what was missing, and a tighter two-sentence version. Track weak areas and repeat them.

## 6. Git habits
No code commits before the rules allow coding; planning notes may be committed and labeled. Small commits, imperative messages (for example "Add night-floor signature check"). Never backdate or rewrite shared history to hide timing. Never commit secrets, real data, virtual environments, model caches, or large generated data. Tag the submitted version. Each member commits under their own identity.

## 7. Attribution
List libraries, datasets, docs, and any help received, with licenses. Do not copy others' code without a compatible license and credit.
