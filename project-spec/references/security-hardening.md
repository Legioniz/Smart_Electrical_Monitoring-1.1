# Security hardening: connection security, firewall, filters, auto-lock

Contents: 1 Scope and honesty; 2 Layered model; 3 What the app can and cannot do; 4 Connection security; 5 Firewall and exposure; 6 DNS attacks; 7 Bots and abuse; 8 SQL injection; 9 Other input and data attacks; 10 Auto-lock (safe mode); 11 Tamper detection; 12 Logging, alerts, and runbook; 13 MVP scope and labels; 14 Security tests; 15 Claims wording; 16 Local-only mode rules; 17 Access control design; 18 Request integrity

Requirement from the user (Brief v4, change C5): connection security, a firewall, and filters for DNS attacks, bots, and SQL attacks; the program locks itself on unusual activity or manipulation. This guide is defensive and for the team's own app only. It is planning until the coding gate is confirmed.
Source labels: Verified (checked 2026-10-27) means read in OWASP guidance, an Australian Signals Directorate DNS security publication, or similar; Likely means common practice not re-checked here; Unknown means it needs research for the chosen host. No system is unhackable: claim layered defenses, not immunity.

## 1. Scope and honesty
The project holds personal consumption data and theft leads, so it is a realistic target. Security is built early: bound queries and validation start in S1 and S2, and request integrity, authorization, rate limits, lock, and tamper checks are built and tested in S5, before any feature work (build.md). Never sacrifice security to make a feature work.

## 2. Layered model
| Layer | Controls | Owner | MVP status |
|---|---|---|---|
| Domain and DNS | Registrar account protection; DNSSEC; managed DNS with DDoS protection | Provider | Not applicable in local mode |
| Edge | CDN, web application firewall, bot management, DDoS protection | Provider | Not applicable in local mode |
| Network firewall | Default deny; only needed ports; database and ML service private | Host or cloud or OS | Built for the demo machine (OS firewall on) |
| Transport | HTTPS everywhere the app is exposed; HSTS; modern TLS | Host plus app settings | Built if exposed beyond the local machine |
| App gateway | Rate limits, size limits, headers, restricted cross-origin access, host check | App | Built |
| Authentication and authorization | Login portal for users and admins (login-portal.md); keys for meter ingestion; roles | App | Built |
| Input validation | Allow-lists, types, ranges, lengths | App | Built |
| Data layer | Bound queries, least-privilege database user, no error leaks | App and database | Built |
| Application logic | Auto-lock, protected settings, integrity checks | App | Built |
| Monitoring and recovery | Security logs, alerts, backups, tested unlock | App and team | Built (basic) |

## 3. What the app can and cannot do
| Request | Reality | Do this |
|---|---|---|
| Firewall | A network firewall is host, cloud, or OS configuration. The app can add request filtering: allow and deny rules, limits, validation | Turn the OS firewall on; expose only needed ports; keep the database private; filter requests in the app |
| Filter DNS attacks | DNS spoofing, amplification, and flooding happen in DNS infrastructure outside the app (Verified). Mitigations are DNSSEC with validating resolvers, careful resolver settings, and DNS DDoS protection from a provider | Label as provider-level and planned; use HTTPS with a valid certificate so a spoofed address cannot impersonate the site; keep the API address in configuration; validate the Host header against an allow-list (Likely); never use DNS names as proof of identity |
| Filter bots | No filter is perfect; user-agent text is unreliable | Rate limits per source and per key; request limits; provider bot management if hosted; challenges only on sensitive customer actions; honeypot fields (Likely) |
| Filter SQL attacks | Bound parameters are the primary defense; allow-list validation and least privilege are additional; escaping alone is discouraged (Verified, OWASP) | Section 8; a WAF is only a backstop |
| Lock itself on unusual activity or manipulation | The app can enter a safe mode from its own signals; it cannot detect every manipulation, and browser-side code is not trustworthy | Sections 10 and 11; server-side checks only |

## 4. Connection security
- HTTPS only for every endpoint that leaves the local machine; redirect plain HTTP; secure REST services should offer only HTTPS (Verified, OWASP REST guidance).
- HSTS, current TLS versions, and provider-managed certificates (Likely); check the host's defaults (Unknown until a host is chosen).
- Security headers: content security policy, frame protection, content-type sniffing off, referrer policy (Likely).
- Cross-origin access restricted to the portal's own origin; no wildcard.
- Cookies, if used: secure, HttpOnly, and SameSite settings (Likely); state-changing customer actions protected against cross-site request forgery (Likely).
- Internal calls (API to database, ML service, local LLM runtime) stay on a private network or use TLS; an online database (out of scope in local mode) must require TLS.
- Secrets in environment variables or a secret manager; never in source.
- Local demo on one machine: localhost connections are acceptable and labeled; if the app is reachable on a LAN or hotspot, use TLS or an isolated network.

