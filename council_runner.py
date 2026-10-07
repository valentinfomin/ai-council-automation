#!/usr/bin/env python3
"""
Local AI Council Browser Automation
Automates multi-model consensus debate across ChatGPT, Gemini, Claude, and Grok.

Features:
- Multi-Round Brainstorm & Consensus Loop: Prevents hallucinations via peer verification.
- Smart Convergence: Models agree, critique, or refine opponent ideas to reach true consensus.
- Chairman Consensus Resolution: Produces a final unified Board Verdict.
- Double-Blind Anonymization: Prevents model bias (Candidate 1, Candidate 2...).
- Full Audit Log: Exports detailed JSON mapping and full multi-round history.
"""

import argparse
import datetime
import json
import os
import sys
import time
from typing import Dict, List, Optional

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from config import (
    BRAVE_EXECUTABLE_PATH,
    DEFAULT_LAUNCH_ARGS,
    DEFAULT_PROFILE_DIRECTORY,
    DEFAULT_TIMEOUT_MS,
    DEFAULT_USER_DATA_DIR,
    GENERATION_TIMEOUT_MS,
    MODEL_CONFIGS,
)


def launch_brave_context(
    playwright: Playwright,
    user_data_dir: str = DEFAULT_USER_DATA_DIR,
    profile_directory: str = DEFAULT_PROFILE_DIRECTORY,
    headless: bool = False,
    executable_path: str = BRAVE_EXECUTABLE_PATH,
) -> BrowserContext:
    """
    Launch Playwright persistent Chromium context using dedicated Brave automation profile.

    Args:
        playwright: Active Playwright instance.
        user_data_dir: Path to Brave user data directory.
        profile_directory: Profile folder name (e.g. 'Default').
        headless: Run browser in headless mode if True.
        executable_path: Path to Brave browser binary.

    Returns:
        BrowserContext: Launched persistent browser context.
    """
    if not os.path.exists(executable_path):
        print(f"[Error] Brave binary not found at: {executable_path}")
        print("Please check your Brave installation or set BRAVE_PATH environment variable.")
        sys.exit(1)

    expanded_data_dir = os.path.expanduser(user_data_dir)
    os.makedirs(expanded_data_dir, exist_ok=True)

    launch_args = list(DEFAULT_LAUNCH_ARGS)
    launch_args.append(f"--profile-directory={profile_directory}")
    launch_args.append("--password-store=detect")

    print(f"[Init] Launching Brave browser from: {executable_path}")
    print(f"[Init] Automation Profile Directory: {expanded_data_dir}")
    print(f"[Init] Headless: {headless}")

    try:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=expanded_data_dir,
            executable_path=executable_path,
            headless=headless,
            ignore_default_args=["--password-store=basic", "--use-mock-keychain"],
            args=launch_args,
            viewport={"width": 1366, "height": 850},
            ignore_https_errors=True,
        )
        context.on("page", lambda p: print(f"[Browser Event] New tab/popup opened: {p.url}"))
        return context
    except Exception as exc:
        err_msg = str(exc)
        print(f"\n[Error] Failed to launch Brave browser context: {err_msg}")
        if "SingletonLock" in err_msg or "in use" in err_msg.lower():
            print("\n" + "=" * 70)
            print("[WARNING] BRAVE AUTOMATION PROFILE IS CURRENTLY OPEN!")
            print("Please close any open automation windows before running council_runner.py.")
            print("=" * 70 + "\n")
        sys.exit(1)


def find_element_with_fallbacks(
    page: Page, selectors: List[str], timeout_ms: int = 5000
) -> Optional[str]:
    """
    Search page for the first matching selector from a list of fallbacks.
    """
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=timeout_ms):
                return selector
        except Exception:
            continue
    return None


