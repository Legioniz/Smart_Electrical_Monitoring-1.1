# Login portal: user and admin sign-in

Contents: 1 Scope and sources; 2 Roles and layout; 3 Accounts and data; 4 Sign-in flows; 5 Credentials; 6 Sessions; 7 Admin protections; 8 Authorization; 9 Screens; 10 Tests; 11 Optional and Unknown

## 1. Scope and sources
Requirement (Brief v7, change C8): a login portal with a User sign-in and an Admin sign-in; everything except the landing page and the sign-in page needs a valid session of the right role. Local mode. Planning until the coding gate is confirmed.
Verified (OWASP Password Storage Cheat Sheet, checked 2026-10-28, and OWASP Developer Guide digital-identity checklist, checked 2026-10-30):
- Hash passwords with a strong, slow algorithm: Argon2id with at least 19 MiB of memory, 2 iterations, and 1 degree of parallelism; scrypt if Argon2id is unavailable; bcrypt (work factor 10 or more, 72-byte limit) for legacy systems; PBKDF2 with 600,000 or more iterations only when FIPS compliance is required. A unique salt per password. Fast hashes such as SHA-256 are unsuitable. Older OWASP versions listed lower minimums, so check the current sheet at build time.
- Use multi-factor authentication for sensitive accounts; re-authenticate before critical operations; either disable an account after repeated failures or add a random, tunable delay.
- Send credentials only in POST requests. Failure responses must not reveal which part was wrong or whether the account exists, including through response time. Close any pre-login session and create a new one after sign-in; generate a new session ID on any re-authentication and periodically; keep session IDs out of URLs, errors, and logs; enforce an idle timeout and an absolute lifetime; disallow persistent logins; set HttpOnly and Secure cookie attributes; require CSRF tokens on requests that change state; end all sessions when an account is disabled and offer to end other sessions after an authentication factor changes; let admins end any session and users end their own; reset questions are deprecated.
Likely (training material and secondary sources): idle timeouts of about 5 to 15 minutes for high-risk apps and 15 to 30 for typical ones with an absolute limit of a few hours; password length of 8 with a second factor and 15 without. Unknown: the hashing library and the second-factor method.

## 2. Roles and layout
- Roles: Customer (a user), Reviewer, and Administrator. The Admin tab signs in internal accounts of either internal role. In this skill a lone "admin" means an internal account of either role; "administrator" means that role only.
- One login portal page with two tabs, User and Admin, in the same design. The Admin tab adds a second-step field and a notice. Whether the admin entry stays on the same page or moves to a separate unlinked route is decision 18; hiding a route is not a control, so the second factor, throttling, and audit are the real protection.
- Unauthenticated visitors reach only the landing page, the sign-in page, and static files. Any other request redirects to sign-in with a neutral message.
- Admin accounts are not customers. A user cannot open admin screens; reviewers and administrators see no appliance names or notes by default (appliances-and-mysql.md section 7).
- At least two administrator accounts exist so the second-approver rule works, plus at least one reviewer. Internal accounts are created by a setup step, never through the portal.

## 3. Accounts and data (MySQL, in words)
- accounts: ID, role, username, password hash with algorithm and parameters, status (active, locked, disabled), must-change-password flag, created and last sign-in times, link to the customer for users.
- sessions: ID stored as a hash, account, role, created, last seen, expiry, source.
- sign-in events: time, account or attempted username, outcome, reason code, source. Never passwords.
- admin second-factor records: method and secret handled per the chosen method (Unknown).
Passwords never appear in logs, errors, URLs, or exports.

## 4. Sign-in flows
- User: username and password; on success close any earlier session, create a new one, show consent on first sign-in (before any analytics), then Overview. Failure shows one generic message ("Incorrect username or password") with similar response time whether or not the username exists (Verified).
- Admin: username and password, then a one-time code; on success a new session with stricter timeouts, then the review queue. Critical operations (unlock safe mode, change protected settings) re-authenticate and need a second approving administrator.
- Sign-out: delete the server session first, then clear the cookie, and show a confirmation on the sign-in page. An expired session shows "Please sign in again".
- Failures: throttle by account and source with increasing delay; apply a short, expiring lockout; never lock permanently. Count per account and source together so an attacker cannot lock out everyone (lockouts can be abused for denial of service). Repeated failures feed the auto-lock levels (security-hardening.md section 10); admin failures also alert the team.