## 5. Firewall and exposure
- Default deny. Open only the portal and API ports. The database, ML service, and admin interface are not reachable from outside.
- Admin and internal endpoints: private interface or authentication plus an address allow-list.
- OS firewall enabled on every demo machine; keep a short table of ports, who may reach them, and why.
- Allow-list the team's demo devices for rate limits, but never for integrity checks or the safe-mode lock.
- Restrict outbound connections to what is needed (none are needed in local mode; the local LLM runtime must not reach the internet) (Likely).
- Hosted setups: cloud network rules, private database networking, and provider edge protection are Unknown until the host is chosen; research them then.

## 6. DNS attacks
- Not solvable inside the app (Verified). Protect the domain: registrar account with multi-factor sign-in and transfer lock (Likely); DNSSEC where the DNS provider supports it (Verified as a mitigation against spoofing and cache poisoning when resolvers validate); a managed DNS service with DDoS protection (Verified as an option).
- App-side: HTTPS, Host header allow-list, configuration instead of hard-coded names, and no trust in DNS for authentication.
- A purely local demo has no public DNS surface; say so instead of claiming protection.

## 7. Bots and abuse
- Rate limit by source, session, and API key at the gateway or in the app; return a clear throttle response (HTTP 429) (Verified, OWASP REST guidance: rate limits can sit at an API gateway or WAF).
- Request size, time, and pagination limits; strict content types; reject unknown fields.
- Meter ingestion requires a per-meter key or signature; reject replays using timestamp checks (Likely).
- Slow down before blocking; block for a short, expiring period.
- Challenge (CAPTCHA or similar) only on human-facing sensitive actions such as feedback, and only if needed.
- Watch request patterns; alert on spikes.

## 8. SQL injection
1. Every value goes through bound parameters (parameterized queries). This is the primary defense (Verified, OWASP).
2. Never build SQL by joining text. Identifiers that cannot be bound (sort column, table name) come only from a fixed allow-list.
3. The runtime database user has least privilege: no schema changes, no dropping tables; migrations use a separate privileged role (Verified, OWASP lists least privilege as an additional defense).
4. Allow-list validation of types, ranges, lengths, and formats before the data layer.
5. Database errors never appear in responses; log them privately.
6. Stored routines must not build dynamic SQL from inputs.
7. Escaping alone is discouraged (Verified, OWASP); a WAF is a backstop, not the defense.
8. Detecting injection-like input is a signal for rate limiting and the lock, not a substitute for bound queries.

## 9. Other input and data attacks relevant here
- Fake or replayed meter readings: authenticate meters, check plausibility, quarantine suspicious batches.
- Poisoning through feedback: customer feedback adjusts customer alerts only; theft-lead criteria stay fixed.
- Prompt injection and unsafe model output: see llm.md section 7.
- Cross-site scripting: escape all output; treat model text as untrusted.
- Dependencies: pinned versions, a lockfile, and an update and vulnerability check before submission (Likely).
- No file uploads in the MVP; if added, validate type and size and store outside the web root.