def handle_authentication_pause(page: Page, model_name: str, url: str) -> bool:
    """
    Check if the page requires authentication/login and pause if needed.
    """
    current_url = page.url.lower()
    needs_auth = False

    if any(k in current_url for k in ["/login", "signin", "auth", "accounts.google.com"]):
        needs_auth = True
    else:
        input_found = False
        for sel in ["#prompt-textarea", "textarea#mobile-composer-prompt", "div[contenteditable='true']", "textarea"]:
            try:
                if page.locator(sel).first.is_visible(timeout=1500):
                    input_found = True
                    break
            except Exception:
                pass
        if not input_found:
            needs_auth = True

    if needs_auth:
        print("\n" + "=" * 75)
        print(f"🔑 [AUTHENTICATION REQUIRED] LOGIN NEEDED FOR {model_name.upper()}")
        print(f"Current Page URL: {page.url}")
        print(f"Action Required: Switch to Brave browser, log into {model_name} ({url}),")
        print("and then press [ENTER] in this terminal when finished.")
        print("=" * 75 + "\n")

        try:
            input(f">>> Press [ENTER] in this terminal after logging into {model_name}... ")
        except (KeyboardInterrupt, EOFError):
            print("\n[Auth] User cancelled login wait.")
            return False

        print(f"[{model_name}] Reloading page and verifying login status...")
        try:
            page.reload(wait_until="domcontentloaded")
            time.sleep(3.0)
        except Exception:
            pass

    return True


def send_prompt(page: Page, model_key: str, prompt_text: str) -> bool:
    """
    Locate input area for a model, clear existing content, insert prompt text instantly, and submit.
    """
    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]

    print(f"[{model_name}] Checking if previous generation is still active...")
    # Wait up to 15 seconds for any previous streaming stop button to disappear
    for _ in range(30):
        if not any(_is_visible(page, s) for s in config["streaming_stop_selectors"]):
            break
        time.sleep(0.5)

    print(f"[{model_name}] Locating prompt input element...")
    input_selector = find_element_with_fallbacks(
        page, config["prompt_input_selectors"], timeout_ms=10000
    )

    if not input_selector:
        print(f"[{model_name}] [Error] Could not locate input box using configured selectors.")
        return False

    try:
        element = page.locator(input_selector).first
        element.wait_for(state="visible", timeout=10000)
        element.click()
        time.sleep(0.3)

        is_contenteditable = element.evaluate("el => el.isContentEditable")

        if is_contenteditable:
            print(f"[{model_name}] Clearing and setting prompt content in editable container...")
            element.evaluate("(el) => { el.focus(); el.innerText = ''; }")
            time.sleep(0.1)
            # Use Playwright's keyboard.insert_text for instant text injection
            page.keyboard.insert_text(prompt_text)
            element.evaluate("(el) => { el.dispatchEvent(new Event('input', { bubbles: true })); }")
        else:
            print(f"[{model_name}] Filling prompt into form element ({input_selector})...")
            element.fill(prompt_text)

        time.sleep(0.5)

        submit_selector = find_element_with_fallbacks(
            page, config["submit_button_selectors"], timeout_ms=4000
        )
        if submit_selector:
            print(f"[{model_name}] Clicking submit button ({submit_selector})...")
            page.click(submit_selector)
        else:
            print(f"[{model_name}] Submit button not found/disabled, pressing Enter...")
            page.keyboard.press("Enter")

        time.sleep(1.0)
        return True
    except Exception as exc:
        print(f"[{model_name}] [Error] Failed during prompt entry: {exc}")
        return False


def get_response_text(page: Page, response_selectors: list) -> str:
    """Extract the latest response text from the page."""
    for sel in response_selectors:
        try:
            locs = page.locator(sel)
            count = locs.count()
            if count > 0:
                return locs.nth(count - 1).inner_text().strip()
        except Exception:
            pass
    return ""


def count_responses(page: Page, response_selectors: list) -> int:
    """Count total response elements currently on the page."""
    for sel in response_selectors:
        try:
            c = page.locator(sel).count()
            if c > 0:
                return c
        except Exception:
            pass
    return 0


