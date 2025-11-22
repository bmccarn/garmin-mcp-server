#!/usr/bin/env python3
"""
Garmin Connect Authentication Setup
Run this script to authenticate with Garmin Connect and save tokens for the MCP server.
Supports MFA (two-factor authentication via SMS).
"""

import os
import sys
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

# Token storage directory
TOKEN_DIR = Path.home() / ".garminconnect"


def prompt_for_mfa():
    """Prompt user for MFA code."""
    print("\n*** Two-Factor Authentication Required ***")
    print("A verification code has been sent to your phone via SMS.")
    mfa_code = input("Enter the MFA code: ").strip()
    return mfa_code


def main():
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║   GARMIN CONNECT AUTHENTICATION SETUP             ║
    ║   ─────────────────────────────────────────       ║
    ║   Authenticate to enable the MCP server           ║
    ╚═══════════════════════════════════════════════════╝
    """)

    # Check for existing tokens
    token_file = TOKEN_DIR / "oauth1_token.json"

    if token_file.exists():
        print(f"Existing tokens found at: {TOKEN_DIR}")
        print("\nTesting existing authentication...")

        try:
            client = Garmin()
            client.login(str(TOKEN_DIR))
            name = client.get_full_name()
            print(f"\nAuthentication successful!")
            print(f"Logged in as: {name}")
            print("\nYour MCP server is ready to use.")

            choice = input("\nRe-authenticate with new credentials? (y/n): ").strip().lower()
            if choice != "y":
                return
            print()
        except Exception as e:
            print(f"Existing tokens invalid: {e}")
            print("Will need to re-authenticate.\n")

    # Get credentials
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if email:
        print(f"Using email from GARMIN_EMAIL: {email}")
    else:
        email = input("Enter your Garmin email: ").strip()

    if password:
        print("Using password from GARMIN_PASSWORD")
    else:
        password = getpass("Enter your Garmin password: ")

    print("\nAuthenticating with Garmin Connect...")

    try:
        # Create client with MFA support
        client = Garmin(email, password, prompt_mfa=prompt_for_mfa)
        client.login()

        # Save tokens
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        client.garth.dump(TOKEN_DIR)

        # Verify
        name = client.get_full_name()
        print(f"\nAuthentication successful!")
        print(f"Logged in as: {name}")
        print(f"\nTokens saved to: {TOKEN_DIR}")
        print("\nYour Garmin MCP server is now ready to use!")
        print("\nTo start the server, run:")
        print("  python garmin_mcp_server.py")
        print("\nOr with FastMCP CLI:")
        print("  fastmcp run garmin_mcp_server.py")

    except GarminConnectAuthenticationError as e:
        print(f"\nAuthentication failed: {e}")
        print("\nPlease check your credentials and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