## 10. Auto-lock (safe mode)
Design principle: graduated, time-bound, explainable, reversible. Account lockout can itself be abused as a denial-of-service tool, so current guidance favors throttling and temporary lockouts that expire over hard permanent locks, combined with rate limiting (Verified, OWASP authentication guidance as summarized by secondary sources).
| Level | Name | Effect | Exit |
|---|---|---|---|
| L0 | Normal | Everything on | n/a |
| L1 | Throttle | Slow or throttle the source; 429 responses | Automatic after quiet period |
| L2 | Temporary block | Block the source for a short expiring period; challenge on sensitive actions | Automatic expiry |
| L3 | Function lock | Lock the affected function (internal endpoint, feedback, ingestion source) for a cool-down; alert the team | Expiry or administrator unlock |
| L4 | Safe mode | App is read-only: ingestion writes and customer actions off, internal lead views locked; customers see existing data with a neutral "Temporarily paused for safety" message | Authenticated administrator unlock only; survives restart |
Triggers (all thresholds are tunable settings; start conservative and tune in rehearsal): repeated failed authentication; request-rate spikes; many invalid or malformed requests from one source; injection-like patterns in inputs; attempts to reach admin or internal paths; replayed or unsigned readings; large numbers of implausible readings; unexpected database error volume; integrity check failure (L4); change to a protected setting without authorization (L3 or L4); audit-log gap (L4).
Safeguards against abusing the lock:
- Count per source for L1 to L3; use global L4 only for integrity, tamper, or confirmed severe events.
- One event never locks anything; use counts over a window.
- Allow-listed team devices skip L1 to L3 but never skip integrity or L4.
- Show neutral messages; never reveal thresholds or reasons to the outside.
- Record reason codes and times in the audit log; alert the team on L3 and above.
- Unlock requires an authenticated admin (second factor, or two people) and writes an audit entry; after unlock keep a short elevated-watch period.
- Lock state is stored and survives restarts. If the lock logic cannot decide, fail closed for writes and internal views and keep customer read-only views where safe.
- A demo mode may raise thresholds only for allow-listed devices, must show a visible banner, and must never switch protections off.
- Never take an irreversible action against a customer automatically.

## 11. Tamper detection
"Manipulating the program" covers several things; the app can check some of them.
| Target | Check | Limit |
|---|---|---|
| Code and configuration on the server | At start and periodically compare file and settings hashes with a known-good manifest (Likely); run as a non-privileged user; read-only deployment where possible | An attacker with full control can disable checks, so send alerts and logs off the machine |
| Protected settings (thresholds, theft-lead criteria, lock settings) | Changes only by an authenticated admin, with an audit entry and an alert | Needs an access-control design |
| Data | Database permissions; detect unexpected updates or deletes of readings; tamper-evident audit log such as a hash chain (Likely) | Does not stop a database administrator |
| Model files | Record version and hash; verify at load | Same limit as code |
| Dependencies | Pinned versions, lockfile, trusted sources | Supply-chain risk remains |
| Browser code | Not trusted; the server validates everything | Cannot be prevented, only ignored |
Result of a failed check: log, alert, and L4 safe mode. Never claim the program is tamper-proof.

## 12. Logging, alerts, and runbook
- Log security events with reason codes, UTC time, and the source; no personal data and no secrets.
- Alert the team (email or webhook) on L3 and above.
- Incident runbook: identify; contain by entering safe mode; preserve logs; rotate secrets; restore the tagged known-good version; review; unlock; write a short retrospective. Practice it once before the demo.

## 13. MVP scope and labels
MVP status is in the last column of section 2. Bound queries and validation start in S1 and S2; request integrity, authorization, rate limits, headers, auto-lock, integrity checks, and the audit log are built in S5 (build.md). Controls that do not apply locally are labeled "Not applicable locally; provider-level if hosting is chosen later"; signed releases, centralized logging, and multi-factor admin are labeled "Planned".

## 14. Security tests (own app only; never test systems you do not own or have permission to test)
| Area | Test | Expected |
|---|---|---|
| SQL | Submit hostile-looking text in every input and parameter (quote characters, comment markers, always-true conditions, multiple statements) | Treated as plain data or rejected; no data change; no error text in the response |
| Database rights | Try a schema change with the runtime user | Refused |
| Rate limit | Exceed the limit from one source | Throttle response; recovers after the window; other users unaffected |
| Auto-lock | Send synthetic abusive traffic from a test device through L1 to L4 | Escalates as designed; administrator unlock works; restart keeps the lock |
| Lock abuse | One source tries to lock out others | Only that source is affected |
| Tamper | Change a protected setting or a file on a test copy | Alarm, audit entry, safe mode |
| Transport | Request over plain HTTP where exposed | Redirected or refused; headers present |
| Cross-origin | Request from a disallowed origin | Rejected |
| Meter ingestion | Unsigned, replayed, and implausible readings | Rejected or quarantined |
| Errors | Trigger errors | No stack traces, paths, or database messages |
| Bots | Scripted rapid requests from one source | Throttled; a normal user is unaffected |
| Logging | Review logs after the tests | Events recorded without personal data |
Report results with the date and what was not tested. Never claim a penetration test.

## 15. Claims wording
Use the approved wording in honesty-and-docs.md section 2 (secure, DNS, bots, SQL injection, tamper).