## 5. Credentials
- Hash with Argon2id at the current OWASP minimum or stronger (Verified); the library is Unknown, so choose a maintained one that supports Argon2id and verify it. Never SHA-256 alone. Rehash at sign-in if parameters change.
- Policy: allow long passphrases; block very common passwords (Likely); length per the current OWASP text (Likely: 8 with a second factor, 15 without); no forced composition rules (Likely); no hints or security questions (Verified).
- Users can change their own password with the current password; a new admin must change the password at first sign-in.
- Sample credentials appear only in the prototype. The real build generates demo passwords at setup, keeps them out of the repository, labels the accounts sample, and deletes them after the event.
- Password reset is Optional; local mode has no email. An admin-assisted reset needs an audit entry.

## 6. Sessions
- Random identifiers from a secure generator with enough entropy (Likely at least 64 bits), stored server-side as hashes; never in URLs.
- Cookie flags HttpOnly and SameSite; Secure when served over HTTPS (browsers treat localhost specially; Likely).
- New session ID at sign-in and at re-authentication (Verified).
- Idle timeout and absolute lifetime, both enforced on the server (Verified). Starting values (Likely, tune and document): users 15 to 30 minutes idle, admins 5 to 15 minutes idle, absolute a few hours.
- No "remember me" persistent logins (Verified).
- Protect state-changing requests with CSRF tokens (Verified; see security-hardening.md section 18).
- Log session events without IDs. Admins can end any session (Verified).

## 7. Admin protections
- A second factor is required (Verified as recommended for sensitive accounts). Method is decision 18: a one-time code shown only on the host console for the demo, or an authenticator-app code (library Unknown).
- Only an administrator can unlock safe mode or change protected settings, after re-authentication and with a second approving administrator.
- Stricter timeouts than users; one active session per admin is Optional.
- Demo admin accounts are labeled sample and deleted after the event.
- Every admin action is audited with account ID and action, never free text; admins cannot change their own role or switch off auditing.
- Admin screens word leads as "pattern consistent with", never as conclusions.

## 8. Authorization
Deny by default. The server checks role and ownership on every request. User data is scoped by the customer ID from the session, never from the request. Internal endpoints use their own path prefix and role check. Failed authorization is logged and counts toward the lock triggers. Hiding a control in the browser is never enough. The tests are generated from this matrix.
| Capability | Customer | Reviewer | Administrator |
|---|---|---|---|
| View and change own data, settings, consent, appliances | Yes | No | No |
| View another customer's data | No | No | No |
| View the review queue and leads | No | Yes | Yes |
| Mark a lead reviewed, request a field check | No | Yes | Yes |
| View protection status | No | Yes | Yes |
| View the audit log | No | Own actions | All |
| Unlock safe mode | No | No | Yes, with a second approving administrator |
| Change protected settings (thresholds, lock settings, theft-lead criteria) | No | No | Yes, audited; criteria changes need a second approver |
| Create or disable internal accounts | No | No | Setup step only (an admin screen is Optional) |

## 9. Screens (prototype mapping)
Sign-in page with User and Admin tabs; username and password; the Admin tab adds a one-time code field; a generic error line; a "Back to home" button; neutral locked and session-expired notices. Flow: landing, sign in, consent on first sign-in, Overview; Admin tab, code, review queue; Sign out returns to the sign-in page. The prototype shows sample credentials; the real build never does.

## 10. Tests (plan; run with synthetic accounts)
| Area | Cases |
|---|---|
| Sign-in | Valid user; wrong password; unknown username gives the same message and similar timing; hostile-looking input in both fields is plain data with no error leak |
| Throttling and lockout | Repeated failures slow down, then lock temporarily, then recover after expiry; one attacker cannot lock out other accounts |
| Sessions | New ID after sign-in; the old ID is rejected; idle and absolute expiry; sign-out invalidates server-side; cookie flags set |
| Authorization | Every role against every route and action in the matrix, allowed and denied; unauthenticated requests redirect; cross-customer access is blocked; reviewers and administrators cannot read appliance names or notes |
| Admin | Second factor required; wrong code refused; a reviewer cannot unlock; an administrator needs re-authentication and a second approving administrator |
| Passwords | Stored as salted Argon2id hashes with the expected parameters; no plain text in the database, logs, or exports |
| Audit | Events recorded without passwords or session IDs |
| Cross-site request forgery | A state-changing request without a valid token is rejected |
| Auto-lock | Repeated admin failures raise the level; the unlock path works |

## 11. Optional and Unknown
Optional: self-registration, password reset, authenticator-app enrollment screens, single-session admins. Not allowed: persistent "remember me", shared accounts, sample credentials in a real build. Unknown: hashing library, second-factor method, session store design, final timeout values.
