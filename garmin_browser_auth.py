#!/usr/bin/env python3
"""
Garmin Connect browser-assisted authentication.

Fallback for when Cloudflare is blocking the normal login POST to
sso.garmin.com. You log in with a real browser (which Cloudflare allows),
paste the resulting ticket back here, and this script uses garth's internal
token-exchange functions — which hit connectapi.garmin.com, not the blocked
SSO host — to produce the OAuth1/OAuth2 token pair that garmin_mcp_server.py
expects at ~/.garminconnect/.

This is a drop-in alternative to garmin_auth.py. It writes the same
oauth1_token.json / oauth2_token.json files, so no other code needs to change.
"""

import re
import sys
import webbrowser
from pathlib import Path

import garth
from garth import sso
from garth.exc import GarthException, GarthHTTPError

TOKEN_DIR = Path.home() / ".garminconnect"

SIGNIN_URL = (
    "https://sso.garmin.com/sso/signin"
    "?id=gauth-widget"
    "&embedWidget=true"
    "&gauthHost=https%3A%2F%2Fsso.garmin.com%2Fsso%2Fembed"
    "&service=https%3A%2F%2Fsso.garmin.com%2Fsso%2Fembed"
    "&source=https%3A%2F%2Fsso.garmin.com%2Fsso%2Fembed"
    "&redirectAfterAccountLoginUrl=https%3A%2F%2Fsso.garmin.com%2Fsso%2Fembed"
    "&redirectAfterAccountCreationUrl=https%3A%2F%2Fsso.garmin.com%2Fsso%2Fembed"
)


def extract_ticket(raw: str) -> str | None:
    """Pull a ticket out of either a full URL or a bare ticket string."""
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return None
    m = re.search(r"ticket=([^&\s\"'<>]+)", raw)
    if m:
        return m.group(1)
    # Bare ticket fallback — garmin tickets look like 'ST-<digits>-<stuff>-cas'
    if raw.startswith("ST-"):
        return raw
    return None


def main():
    print(
        """
    ╔═══════════════════════════════════════════════════╗
    ║   GARMIN CONNECT BROWSER AUTHENTICATION           ║
    ║   ─────────────────────────────────────────       ║
    ║   Cloudflare-safe fallback using a real browser   ║
    ╚═══════════════════════════════════════════════════╝
    """
    )

    print("STEP 1 — sign in with your real browser")
    print("-" * 55)
    print("Opening the Garmin SSO sign-in page in your default browser.")
    print("If it doesn't open automatically, copy-paste this URL:\n")
    print(f"  {SIGNIN_URL}\n")

    try:
        webbrowser.open(SIGNIN_URL)
    except Exception:
        pass

    print("Sign in normally (complete MFA if prompted).")
    print()
    print("STEP 2 — grab the ticket")
    print("-" * 55)
    print(
        "After you click 'Sign In', the browser will land on a page whose URL\n"
        "contains '?ticket=ST-...'. That URL can flash by quickly and redirect\n"
        "away, so you have two options:\n"
    )
    print(
        "  (a) Fast path: copy the URL from the address bar the moment login\n"
        "      completes — before it redirects — and paste it below.\n"
    )
    print(
        "  (b) Reliable path: BEFORE clicking Sign In, open Chrome DevTools\n"
        "      (Cmd+Option+I) → Network tab → check 'Preserve log'. Sign in,\n"
        "      then find the POST to '/sso/signin' in the Network list,\n"
        "      open its Response tab, and search (Cmd+F in the response)\n"
        "      for 'embed?ticket='. Copy everything from 'ST-' up to the\n"
        "      next quote character and paste it below.\n"
    )

    raw = input("Paste the post-login URL or just the ticket (ST-...): ").strip()
    ticket = extract_ticket(raw)

    if not ticket:
        print(
            "\nCouldn't find a ticket in that input. Expected either a URL\n"
            "containing '?ticket=ST-...' or a bare ticket starting with 'ST-'."
        )
        sys.exit(1)

    print(f"\nExtracted ticket: {ticket[:24]}…")
    print("\nSTEP 3 — exchange ticket for OAuth tokens")
    print("-" * 55)
    print("Calling connectapi.garmin.com/oauth-service/oauth/preauthorized …")

    client = garth.http.Client()
    try:
        oauth1 = sso.get_oauth1_token(ticket, client)
    except GarthHTTPError as e:
        print(f"\nOAuth1 exchange failed: {e}")
        print(
            "\nThe ticket is likely expired (they're single-use and short-lived).\n"
            "Re-run this script and grab a fresh ticket."
        )
        sys.exit(1)
    except Exception as e:
        print(f"\nOAuth1 exchange failed: {e}")
        sys.exit(1)

    print("Calling connectapi.garmin.com/oauth-service/oauth/exchange/user/2.0 …")
    try:
        oauth2 = sso.exchange(oauth1, client)
    except Exception as e:
        print(f"\nOAuth2 exchange failed: {e}")
        sys.exit(1)

    client.configure(oauth1_token=oauth1, oauth2_token=oauth2)

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    client.dump(str(TOKEN_DIR))
    print(f"\nTokens written to: {TOKEN_DIR}")
    for fname in ("oauth1_token.json", "oauth2_token.json"):
        fpath = TOKEN_DIR / fname
        print(f"  {fname}: {'OK' if fpath.exists() else 'MISSING'}")

    # Best-effort verification — non-fatal if this fails
    print("\nSTEP 4 — verifying token by hitting the Garmin API")
    print("-" * 55)
    try:
        profile = client.connectapi("/userprofile-service/socialProfile")
        if isinstance(profile, dict):
            name = profile.get("fullName") or profile.get("displayName") or "(unknown)"
            print(f"Authenticated as: {name}")
        else:
            print("(Profile response was not a dict — tokens saved anyway.)")
    except GarthException as e:
        print(f"(Could not verify profile: {e} — tokens saved anyway.)")
    except Exception as e:
        print(f"(Could not verify profile: {e} — tokens saved anyway.)")

    print("\nDone. Your Garmin MCP server is ready to use:")
    print("  python garmin_mcp_server.py")


if __name__ == "__main__":
    main()
