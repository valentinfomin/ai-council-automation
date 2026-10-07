#!/usr/bin/env python3
"""
Sync Logins from Desktop Brave Browser to AI Council Automation Profile.
Use this after logging into ChatGPT, Claude, Gemini, or Grok in your regular Brave browser.
"""

import os
import subprocess
import sys

def main():
    src = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")
    dst = os.path.expanduser("~/.config/BraveSoftware/Brave-Automation")

    print("=" * 70)
    print("🔄 SYNC LOGINS FROM DESKTOP BRAVE TO AUTOMATION PROFILE")
    print("=" * 70)
    print(f"Source: {src}")
    print(f"Target: {dst}\n")

    if not os.path.exists(src):
        print(f"[Error] Desktop Brave profile not found at: {src}")
        sys.exit(1)

    os.makedirs(dst, exist_ok=True)

    cmd = [
        "rsync",
        "-a",
        "--exclude=Singleton*",
        "--exclude=LOCK*",
        "--exclude=*.lock",
        "--exclude=Default/Cache*",
        "--exclude=Default/Code Cache*",
        "--exclude=Default/GPUCache*",
        f"{src}/",
        f"{dst}/",
    ]
    try:
        subprocess.run(cmd, check=True)
        print("[Success] All active logins, cookies, and tokens copied to AI Council Automation profile!")
        print("You can now run council_runner.py seamlessly.")
    except Exception as e:
        print(f"[Error] Sync failed: {e}")

if __name__ == "__main__":
    main()
