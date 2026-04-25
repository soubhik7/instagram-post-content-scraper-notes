"""
Run this locally after logging in to generate the INSTAGRAM_SESSION_B64 env var value.

Usage:
    python export_session.py m.soubhik7
"""
import base64, os, sys

username = sys.argv[1] if len(sys.argv) > 1 else input("Instagram username: ").strip()
session_path = os.path.join(os.path.abspath("sessions"), f"session-{username}")

if not os.path.exists(session_path):
    print(f"Session file not found: {session_path}")
    print("Log in via the local app first, then re-run this script.")
    sys.exit(1)

with open(session_path, "rb") as f:
    encoded = base64.b64encode(f.read()).decode()

print("\nCopy this value into Render → Environment → INSTAGRAM_SESSION_B64:\n")
print(encoded)
