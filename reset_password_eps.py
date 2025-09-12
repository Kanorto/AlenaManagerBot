#!/usr/bin/env python3
"""
Reset a user's password in the EPS (Event Planner System) SQLite database.

This script DOES NOT read or reveal any existing passwords. It simply sets a new password
hash (PBKDF2-HMAC-SHA256, format "salthex$hashhex") for the specified user email.

Usage:
    python reset_password_eps.py --db ./event_planner_api/event_planner.db --email admin@ex.com --password "NewStrongPass!234"

If --password is omitted, you will be prompted to enter it securely.
"""

import os
import sys
import sqlite3
import argparse
import getpass
import hashlib
from datetime import datetime

def hash_password(password: str) -> str:
    """Hash password using PBKDF2‑HMAC‑SHA256 with 100k iterations.
    Returns "salthex$hashhex".
    """
    salt = os.urandom(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{salt.hex()}${dk.hex()}"

def main():
    ap = argparse.ArgumentParser(description="Reset EPS user password (SQLite).")
    ap.add_argument("--db", required=True, help="Path to SQLite DB file (e.g., ./event_planner_api/event_planner.db)")
    ap.add_argument("--email", required=True, help="User email to update")
    ap.add_argument("--password", help="New password. If omitted, you'll be prompted securely.")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"[!] DB not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    new_password = args.password or getpass.getpass("Enter NEW password: ")
    if not new_password:
        print("[!] Empty password is not allowed.", file=sys.stderr)
        sys.exit(1)

    hashed = hash_password(new_password)

    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM users WHERE email = ?", (args.email,))
        row = cur.fetchone()
        if not row:
            print(f"[!] No user found with email: {args.email}", file=sys.stderr)
            sys.exit(2)

        cur.execute(
            "UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?",
            (hashed, args.email),
        )
        conn.commit()
        print(f"[+] Password updated for user: {args.email}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