def wait_for_completion(
    page: Page,
    model_key: str,
    baseline_text: str = "",
    timeout_ms: int = GENERATION_TIMEOUT_MS,
) -> None:
    """
    Wait for stream response generation to complete.

    Phase 1 — Wait for Generation Start (up to 10s):
        Watches for stop button to appear, input box to become disabled,
        or response text length to increase beyond baseline_text.

    Phase 2 — Wait for Generation Completion:
        Polls until:
        1. Stop button is NO LONGER visible.
        2. Response text is non-empty and has changed from baseline_text.
        3. Response text has remained identical for STABLE_SECS (4 seconds).
    """
    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]
    stop_selectors = config["streaming_stop_selectors"]
    response_selectors = config["response_message_selectors"]

    POLL_INTERVAL = 1.0
    STABLE_SECS = 4
    MAX_WAIT = timeout_ms / 1000

    print(f"[{model_name}] Phase 1: Waiting for response generation to start...")

    # Phase 1: Wait up to 10s for generation start
    elapsed = 0.0
    started = False

    for _ in range(20):  # 20 * 0.5s = 10s max start wait
        time.sleep(0.5)
        elapsed += 0.5

        stop_visible = any(_is_visible(page, s) for s in stop_selectors)
        current_text = get_response_text(page, response_selectors)

        if stop_visible or (current_text and len(current_text) > len(baseline_text)):
            print(f"[{model_name}] ✓ Generation in progress (stop_button={stop_visible}, len={len(current_text)}).")
            started = True
            break

    if not started:
        print(f"[{model_name}] ⚠ Warning: Generation start signal not detected within 10s. Checking current state...")

    # Phase 2: Wait for completion
    print(f"[{model_name}] Phase 2: Monitoring generation progress until complete...")
    last_text = get_response_text(page, response_selectors)
    stable_count = 0

    while elapsed < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        stop_visible = any(_is_visible(page, s) for s in stop_selectors)
        current_text = get_response_text(page, response_selectors)

        if current_text == last_text and len(current_text) > 0:
            stable_count += 1
            print(f"[{model_name}] Stable {stable_count}/{STABLE_SECS}s | stop_visible={stop_visible} | len={len(current_text)}")
        else:
            stable_count = 0
            last_text = current_text

        # Generation complete condition:
        # 1. Stop button is GONE
        # 2. Text is non-empty and has stabilized for STABLE_SECS
        if stable_count >= STABLE_SECS and not stop_visible:
            print(f"[{model_name}] ✓ Generation complete ({len(current_text)} chars).")
            time.sleep(0.5)
            return

    print(f"[{model_name}] ⚠ Timeout ({int(elapsed)}s) reached — proceeding with extracted text.")


def _is_visible(page: Page, selector: str) -> bool:
    """Safe visibility check returning bool."""
    try:
        return page.locator(selector).first.is_visible(timeout=300)
    except Exception:
        return False


def extract_latest_response(page: Page, model_key: str) -> str:
    """
    Extract the text content of the latest assistant message.
    """
    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]
    selectors = config["response_message_selectors"]

    for selector in selectors:
        try:
            locators = page.locator(selector)
            count = locators.count()
            if count > 0:
                last_element = locators.nth(count - 1)
                text = last_element.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue

    print(f"[{model_name}] [Warning] Could not extract text via configured response selectors.")
    return "(Failed to extract response text. Please inspect selector configurations.)"


def get_or_create_model_page(
    context: BrowserContext, model_pages: Dict[str, Page], model_key: str
) -> Page:
    """
    Get existing open tab for a model or open a new persistent tab without closing it.
    """
    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]
    url = config["url"]

    if model_key in model_pages and not model_pages[model_key].is_closed():
        page = model_pages[model_key]
        print(f"[{model_name}] Switching to existing open tab...")
        page.bring_to_front()
        return page

    print(f"[{model_name}] Opening new persistent tab for {url}...")
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    time.sleep(3.0)
    model_pages[model_key] = page
    page.bring_to_front()
    return page