## 16. Local-only mode rules (decision 15)
- Listen on localhost only by default; never bind to all network interfaces. Any exposure beyond the machine (LAN, hotspot, second device, phone) needs the user's explicit approval, TLS or an isolated network, and a decision-log entry.
- The database is local MySQL: bind it to localhost or use the local socket only, check the installed package's default binding, add no inbound firewall rule for its port, and use the least-privilege runtime user (appliances-and-mysql.md section 9).
- OS firewall on, with no inbound rules for the app beyond localhost; limit unexpected outbound connections where practical (Likely).
- No internet needed at run time: no hosted LLM, no external APIs, no CDN assets or web fonts; keep local copies. Download dependencies before the event only if the rules allow.
- DNS, edge, and hosting protections do not apply to a local app; say "not applicable in local mode" and do not claim them.
- Backups: copy the tagged version and the exported demo database to a second device and a USB drive; each copy must run locally with no internet.
- Check phone-width layouts by resizing a browser window on the same machine, not by putting a phone on the network.
- Rate limits, validation, bound queries, auto-lock, and tamper checks stay on even though the app is local, because other software on the machine and shared venue networks still matter (Likely).

## 17. Access control design (local mode)
Roles, sign-in, sessions, admin protections, and authorization are specified once, in login-portal.md. This guide supplies the auto-lock (section 10) and the network and input defenses.

## 18. Request integrity: CSRF, Origin, Host, and request validation
Verified (OWASP CSRF Prevention Cheat Sheet and related guidance, checked 2026-10-30):
- The primary defense is an unpredictable token bound to the user's session and verified on every state-changing request that relies on cookies: a synchronizer token for stateful apps, or a signed double-submit cookie for stateless ones. A cookie-and-parameter pair that an attacker could set together is not enough.
- For API-driven pages, send the token in a custom request header and keep cross-origin access narrow.
- Origin validation and Fetch Metadata (Sec-Fetch-Site) are defense in depth; the cheat sheet's weighting of Fetch Metadata has changed over time, so read the current text. SameSite cookies are an additional control.
- Cross-site scripting can bypass CSRF defenses, so prevent it too. Never change state on GET or HEAD.
Design: cookie sessions with a per-session token, renewed at sign-in and sent in a custom header; Origin checked against an allow-list (Referer fallback when Origin is absent, Likely); Sec-Fetch-Site checked (Likely); SameSite Lax or Strict host-only cookies.
Host validation: allow-list the expected Host values (localhost, 127.0.0.1, and ::1 with the app's port, plus any deliberately configured name) and reject the rest with a clear error; never build links from the raw Host header (Likely).
Request validation on every state-changing route, consent included: allowed methods; allowed content types; a maximum body size; field allow-list with types, ranges, and lengths; unknown fields rejected; control characters rejected; one error format with a request ID.
Rule: never disable, loosen to a wildcard, or add a bypass for CSRF, Origin, Host, or validation checks to make a feature work. Find and fix the root cause. A test must fail if a production profile turns any of them off.
Diagnosis playbook for blocked requests (reproduce, log the reason code, compare headers and cookies, fix the cause, add a regression test):
| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| 403 on the first submit | Token not fetched, or the header name differs | Request headers against the session | Fetch the token from the session endpoint and send it in the agreed header |
| 403 only after waiting | Session expired or token rotated | Session timestamps | Redirect to sign-in and resume; renew the token on re-authentication |
| Works on localhost, fails on 127.0.0.1 | Host-only cookie or origin differs | Origin, Host, cookie scope | Use one canonical origin; allow others deliberately; keep cookies host-only |
| Origin check failed | Front-end dev server on another port, or a proxy rewriting headers | Origin against the allow-list | Add the exact dev origin for development only (no wildcard); fix proxy headers |
| Host not allowed | Opened by LAN name or IP | Host value | Stay local, or add the exact name after a security review (leaves local mode) |
| Cookie not stored | SameSite or Secure mismatch on plain HTTP, or cookies disabled | Browser cookie panel | Lax host-only cookies on localhost; Secure only over HTTPS |
| Token valid but 403 | Token tied to the old session ID after renewal | Compare session IDs | Renew the token with the session and refresh the client copy |
| Validation error | Stale form version, a field outside the allow-list | Response body | Reload the form; fix the field |
Tests: missing, invalid, and old tokens; wrong Origin; missing Origin per policy; wrong Sec-Fetch-Site; wrong Host; side effects on GET; oversized body; unknown field; wrong content type. Each gives the documented error and a log entry.
