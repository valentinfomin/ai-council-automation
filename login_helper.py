#!/usr/bin/env python3
"""
Brave Profile Login Helper
Launches Brave Browser with the automation profile so you can log in to
ChatGPT, Claude, Gemini, and Grok without any script timeouts or mock keyring wipes.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

from config import BRAVE_EXECUTABLE_PATH, DEFAULT_LAUNCH_ARGS

def main():
    print("=" * 75)
    print("🌐 BRAVE PROFILE LOGIN HELPER (KEYRING ENCRYPTION SUPPORTED)")
    print("=" * 75)
    print("This tool opens Brave Browser with your dedicated automation profile.")
    print("Please log into your accounts for ChatGPT, Claude, Gemini, and Grok.")
    print("All logins/cookies will be saved permanently for the AI Council.\n")

    user_data_dir = os.path.expanduser("~/.config/BraveSoftware/Brave-Automation")
    os.makedirs(user_data_dir, exist_ok=True)

    urls = [
        ("ChatGPT", "https://chatgpt.com"),
        ("Gemini", "https://gemini.google.com/app"),
    ]

    launch_args = list(DEFAULT_LAUNCH_ARGS)
    launch_args.append("--password-store=detect")

    with sync_playwright() as p:
        print(f"[Init] Launching Brave browser from: {BRAVE_EXECUTABLE_PATH}")
        print(f"[Init] User Data Directory: {user_data_dir}\n")

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=BRAVE_EXECUTABLE_PATH,
            headless=False,
            ignore_default_args=["--password-store=basic", "--use-mock-keychain"],
            args=launch_args,
            viewport={"width": 1366, "height": 850},
            ignore_https_errors=True,
        )

        # Open tabs for each model
        for name, url in urls:
            print(f"[Tab] Opening {name} ({url})...")
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception as e:
                print(f"[Warning] Error opening {url}: {e}")
            time.sleep(1)

        print("\n" + "★" * 75)
        print("ALL TABS OPENED IN BRAVE BROWSER.")
        print("1. Switch to the Brave browser window.")
        print("2. Log into ChatGPT, Claude, Gemini, and Grok.")
        print("   (Tip: On Claude, if Google Auth closes, log in using Email Code - enter your email and copy the 6-digit code sent to your email!)")
        print("3. When finished, press [ENTER] below to save session and exit.")
        print("★" * 75 + "\n")

        try:
            input("Press [ENTER] after completing all logins in Brave > ")
        except (KeyboardInterrupt, EOFError):
            pass

        print("\nSaving session and closing browser...")
        context.close()
        print("Done! All sessions saved. You can now run council_runner.py.")

if __name__ == "__main__":
    main()