def query_model(
    context: BrowserContext,
    model_pages: Dict[str, Page],
    model_key: str,
    prompt: str,
) -> str:
    """
    Execute a full query cycle using a persistent open tab for the model.
    """
    if model_key not in MODEL_CONFIGS:
        return f"[Error: Unknown model '{model_key}']"

    config = MODEL_CONFIGS[model_key]
    model_name = config["name"]

    print(f"\n" + "=" * 60)
    print(f"[Council Step] Activating tab for {model_name}...")
    print("=" * 60)

    page = get_or_create_model_page(context, model_pages, model_key)
    try:
        handle_authentication_pause(page, model_name, config["url"])

        # Snapshot baseline text BEFORE sending prompt
        baseline_text = get_response_text(page, config["response_message_selectors"])
        print(f"[{model_name}] Baseline text length: {len(baseline_text)}")

        success = send_prompt(page, model_key, prompt)
        if not success:
            return f"[{model_name} Error: Failed to submit prompt]"

        wait_for_completion(page, model_key, baseline_text=baseline_text)
        response_text = extract_latest_response(page, model_key)

        return response_text
    except Exception as exc:
        print(f"[{model_name}] [Error] Exception during query: {exc}")
        return f"[{model_name} Error: {exc}]"



def build_prompt_with_language(prompt_text: str, lang: str = "auto") -> str:
    """Prepend strict language constraint instructions to prompt text if specified."""
    if lang == "ru":
        prefix = (
            "ВАЖНОЕ ТРЕБОВАНИЕ: Отвечайте СТРОГО на русском языке.\n"
            "Весь ваш ответ, сгенерированный анализ, аргументы и выводы должны быть написаны НА РУССКОМ ЯЗЫКЕ.\n\n"
        )
        return prefix + prompt_text
    elif lang == "en":
        prefix = (
            "IMPORTANT REQUIREMENT: Respond STRICTLY in English.\n"
            "All your response, generated analysis, arguments, and conclusions must be written IN ENGLISH.\n\n"
        )
        return prefix + prompt_text
    return prompt_text


