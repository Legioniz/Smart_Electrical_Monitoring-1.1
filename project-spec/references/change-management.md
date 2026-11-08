# Change management: adapting the project to any instruction

Contents: 1 Principles; 2 Immutable core and flexible layer; 3 The Brief; 4 Baseline Brief v1; 5 Change classes; 6 Impact checklist; 7 Pivot mode; 8 Conflicting or unclear instructions; 9 Undo and versions; 10 Status block; 11 Changelog format

## 1. Principles
- The user owns the project. Their instruction is the specification. Adapt to it without asking permission for ordinary changes.
- Be flexible about WHAT is built (scope, design, stack, algorithm, deliverables) and strict about HOW it is built (the immutable core below).
- Make the smallest change that satisfies the instruction. Do not add features the user did not ask for; suggest up to three optional ideas instead.
- Keep everything consistent after a change: code, tests, data contracts, docs, banner text, claims, demo script.
- Record every change so it can be explained and undone.

## 2. Immutable core and flexible layer
The immutable core is defined once, in SKILL.md; do not restate it elsewhere. Everything else is the flexible layer and changes on the user's instruction: name, purpose, audience, features, screens, data model, models, thresholds, stack, storage, visual identity, devices, deployment, deliverables, test scope, schedule. If an instruction collides with the immutable core, decline only that part, do the rest, and offer the nearest allowed alternative. Domain rules (theft leads, facts before language) apply while the project involves them; after a pivot, keep the universal rules and re-derive the domain rules.

## 3. The Brief (single source of truth)
Skills cannot store files between chats, so the Brief travels with the user.
- At the start of every chat, look for a pasted Brief. If none, use Baseline Brief v1 (section 4) and say so in one line. Never claim to remember earlier chats that are not in the conversation.
- The Brief holds: name; purpose; users and judges; core feature; scope IN and OUT; stack; data; design and device targets; acceptance criteria; deployment target; rules and gate status; open decisions; version and changelog.
- After each accepted change, show a short Brief delta. After a major change, show the full updated Brief and tell the user to save it (in coding mode as a file in the repo, for example under docs) and paste it into later chats.
- Where the Brief and the original proposal differ, the Brief wins.

## 4. Baseline Brief v1
The baseline is references/project-brief.md (derived from the uploaded proposal). Where an accepted change differs from the baseline, the change wins.

## 5. Change classes
| Class | Examples | Handling |
|---|---|---|
| C1 Tweak | Text, color, one parameter value, one field label | Do it now; one-line note |
| C2 Feature change | Add or modify a page, constraint, chart, data field, validation rule | Run the impact checklist silently; state assumptions; do it; list changed files; update tests and docs; run tests |
| C3 Major change | New objective or algorithm, new data model, stack swap, new deployment target, architecture change | Show a plan of at most 8 lines (impact, tests to rewrite, migration, rollback); proceed unless it is destructive or irreversible, in which case wait for "go"; bump the Brief version; rerun the whole suite |
| C4 Pivot | New purpose, domain, or audience | Use pivot mode (section 7) |
In allowed mode (coding unconfirmed) every class produces plans, specs, and updated documents only, never code.
Scale effort to the class. A color change does not need a plan, and a pivot should not be treated as a tweak.

## 6. Impact checklist
| If this changes | Also review |
|---|---|
| Purpose or scope | Brief, README, methodology page, banner, demo script, acceptance list |
| Features, models, thresholds, or tier rules | Model spec, detection code, explanations, tests with hand-calculated values, synthetic benchmark rerun, README |
| Fact sheet or narrative templates | Validator rules and cases, fallback templates, localization, claims check |
| Data fields or units | CSV contracts, validation, sample data, charts and axis units, persistence |
| Screens or navigation | Routes, responsive layout at 360, 768, 1280 px, README, demo script |
| Stack or dependencies | requirements, Python version, deployment, troubleshooting notes, tests |
| Visual identity | Banner, contrast, charts, responsive checks |
| Deployment target | Deploy guide, smoke test, runbook, privacy of the public link |
| Mode (local only or hosted) | Brief decisions 10, 12, 15; security-hardening.md sections 5, 6, 16; deployment.md; security-privacy.md section 10; foolproof drills; claims wording |
| Anything that affects numbers | Claims check, synthetic labels, kWh versus kW labels |
Report only the rows that apply. Do not list unrelated rows.

## 7. Pivot mode
1. Confirm in one line what the new project is. Ask one question only if the purpose is unclear.
2. Archive the old Brief (keep its version), and write Brief v1 for the new project using the same fields.
3. Re-check the gate. The hackathon rules might treat the new project differently; ask the user, and treat unknown as not allowed.
4. Keep the universal rules: immutable core, response protocol, source trust, command safety, delivery gates, responsive design, security and privacy checks.
5. List what carries over (reusable modules, tests, design tokens, docs structure) and what must be rebuilt.
6. Rewrite the model spec, data contracts, test plan, and claims list for the new domain before any code.
7. Tell the user that "this project is now X" is enough for the rest of the chat; the skill name is only a label.

## 8. Conflicting or unclear instructions
- The latest instruction wins. Say in one line what it supersedes ("Earlier: A. Now: B. Using B.").
- If two instructions cannot both be honored and the difference matters, show a two-row decision table and ask once.
- If an instruction is vague, state the assumptions in a short table with defaults and proceed; the user corrects by exception.
- If the user states a fact about the hackathon rules, use it as stated and note "per user".
- If the instruction asks for something outside the immutable core, follow section 2.

## 9. Undo and versions
After any major change (C3 or C4), rerun the affected go or no-go rows in foolproof.md.
- Keep Brief versions (v1, v2, ...) and changelog IDs (C1, C2, ...).
- "UNDO Cn" reverses that change: list the files and sections it touched, restore them, update the Brief, and rerun tests. In coding mode prefer git revert over rewriting history.
- If later changes depend on the one being undone, say so before reverting.

## 10. Status block (use on STATUS and after each phase)
| Item | Value |
|---|---|
| Brief version | vN |
| Mode | Allowed (no code) or Coding |
| Phase | Number and name |
| Done and verified | Items with evidence |
| Not done or not run | Items |
| Open decisions | Items |
| Risks | Top three |
| Next step | One action |

## 11. Changelog format
| ID | Date | User instruction (short) | Class | Files or sections touched | Tests run | Status |
