"""
Configuration settings and selector maps for Local AI Council Browser Automation.
Supports ChatGPT, Claude, Gemini, and Grok.
"""

import os

# Default Browser Paths (Dedicated Brave Automation Profile)
BRAVE_EXECUTABLE_PATH = os.environ.get("BRAVE_PATH", "/usr/bin/brave-browser")
DEFAULT_USER_DATA_DIR = os.path.expanduser(
    os.environ.get("BRAVE_USER_DATA", "~/.config/BraveSoftware/Brave-Automation")
)
DEFAULT_PROFILE_DIRECTORY = os.environ.get("BRAVE_PROFILE", "Default")

# Browser Context Launch Arguments (Cleaned to remove --no-sandbox warning banner)
DEFAULT_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]

# Timeouts in milliseconds
DEFAULT_TIMEOUT_MS = 30000
GENERATION_TIMEOUT_MS = 300000  # 5 minutes max wait per response

# Model Platform Configuration & Fallback CSS Selectors
MODEL_CONFIGS = {
    "chatgpt": {
        "name": "ChatGPT",
        "url": "https://chatgpt.com",
        "prompt_input_selectors": [
            "#prompt-textarea",
            "textarea#mobile-composer-prompt",
            "#mobile-composer-prompt",
            "div#prompt-textarea",
            "textarea[data-id='root']",
            "textarea",
        ],
        "submit_button_selectors": [
            "button[data-testid='send-button']",
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[aria-label*='Отправить']",
            "button[aria-label*='отправить']",
            "button:has(svg)",
        ],
        "streaming_stop_selectors": [
            "button[data-testid='stop-button']",
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
            "button[aria-label*='Остановить']",
            "button[aria-label*='остановить']",
            "button[aria-label*='Прекратить']",
        ],
        "response_message_selectors": [
            "article[data-testid^='conversation-turn-']",
            "div[data-message-author-role='assistant']",
            "div.markdown",
            ".agent-turn",
            "div.prose",
        ],
    },
    "claude": {
        "name": "Claude",
        "url": "https://claude.ai",
        "prompt_input_selectors": [
            "div[contenteditable='true']",
            "fieldset div[contenteditable='true']",
            "div.ProseMirror",
            "textarea",
        ],
        "submit_button_selectors": [
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[aria-label*='Отправить']",
            "button[aria-label*='отправить']",
            "button:has(svg)",
        ],
        "streaming_stop_selectors": [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
            "button[aria-label*='Остановить']",
            "button[aria-label*='остановить']",
        ],
        "response_message_selectors": [
            ".font-claude-message",
            "div.grid-cols-1",
            "div[data-is-streaming]",
            "div.prose",
        ],
    },
    "gemini": {
        "name": "Gemini",
        "url": "https://gemini.google.com/app",
        "prompt_input_selectors": [
            "rich-textarea div[contenteditable='true']",
            "div[contenteditable='true']",
            ".qd-input",
            "textarea",
        ],
        "submit_button_selectors": [
            "button.send-button",
            "button.send-button-container",
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[aria-label*='Отправить']",
            "button[aria-label*='отправить']",
            "button:has(mat-icon[fonticon='send'])",
        ],
        "streaming_stop_selectors": [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
            "button[aria-label*='Остановить']",
            "button[aria-label*='остановить']",
            "mat-icon[fonticon='stop']",
            "button:has(mat-icon[fonticon='stop'])",
            "button.stop-button",
        ],
        "response_message_selectors": [
            "message-content",
            "model-response",
            "div.model-response-text",
            ".markdown",
        ],
    },
    "grok": {
        "name": "Grok",
        "url": "https://grok.com",
        "prompt_input_selectors": [
            "textarea",
            "div[contenteditable='true']",
            "input[type='text']",
        ],
        "submit_button_selectors": [
            "button[type='submit']",
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[aria-label*='Отправить']",
            "button[aria-label*='отправить']",
        ],
        "streaming_stop_selectors": [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
            "button[aria-label*='Остановить']",
            "button[aria-label*='остановить']",
        ],
        "response_message_selectors": [
            "div.response-message",
            "div.prose",
            "div[class*='message']",
            "article",
        ],
    },
}
