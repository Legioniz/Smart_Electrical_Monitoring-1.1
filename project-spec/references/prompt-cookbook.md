# Prompt cookbook: building and changing the project with short prompts

Contents: 1 How it works; 2 Keywords; 3 Templates; 4 Examples; 5 One-shot full build; 6 Tips; 7 What Claude does with vague prompts

## 1. How it works
Start a message with a keyword, then say what you want in plain words. Everything else is optional. Claude fills gaps with listed assumptions and proceeds, asks at most one question when the answer would change the direction, and always applies the coding gate first.
These keywords are conventions of this skill, not platform commands.

## 2. Keywords
| Keyword | Meaning | Output |
|---|---|---|
| BRIEF | Show, create, or update the project Brief | The Brief table |
| PLAN | Plan a piece of work | Short plan, assumptions, tests, risks |
| BUILD | Build a module, page, or slice | Changed files, tests run, results (coding mode only for code) |
| CHANGE | Modify something already decided | Class C1 to C4, impact, changes made |
| PIVOT | Change what the project is | Pivot mode steps |
| STATUS | Where are we | Status block |
| REVIEW | Check my work or output | Findings table |
| TEST | Plan or run tests | Cases, or real results |
| DEPLOY | Prepare or troubleshoot deployment | Checklist, steps, smoke test |
| DEMO | Rehearse or script the demo | Script or quiz |
| UNDO | Reverse a change | Files touched, restored state |
| EXPLAIN | Teach me this part | Plain explanation with a worked example |
| READY | Run the foolproof checks | Go or no-go table, failed items, next fixes |

## 3. Templates (copy, delete what you do not need)
- BRIEF: [paste Brief or say "use baseline"]
- PLAN: [goal]. Done when: [condition]. Keep: [what must not change].
- BUILD: [slice, for example S9 features]. Done when: [condition]. Keep: [constraints]. Coding is allowed.
- CHANGE: [what to change and why]. Keep: [what must stay].
- PIVOT: The project is now [description]. Reuse: [what to keep, or "decide for me"].
- STATUS
- REVIEW: [paste code, text, or screen description]. Focus: [security, claims, units, design].
- TEST: [what to test]. Share real output if you ran it.
- DEPLOY: Target: [local or cloud]. Problem: [paste the error or log lines].
- DEMO: Time: [minutes]. Audience: [judges]. Quiz me or write the script.
- UNDO: [change ID or description]
- EXPLAIN: [function, module, or concept]. My level: [beginner or intermediate].
- READY: [before coding, before submission, or demo day]. Evidence I have: [test output, rehearsal notes, organizer replies].

## 4. Examples
- CHANGE: raise the persistence rule to 4 consecutive evenings before WATCH. Keep: the cooldown. Done when: the tier tests pass.
- CHANGE: make the narrative template-only for now. Keep: the validator.
- CHANGE: add a rule that flags a night-floor drop of more than half versus the 28-day median. Done when: a constructed series fires it.
- BUILD: synthetic generator first, with injected anomalies and labels. Done when: the same seed gives identical data. Coding is allowed.
- BUILD: fact sheet and validator. Done when: the documented accept and reject cases pass.
- REVIEW: [paste narrative text]. Focus: numbers not in the fact sheet.
- PIVOT: the project is now a school-campus energy dashboard. Reuse: whatever fits.
- DEPLOY: Target: local. Problem: the API container exits at start. [paste log lines]
- DEMO: Time: 5 minutes. Quiz me on the judge questions.
- CHANGE: shorten the landing page headline. Keep: the sample disclaimer.
- CHANGE: show the app on a phone over the hotspot. Expect a question: this leaves local-only mode and needs TLS or an isolated network and your approval.
- CHANGE: move to the block level after 10 invalid requests a minute from one source. Keep: team devices allow-listed.
- CHANGE: make the admin session expire after 10 idle minutes. Keep: the second step.
- REVIEW: [paste sign-in code]. Focus: sessions, lockout, and password storage.
- REVIEW: consent submission returns a CSRF error. Fix the root cause without weakening the check.
- BUILD: S12 local LLM. Done when: the evaluation set passes and the LLM-off path works. Coding is allowed.
- BUILD: S8 appliances. Done when: add, edit, and delete work with validation and the Breakdown changes. Coding is allowed.
- CHANGE: add a water heater category. Keep: the estimate method.
- REVIEW: [paste API code]. Focus: SQL injection and rate limiting.
- BUILD: S7 from the prototype. Done when: the landing route and screens match prototype.md and work at 360, 768, 1280 px. Coding is allowed.
- READY: before submission. I ran the full suite and rehearsed once.
- STATUS

## 5. One-shot full build
Prompt: BUILD FULL from Brief v1. Coding is allowed. Priorities: required items first, then responsive polish, then deployment.
Claude then works in slices following the phase gates: after each slice it reports what changed, tests run with real results, remaining issues, and the next slice. Reply NEXT to continue, or CHANGE to redirect. Claude never claims the whole project is done until every acceptance item is marked Met with evidence. A single reply cannot hold a whole project, so expect several slices.
If coding is not confirmed, BUILD returns the plan and specs instead, and says so.

## 6. Tips for better results
- Say what "done" looks like in one line.
- Say what must not change (Keep).
- Paste the latest Brief at the start of a new chat.
- Paste real error text or test output instead of describing it.
- Say what you already tried.
- Change one thing at a time when debugging.
- Tell Claude when the hackathon rules or schedule change, so it can adjust.

## 7. What Claude does with vague prompts
It restates the request in one line, lists assumptions with defaults in a small table, proceeds, and asks at most one question if the direction truly depends on it. You correct by exception ("assumption 2 is wrong, use X").
Claude will decline to add unsupported claims, skip the coding gate, use real personal data without authorization, or call untested work finished. In each case it says why in one sentence and offers the closest allowed option.
