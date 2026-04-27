"""
Generate an Apple Sign-In client secret JWT.

Usage:
    uv run python scripts/gen_apple_secret.py

You need four things from your Apple Developer account:
  TEAM_ID   — 10-char ID at the top-right of developer.apple.com
  KEY_ID    — ID of the .p8 key (shown when you download it)
  CLIENT_ID — your Service ID, e.g. "com.yourcompany.prepmax" (NOT the bundle ID)
  KEY_FILE  — path to the downloaded AuthKey_XXXXXXXXXX.p8 file

Paste the printed JWT into:
  Supabase Dashboard → Authentication → Providers → Apple → Secret Key
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from jose import jwt
except ImportError:
    print("Install python-jose: pip install python-jose[cryptography]")
    sys.exit(1)

# ── Fill these in ──────────────────────────────────────────────────────────────
TEAM_ID   = "63XVB98W2T"   # e.g. "ABC1234DEF"
KEY_ID    = "SA4BM3YFS9"
CLIENT_ID = "com.prepmax.app"
KEY_FILE  = "/Users/ebukaegbunam/Downloads/AuthKey_SA4BM3YFS9.p8"
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    missing = [k for k, v in [("TEAM_ID", TEAM_ID), ("KEY_ID", KEY_ID), ("CLIENT_ID", CLIENT_ID), ("KEY_FILE", KEY_FILE)] if not v]
    if missing:
        print(f"Error: fill in {', '.join(missing)} at the top of this script.")
        sys.exit(1)

    key_path = Path(KEY_FILE)
    if not key_path.exists():
        print(f"Error: key file not found: {key_path}")
        sys.exit(1)

    private_key = key_path.read_text()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=180)   # Apple max is 6 months

    token = jwt.encode(
        {
            "iss": TEAM_ID,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "aud": "https://appleid.apple.com",
            "sub": CLIENT_ID,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )

    print("\n── Apple client secret JWT ─────────────────────────────")
    print(token)
    print("────────────────────────────────────────────────────────")
    print(f"\nValid until: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print("Paste into: Supabase → Authentication → Providers → Apple → Secret Key\n")


if __name__ == "__main__":
    main()
