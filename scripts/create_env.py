from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / ".env.example"
target = ROOT / ".env"

if target.exists():
    print(".env already exists; left unchanged.")
    raise SystemExit(0)
text = source.read_text(encoding="utf-8")
text = text.replace("GENERATE_ME", secrets.token_urlsafe(48))
target.write_text(text, encoding="utf-8")
try:
    target.chmod(0o600)
except OSError:
    pass
print("Created .env with a unique local APP_SECRET_KEY.")
print("Edit DATABASE_URL and MIGRATION_DATABASE_URL to use your local MySQL accounts.")
print("The .env file is excluded from version control. Do not share it.")