def save_checkpoint(output_dir: str, data: Dict[str, object]) -> None:
    """Save real-time checkpoint state to council_checkpoint.json."""
    os.makedirs(output_dir, exist_ok=True)
    ckpt_file = os.path.join(output_dir, "council_checkpoint.json")
    with open(ckpt_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint(output_dir: str) -> Optional[Dict[str, object]]:
    """Load existing checkpoint state from council_checkpoint.json if present."""
    ckpt_file = os.path.join(output_dir, "council_checkpoint.json")
    if os.path.exists(ckpt_file):
        try:
            with open(ckpt_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Checkpoint] Warning: Failed to parse checkpoint {ckpt_file}: {e}")
    return None


def run_interactive_loop(
    context: BrowserContext,
    model_pages: Dict[str, Page],
    chairman_key: str,
    output_dir: str,
    task_prompt: str,
    results: Dict[str, object],
    lang: str = "auto",
) -> None:
    """
    Run an interactive follow-up Q&A loop with the Council Chairman in their active browser tab.
    """
    chairman_name = MODEL_CONFIGS.get(chairman_key, {}).get("name", "Chairman")
    print("\n" + "★" * 70)
    print(f"💬 INTERACTIVE COUNCIL CHAT WITH CHAIRMAN ({chairman_name})")
    print("Type your follow-up question below, or type 'exit' / 'quit' to finish.")
    print("★" * 70 + "\n")

    qa_history = []

    while True:
        try:
            user_q = input("\n>>> Follow-up Question for AI Council Chairman (or 'exit') > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Interactive] Exiting interactive chat session.")
            break

        if not user_q or user_q.lower() in ["exit", "quit", "q"]:
            print("[Interactive] Session ended by user.")
            break

        print(f"\n[Interactive] Sending follow-up to {chairman_name}...")
        raw_prompt = (
            f"You are acting as Chairman of the AI Council.\n"
            f"Original Task:\n\"{task_prompt}\"\n\n"
            f"Consensus Resolution Summary:\n\"{str(results.get('consensus', ''))[:1200]}\"\n\n"
            f"User Follow-up Question:\n\"{user_q}\"\n\n"
            f"Please provide an authoritative, clear follow-up answer on behalf of the Executive Board."
        )
        prompt = build_prompt_with_language(raw_prompt, lang)

        ans = query_model(context, model_pages, chairman_key, prompt)

        print(f"\n" + "=" * 60)
        print(f"📜 [Chairman Follow-up Answer] ({chairman_name}):\n")
        print(ans)
        print("=" * 60)

        qa_history.append({"question": user_q, "answer": ans})

        summary_path = os.path.join(output_dir, "council_output.md")
        if os.path.exists(summary_path):
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(f"\n### 💬 Interactive Q&A Follow-up\n**Question:** {user_q}\n\n**[{chairman_name} Chairman Answer]:**\n{ans}\n\n---\n")

    results["interactive_qa"] = qa_history


def run_council(
    context: BrowserContext,
    selected_models: List[str],
    task_prompt: str,
    max_rounds: int = 1,
    lang: str = "auto",
    resume: bool = False,
    output_dir: str = ".",
) -> Dict[str, object]:
    """
    Run the multi-model double-blind consensus council workflow with language constraints and checkpoints.
    """
    proposals: Dict[str, str] = {}
    debates: List[Dict[str, str]] = []
    model_pages: Dict[str, Page] = {}
    anonymous_mapping: Dict[str, str] = {}
    candidate_labels: Dict[str, str] = {}
    chairman_key: str = ""

    # Check for resume checkpoint
    ckpt = load_checkpoint(output_dir) if resume else None
    if ckpt:
        print("\n" + "🔄" * 35)
        print("[Resume] Found existing session checkpoint. Restoring state...")
        proposals = ckpt.get("proposals", {})
        debates = ckpt.get("debates", [])
        anonymous_mapping = ckpt.get("mapping", {})
        candidate_labels = ckpt.get("candidate_labels", {})
        chairman_key = ckpt.get("chairman_key", "")
        print(f"[Resume] Restored {len(proposals)} proposals and {len(debates)} debate rounds.")
        print("🔄" * 35 + "\n")

    # Stage 1: Proposals
    if not proposals:
        print("\n" + "★" * 70)
        print("STAGE 1: GENERATING INITIAL PROPOSALS FROM AI COUNCIL")
        print("★" * 70)

        formatted_task = build_prompt_with_language(task_prompt, lang)

        for key in selected_models:
            model_name = MODEL_CONFIGS[key]["name"]
            print(f"\n>>> Requesting Proposal from {model_name}...")
            proposals[key] = query_model(context, model_pages, key, formatted_task)

        # Filter active models
        active_keys = [k for k, text in proposals.items() if not text.startswith("[") or "Error" not in text]

        if not active_keys:
            print("\n[Warning] No active models returned valid proposals in Stage 1.")
            return {"proposals": proposals, "debates": [], "consensus": "", "mapping": {}, "model_pages": model_pages}

        for idx, key in enumerate(active_keys):
            label = f"Candidate Proposal {idx + 1}"
            candidate_labels[key] = label
            anonymous_mapping[label] = MODEL_CONFIGS[key]["name"]

        chairman_key = active_keys[0]

        save_checkpoint(output_dir, {
            "task_prompt": task_prompt,
            "proposals": proposals,
            "debates": debates,
            "mapping": anonymous_mapping,
            "candidate_labels": candidate_labels,
            "chairman_key": chairman_key,
            "stage": 1,
        })
    else:
        active_keys = [k for k in proposals.keys() if not proposals[k].startswith("[") or "Error" not in proposals[k]]
        if not chairman_key and active_keys:
            chairman_key = active_keys[0]

    print("\n" + "🔒" * 35)
    print("DOUBLE-BLIND ANONYMIZATION APPLIED")
    for key, label in candidate_labels.items():
        print(f"  - {MODEL_CONFIGS[key]['name']} -> {label}")
    print("🔒" * 35 + "\n")

    # Stage 2: Iterative Brainstorm & Debate Loop
    last_round_responses = dict(proposals)
    if debates:
        last_round_responses = debates[-1]

    start_round = len(debates) + 1
    for round_num in range(start_round, max_rounds + 1):
        print("\n" + "★" * 70)
        print(f"STAGE 2: BRAINSTORM & DEBATE ROUND {round_num} OF {max_rounds}")
        print("★" * 70)

        round_critiques: Dict[str, str] = {}

        for reviewer_key in active_keys:
            reviewer_name = MODEL_CONFIGS[reviewer_key]["name"]

            peer_text = ""
            for target_key in active_keys:
                if target_key != reviewer_key:
                    label = candidate_labels[target_key]
                    text = last_round_responses[target_key]
                    peer_text += f"\n--- {label.upper()} ---\n{text}\n"

            if not peer_text:
                continue

            raw_debate_prompt = (
                f"Please provide an objective evaluation of these proposed solutions for the task:\n"
                f"Original Task Requirement:\n\"{task_prompt}\"\n\n"
                f"Candidate Solutions:\n{peer_text}\n\n"
                f"Instructions:\n"
                f"1. Identify any factual inaccuracies, hallucinations, or logical flaws.\n"
                f"2. Highlight strong points you agree with.\n"
                f"3. Provide your updated, refined solution striving for optimal consensus."
            )
            formatted_debate_prompt = build_prompt_with_language(raw_debate_prompt, lang)

            print(f"\n>>> Requesting Debate Round {round_num} Input from {reviewer_name}...")
            resp = query_model(context, model_pages, reviewer_key, formatted_debate_prompt)
            round_critiques[reviewer_key] = resp

        debates.append(round_critiques)
        last_round_responses = round_critiques

        save_checkpoint(output_dir, {
            "task_prompt": task_prompt,
            "proposals": proposals,
            "debates": debates,
            "mapping": anonymous_mapping,
            "candidate_labels": candidate_labels,
            "chairman_key": chairman_key,
            "stage": 2,
            "round": round_num,
        })

    # Stage 3: Board Consensus Resolution
    print("\n" + "★" * 70)
    print("STAGE 3: EXECUTIVE BOARD CONSENSUS RESOLUTION")
    print("★" * 70)

    chairman_name = MODEL_CONFIGS[chairman_key]["name"]

    all_debates_summary = ""
    for idx, d_round in enumerate(debates):
        all_debates_summary += f"\n=== DEBATE ROUND {idx+1} ===\n"
        for k, txt in d_round.items():
            label = candidate_labels.get(k, MODEL_CONFIGS[k]["name"])
            all_debates_summary += f"\n[{label} Review]:\n{txt}\n"

    raw_consensus_prompt = (
        f"You are acting as the Chairman of the AI Council.\n"
        f"Task:\n\"{task_prompt}\"\n\n"
        f"Deliberation History across Council Members:\n{all_debates_summary}\n\n"
        f"Please issue the final Executive Board Consensus Resolution:\n"
        f"1. Final Agreed Solution (Consensus Strategy)\n"
        f"2. Key Risks & Eliminated Hallucinations/Flaws\n"
        f"3. Action Plan / Executive Summary."
    )
    formatted_consensus_prompt = build_prompt_with_language(raw_consensus_prompt, lang)

    print(f"\n>>> Requesting Final Executive Board Resolution from {chairman_name} (Chairman)...")
    final_consensus = query_model(context, model_pages, chairman_key, formatted_consensus_prompt)

    results = {
        "proposals": proposals,
        "debates": debates,
        "consensus": final_consensus,
        "mapping": anonymous_mapping,
        "candidate_labels": candidate_labels,
        "chairman": chairman_name,
        "chairman_key": chairman_key,
        "model_pages": model_pages,
    }

    save_checkpoint(output_dir, {
        "task_prompt": task_prompt,
        "proposals": proposals,
        "debates": debates,
        "consensus": final_consensus,
        "mapping": anonymous_mapping,
        "candidate_labels": candidate_labels,
        "chairman": chairman_name,
        "chairman_key": chairman_key,
        "stage": 3,
    })

    return results


def export_markdown_report(
    task_prompt: str,
    results: Dict[str, object],
    output_dir: str = ".",
) -> None:
    """
    Save proposals, debate rounds, consensus resolution, and JSON mapping audit log.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    proposals: Dict[str, str] = results.get("proposals", {})
    debates: List[Dict[str, str]] = results.get("debates", [])
    consensus: str = results.get("consensus", "")
    mapping: Dict[str, str] = results.get("mapping", {})
    candidate_labels: Dict[str, str] = results.get("candidate_labels", {})
    chairman: str = results.get("chairman", "Council Chairman")

    # Save Detailed JSON Audit & History Log
    json_log_path = os.path.join(output_dir, "council_mapping_log.json")
    log_data = {
        "timestamp": timestamp,
        "task_prompt": task_prompt,
        "anonymized_mapping": mapping,
        "proposals": {MODEL_CONFIGS[k]["name"]: v for k, v in proposals.items()},
        "debates": [
            {MODEL_CONFIGS[k]["name"]: v for k, v in d_round.items()}
            for d_round in debates
        ],
        "final_consensus_resolution": consensus,
    }
    with open(json_log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    # Save Stage 1 Proposals
    stage1_path = os.path.join(output_dir, "stage1_proposals.md")
    with open(stage1_path, "w", encoding="utf-8") as f:
        f.write(f"# AI Council Stage 1 - Initial Proposals\n")
        f.write(f"**Date:** {timestamp}\n\n")
        f.write(f"## Original Task\n> {task_prompt}\n\n")
        for key, text in proposals.items():
            name = MODEL_CONFIGS[key]["name"]
            label = candidate_labels.get(key, name)
            f.write(f"## Model: {name} (`{label}`)\n\n{text}\n\n---\n\n")

    # Save Stage 2 Debates
    stage2_path = os.path.join(output_dir, "stage2_critiques.md")
    with open(stage2_path, "w", encoding="utf-8") as f:
        f.write(f"# AI Council Stage 2 - Brainstorm & Peer Debates\n")
        f.write(f"**Date:** {timestamp}\n\n")
        f.write(f"## Original Task\n> {task_prompt}\n\n")
        for idx, d_round in enumerate(debates):
            f.write(f"# Debate Round {idx + 1}\n\n")
            for key, text in d_round.items():
                name = MODEL_CONFIGS[key]["name"]
                f.write(f"## Review by {name}\n\n{text}\n\n---\n\n")

    # Save Combined Executive Council Summary
    summary_path = os.path.join(output_dir, "council_output.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# 📜 Local AI Council Executive Report\n")
        f.write(f"**Generated:** {timestamp}\n\n")
        f.write(f"## Task Description\n> {task_prompt}\n\n")

        # Section 1: Executive Board Consensus Resolution
        f.write("---\n\n")
        f.write(f"## 🏆 Executive Board Consensus Resolution (Synthesized by {chairman})\n\n")
        f.write(f"{consensus}\n\n")
        f.write("---\n\n")

        # Section 2: Attribution Mapping Key
        f.write("## 🔍 Anonymization & Model Attribution Key\n\n")
        f.write("| Anonymized Label | Actual AI Model |\n")
        f.write("|---|---|\n")
        for label, model_name in mapping.items():
            f.write(f"| **{label}** | `{model_name}` |\n")
        f.write("\n---\n\n")

        # Section 3: Initial Proposals Overview
        f.write("## 1. Initial Proposals Overview\n")
        for key, text in proposals.items():
            name = MODEL_CONFIGS[key]["name"]
            label = candidate_labels.get(key, name)
            f.write(f"### [{name}] Proposal (`{label}`)\n\n{text}\n\n")

        # Section 4: Brainstorm & Debates
        f.write("---\n\n")
        f.write("## 2. Peer Review & Debate Deliberations\n")
        for idx, d_round in enumerate(debates):
            f.write(f"### Round {idx + 1} Deliberations\n")
            for key, text in d_round.items():
                name = MODEL_CONFIGS[key]["name"]
                f.write(f"#### [{name}] Peer Review\n\n{text}\n\n")

    print(f"\n[Success] Executive Council outputs & audit logs saved to:")
    print(f"  - Executive Summary & Consensus: {summary_path}")
    print(f"  - Detailed Audit Log: {json_log_path}")
    print(f"  - Stage 1 Proposals: {stage1_path}")
    print(f"  - Stage 2 Debates: {stage2_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Local AI Council Browser Automation (Consensus & Brainstorm Loop)"
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task description prompt to run through the AI Council.",
    )
    parser.add_argument(
        "--task-file",
        type=str,
        help="Path to a text file containing the task description prompt.",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="chatgpt,gemini",
        help="Comma-separated list of models to include (chatgpt,claude,gemini,grok). Default: chatgpt,gemini.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of debate rounds to conduct (default: 1 round).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["auto", "ru", "en"],
        default="auto",
        help="Strict language enforcement for model outputs ('auto', 'ru', 'en'). Default: auto.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume an interrupted council session from council_checkpoint.json if present.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Enter interactive Q&A follow-up mode with the Council Chairman after consensus is reached.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False).",
    )
    parser.add_argument(
        "--user-data-dir",
        type=str,
        default=DEFAULT_USER_DATA_DIR,
        help="Path to Brave user data directory.",
    )
    parser.add_argument(
        "--profile-dir",
        type=str,
        default=DEFAULT_PROFILE_DIRECTORY,
        help="Brave profile directory name (e.g. 'Default').",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory where output markdown files and JSON mapping logs will be saved.",
    )

    args = parser.parse_args()

    # Determine task prompt
    task_prompt = ""
    if args.task:
        task_prompt = args.task
    elif args.task_file and os.path.exists(args.task_file):
        with open(args.task_file, "r", encoding="utf-8") as f:
            task_prompt = f.read().strip()
    elif args.resume and os.path.exists(os.path.join(args.output_dir, "council_checkpoint.json")):
        ckpt = load_checkpoint(args.output_dir)
        if ckpt and "task_prompt" in ckpt:
            task_prompt = ckpt["task_prompt"]
            print(f"[Resume] Restored task prompt from checkpoint: \"{task_prompt}\"")

    if not task_prompt and not args.resume:
        print("[Input] Enter the task prompt for the AI Council:")
        task_prompt = input("> ").strip()

    if not task_prompt:
        print("[Error] No task prompt provided. Exiting.")
        sys.exit(1)

    # Parse requested models
    requested_models = [m.strip().lower() for m in args.models.split(",") if m.strip()]
    valid_models = [m for m in requested_models if m in MODEL_CONFIGS]

    if not valid_models:
        print(f"[Error] No valid models specified. Choose from: {list(MODEL_CONFIGS.keys())}")
        sys.exit(1)

    print(f"\nStarting Local AI Council Session (Language: {args.lang.upper()}, Rounds: {args.rounds}) with models: {[MODEL_CONFIGS[m]['name'] for m in valid_models]}")

    with sync_playwright() as playwright:
        context = launch_brave_context(
            playwright=playwright,
            user_data_dir=args.user_data_dir,
            profile_directory=args.profile_dir,
            headless=args.headless,
            executable_path=BRAVE_EXECUTABLE_PATH,
        )

        try:
            results = run_council(
                context=context,
                selected_models=valid_models,
                task_prompt=task_prompt,
                max_rounds=args.rounds,
                lang=args.lang,
                resume=args.resume,
                output_dir=args.output_dir,
            )
            export_markdown_report(
                task_prompt=task_prompt,
                results=results,
                output_dir=args.output_dir,
            )

            if args.interactive and results.get("chairman_key") and results.get("model_pages"):
                run_interactive_loop(
                    context=context,
                    model_pages=results["model_pages"],
                    chairman_key=results["chairman_key"],
                    output_dir=args.output_dir,
                    task_prompt=task_prompt,
                    results=results,
                    lang=args.lang,
                )

            print("\n" + "★" * 70)
            print("[Done] Council session complete. Results saved.")
            print("The Brave browser window will remain OPEN for your review.")
            print(">>> To exit the script and close the browser, press Ctrl+C in this terminal.")
            print("★" * 70 + "\n")
            try:
                while True:
                    time.sleep(1)
            except (KeyboardInterrupt, EOFError):
                print("\n[Exit] Closing browser context...")
        except Exception as exc:
            print(f"\n[Error] Council session failed: {exc}")


if __name__ == "__main__":
    main()
