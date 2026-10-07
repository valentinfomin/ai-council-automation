# 🏛️ Local AI Council — Chrome / Brave Extension

An automated local **AI Council** Chrome Extension (Manifest V3 Side Panel).

It coordinates multiple top-tier web-based AI interfaces (**ChatGPT**, **Claude**, **Gemini**, and **Grok**) directly inside your active browser tabs to run multi-round peer reviews, double-blind deliberations, and chairman synthesis — **without requiring paid API keys**.

---

## 🌟 Key Features

- **🧩 Chrome / Brave Extension Side Panel:** Runs directly in your browser sidebar while you browse.
- **🤖 Multi-Model Integration:** Works natively with ChatGPT (`chatgpt.com`), Gemini (`gemini.google.com`), Claude (`claude.ai`), and Grok (`grok.com`).
- **👑 Custom Chairman Selection:** Select **Auto (1st Checked)** or explicitly assign **ChatGPT**, **Gemini**, **Claude**, or **Grok** as Chairman to synthesize the final executive resolution.
- **🔍 Double-Blind Peer Review:** Anonymizes proposals during evaluation rounds to eliminate model bias.
- **💬 Interactive Follow-Up Clarifications:** Ask clarifying questions post-consensus; the council reviews clarifications and the Chairman rewrites the complete executive consensus resolution.
- **🏆 Clean Executive Output:** Displays clean, structured executive consensus resolutions without cluttering the screen with intermediate drafts.
- **💸 100% Always Free:** Uses your existing browser sessions — zero API tokens or subscriptions required.

---

## 📦 Installation & Setup

1. Open your Chromium browser (**Brave**, **Chrome**, **Edge**, etc.).
2. Navigate to `brave://extensions` or `chrome://extensions`.
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select this repository directory.
5. Pin the **Local AI Council** extension and click its icon to open the Side Panel!

> **Note:** Make sure you are logged into your accounts on `chatgpt.com`, `gemini.google.com`, `claude.ai`, and `grok.com` in your browser tabs.

---

## 📁 Repository Structure

```
ai_council_automation/
├── manifest.json          # Extension configuration & side panel manifest
├── background.js          # Service worker for tab management & injection
├── content_scripts/       # Content scripts for web DOM injection
│   └── ai_injector.js     # Universal AI prompt injector & response listener
├── side_panel/            # Extension UI Side Panel
│   ├── side_panel.html    # Side panel interface
│   ├── side_panel.css     # Dark mode glassmorphism styles
│   └── side_panel.js      # Council deliberation & state manager
├── icons/                 # Extension app icons (16px, 48px, 128px)
└── README.md              # Documentation
```

---

## 📄 License

MIT License — Free and Open Source.
