// Service worker for Local AI Council Extension

// Configure side panel to open on action icon click
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((err) => {
  console.warn("sidePanel.setPanelBehavior not supported on this browser version:", err);
});

// Message Passing Listener
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "QUERY_TABS") {
    (async () => {
      try {
        const tabs = await chrome.tabs.query({});
        const modelTabs = {};

        for (const tab of tabs) {
          if (!tab.url) continue;
          if (tab.url.includes("chatgpt.com")) modelTabs["chatgpt"] = tab.id;
          else if (tab.url.includes("gemini.google.com")) modelTabs["gemini"] = tab.id;
          else if (tab.url.includes("claude.ai")) modelTabs["claude"] = tab.id;
          else if (tab.url.includes("grok.com")) modelTabs["grok"] = tab.id;
        }

        sendResponse({ success: true, modelTabs });
      } catch (exc) {
        sendResponse({ success: false, error: String(exc) });
      }
    })();
    return true; // Keep message channel open for async response
  }

  if (message.type === "OPEN_TAB") {
    (async () => {
      try {
        const tab = await chrome.tabs.create({ url: message.url, active: false });
        sendResponse({ success: true, tabId: tab.id });
      } catch (exc) {
        sendResponse({ success: false, error: String(exc) });
      }
    })();
    return true;
  }
});
