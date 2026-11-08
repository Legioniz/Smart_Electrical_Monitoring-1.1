# LLM layer: local model, grounded generation, validation, and safety

Contents: 1 Scope and sources; 2 Role and boundaries; 3 Local runtime and model; 4 Grounded generation pipeline; 5 Prompting and structured output; 6 Validation, fallback, and switches; 7 Safety (OWASP LLM Top 10); 8 Languages; 9 Performance and operations; 10 Evaluation; 11 Tests; 12 Optional features; 13 Unknown

## 1. Scope and sources
Requirement (Brief v10, change C12): add a large language model that phrases insights. Local mode applies: the model runs on the team's machine; there is no hosted API and no cloud-model variant. The app must work fully with the LLM off.
Verified (checked 2026-10-30):
- OWASP Top 10 for LLM Applications, 2025 edition: prompt injection; sensitive information disclosure; supply chain; data and model poisoning; improper output handling; excessive agency; system prompt leakage; vector and embedding weaknesses; misinformation; unbounded consumption. Guidance: treat model output as untrusted input everywhere; keep no secrets in a system prompt; bound the cost and tokens of every LLM feature.
- Ollama serves a local API (default http://localhost:11434). Self-hosted Ollama 0.5.0 or later enforces JSON-schema output through llama.cpp's grammar-constrained decoding (Pydantic AI documentation). Ollama Cloud accepts the schema but does not enforce it and is a hosted service; a base URL on ollama.com or a model name ending in -cloud signals it, and neither is allowed in local mode. Some other runtimes treat json_schema as advisory only, so always validate the output yourself.
Likely: Ollama is open source under the MIT license and wraps llama.cpp (secondary sources); other local runtimes exist and open-weight model families such as Llama, Qwen, Gemma, and Mistral run on them; fixed seeds give repeatable output on some runtimes. Unknown: the runtime and model choice, hardware, Filipino quality, licenses.

## 2. Role and boundaries
- The LLM only phrases. It computes nothing, decides nothing, scores nothing, and has no tools, no database access, no file access, and no network.
- Input is the fact sheet only (computed, versioned, aggregated). Never free text from customers (appliance names, notes), identifiers, or raw intervals.
- Uses: energy story narration; alert explanation sentences. Never theft leads, detection, scoring, or admin lead summaries.
- Output is untrusted until the validator passes it; unvalidated text is never shown.

## 3. Local runtime and model
- Run the runtime bound to loopback only (127.0.0.1), as a non-admin user, with no inbound firewall rule; confirm with a port check. Refuse any model name ending in -cloud, any base URL on ollama.com, and any other remote endpoint.
- Pick a small instruction-tuned open-weight model by: license allows the use; fits the machine's memory; supports structured output; handles the needed languages; meets the latency target (Unknown). Pin the exact model name and file hash and the runtime version; record them with every output.
- Check the hackathon rules on installing software and downloading models; download before the event and verify checksums from the publisher (Likely).
- No fine-tuning on customer data in the MVP; use stock models.

## 4. Grounded generation pipeline
1. Build the fact sheet from stored readings (model-spec.md sections 5 and 12).
2. Fill the fixed prompt template with the fact sheet; no other inputs.
3. Call the local model with a JSON-schema output: a list of sentences, each with its text and the fact fields it used.
4. Validate (section 6). Pass: store the narrative with provenance. Fail: retry once with stricter settings, then use the template. Never show failed text.
5. Cache by period, fact-sheet hash, model, and prompt version; generate once per period in the background, not on page load.
Settings: low temperature (Likely 0 to 0.2) and a fixed seed where supported; record them.

## 5. Prompting and structured output
- The system prompt holds rules only and no secrets; it is not confidential (Verified guidance).
- Rules: use only the provided facts; say "not available" for null fields; introduce no new numbers; no advice beyond energy use; no medical, legal, or financial claims; plain language; the named language; one to three sentences.
- The fact sheet is data, not instructions; delimit it clearly.
- Few-shot examples are fixed and reviewed and use placeholder numbers.
- The prompt template has a version; changing it triggers the evaluation set.

## 6. Validation, fallback, and switches
Validator (all must pass): schema valid; every number in the text appears in the fact sheet after the documented transformations (model-spec.md section 6); each sentence's cited fields exist and hold the numbers it states; no forbidden terms (theft, accusation words); length cap; language matches; no names or identifiers; advice only from approved constants.
- Fallback: the deterministic template built from the same fact sheet. The customer sees no error.
- Switches: an LLM-off setting; a circuit breaker that turns the LLM off for a cool-down after repeated failures or timeouts (tunable); timeouts; a maximum token count; one request at a time; a per-customer regeneration limit.
- Track validator pass rate and fallback rate.

## 7. Safety (OWASP LLM Top 10, 2025)
| Risk | Control |
|---|---|
| LLM01 Prompt injection | Only the fact sheet enters prompts; no customer free text; fixed category labels; the validator checks the output |
| LLM02 Sensitive information disclosure | Aggregated facts only; no identifiers; logs hold IDs and hashes, not prompts or outputs with personal data |
| LLM03 Supply chain | Pinned model and runtime, verified checksums, license check, downloads before the event |
| LLM04 Data and model poisoning | Stock models only; no training on customer data |
| LLM05 Improper output handling | Output is schema-validated, escaped when rendered, never executed, never placed in queries or commands |
| LLM06 Excessive agency | No tools, function calling, database, file, or network access; no actions |
| LLM07 System prompt leakage | No secrets in prompts |
| LLM08 Vector and embedding weaknesses | No retrieval or embeddings in the MVP |
| LLM09 Misinformation | Grounding, validator, and "estimated" wording |
| LLM10 Unbounded consumption | Token caps, timeouts, one request at a time, caching, per-customer limits, queue depth; abnormal request volume feeds the auto-lock triggers |

## 8. Languages
English first. Filipino text stays on templates until a fluent speaker has reviewed a fixed evaluation set; only then may the model phrase it, with the language-specific number and time transformations documented. Until then the screen shows "Filipino (planned)".

## 9. Performance and operations
Measure first (build.md section 11): time to first token, tokens per second, time per narrative, memory; the latency budget is Unknown. Pre-generate narratives for the demo data, warm the model before the demo, show the last validated narrative while a new one generates, and keep the LLM-off path ready. Provenance per narrative: model name and hash, runtime and prompt versions, settings, fact-sheet ID, validator result, latency.

## 10. Evaluation
A fixed set of fact sheets: typical, nulls, low coverage, over-declared appliances, no anomaly, WATCH alert, cold start. Measure validator pass rate, number faithfulness, unsupported-claim rate (human review of a sample), forbidden-term rate (must be 0), fallback rate, readability, and latency. Compare with the template; keep the LLM only if it meets the faithfulness bar the team sets (Unknown) and reviewers prefer it. Rerun after any model or prompt change. Label results synthetic.

## 11. Tests
| Area | Cases |
|---|---|
| Unit | A fake local model returns valid text, invalid schema, an extra number, a forbidden term, and an over-length text; the validator and fallback handle each; no network is used |
| Evaluation | The fixed set runs and results are reported |
| Injection | Injection-like text in appliance names and notes never reaches a prompt; the output does not change |
| Output handling | Model text is escaped when rendered and never reaches a query or command |
| Switches | LLM-off setting, circuit breaker, timeout, and token cap each give template text with no error |
| Caching | The same inputs reuse the cached narrative; a changed fact sheet, model, or prompt regenerates it |
| Provenance | Every stored narrative has the full provenance record |
| Local-only | The runtime listens on loopback only; the app makes no outbound calls |
| Languages | Filipino uses templates until review; English passes the validator |

## 12. Optional features
"Ask about my usage": the model only chooses a question type from a closed list (for example this week versus last week, biggest appliance, why last evening was high). The app runs the matching allow-listed, read-only function for the signed-in customer, and the model phrases the computed result under the same validator. No free-form SQL, no model-run tools. Fine-tuning and retrieval stay out of scope.

## 13. Unknown
Runtime and model; hardware and latency target; Filipino quality; licenses; whether the rules allow downloading models; seed determinism on the chosen runtime; the faithfulness bar.
