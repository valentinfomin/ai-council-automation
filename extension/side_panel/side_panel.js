document.addEventListener("DOMContentLoaded", () => {
  const btnRun = document.getElementById("btnRun");
  const taskPrompt = document.getElementById("taskPrompt");
  const debateRounds = document.getElementById("debateRounds");
  const chairmanSelect = document.getElementById("chairmanSelect");

  const progressText = document.getElementById("progressText");
  const consensusCard = document.getElementById("consensusCard");
  const consensusText = document.getElementById("consensusText");

  // Follow-up panel
  const followUpSection  = document.getElementById("followUpSection");
  const followUpPrompt   = document.getElementById("followUpPrompt");
  const btnFollowUp      = document.getElementById("btnFollowUp");
  const followUpStatus   = document.getElementById("followUpStatus");

  let allResults = { candidateLabels: {}, mapping: {} };

  // Shared state — set by runCouncil, reused by follow-up
  let sessionTabIds  = {};   // { chatgpt: tabId, gemini: tabId, ... }
  let sessionModels  = [];   // active model keys
  let sessionChairman = "";  // active chairman key

  function getChosenChairman(modelsList) {
    if (!modelsList || !modelsList.length) return "";
    const sel = chairmanSelect ? chairmanSelect.value : "auto";
    if (sel !== "auto" && modelsList.includes(sel)) {
      return sel;
    }
    return modelsList[0];
  }
  let followUpCount = 0;

  // --- Tab Management ---
  async function getModelTabs() {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "QUERY_TABS" }, (response) => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else if (response && response.success) resolve(response.modelTabs);
        else reject(new Error("Failed to query tabs"));
      });
    });
  }

  async function ensureScriptInjected(tabId) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content_scripts/ai_injector.js"]
      });
    } catch (e) {
      console.warn("Script injection notice:", e);
    }
    await new Promise(r => setTimeout(r, 300));
  }

  async function ensureTab(modelKey) {
    const tabs = await getModelTabs();
    if (tabs[modelKey]) {
      await ensureScriptInjected(tabs[modelKey]);
      return tabs[modelKey];
    }
    const urls = {
      chatgpt: "https://chatgpt.com",
      gemini: "https://gemini.google.com/app",
      claude: "https://claude.ai",
      grok: "https://grok.com"
    };
    const tabId = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "OPEN_TAB", url: urls[modelKey] }, (resp) => {
        if (resp && resp.success) resolve(resp.tabId);
        else reject(new Error(`Failed to open tab for ${modelKey}`));
      });
    });
    await new Promise(r => setTimeout(r, 3500));
    await ensureScriptInjected(tabId);
    return tabId;
  }

  async function sendTabPrompt(tabId, promptText) {
    await ensureScriptInjected(tabId);
    return new Promise((resolve, reject) => {
      function attemptSend(retryCount = 0) {
        chrome.tabs.sendMessage(tabId, { type: "EXECUTE_PROMPT", prompt: promptText }, (resp) => {
          if (chrome.runtime.lastError) {
            if (retryCount < 2) {
              setTimeout(() => attemptSend(retryCount + 1), 1500);
            } else {
              reject(new Error(`Connection failed: ${chrome.runtime.lastError.message}. Please reload the AI tab.`));
            }
          } else if (resp && resp.success) {
            resolve(resp.text);
          } else {
            reject(new Error(resp ? resp.error : "Failed to execute prompt in tab"));
          }
        });
      }
      attemptSend();
    });
  }

  function applyLanguage(promptText) {
    return promptText; // No forced language — model responds in task language
  }

  // --- Main Council Runner ---
  btnRun.addEventListener("click", async () => {
    const prompt = taskPrompt.value.trim();
    if (!prompt) { alert("Please enter a task description prompt."); return; }

    const selectedModels = Array.from(document.querySelectorAll(".model-chips input:checked")).map(cb => cb.value);
    if (selectedModels.length === 0) { alert("Please select at least one AI model."); return; }

    btnRun.disabled = true;
    progressText.style.display = "block";
    progressText.textContent = "Initializing council session...";

    // Reset cards
    consensusCard.style.display = "none";
    consensusText.textContent = "";
    allResults = { candidateLabels: {}, mapping: {} };

    try {
      await runCouncil(prompt, selectedModels, parseInt(debateRounds.value));
    } catch (exc) {
      progressText.textContent = `⚠️ Error: ${exc.message || exc}`;
      btnRun.disabled = false;
    }
  });

  async function runCouncil(task, models, rounds) {
    // Ensure all tabs ready
    const modelTabIds = {};
    for (const m of models) {
      progressText.textContent = `🔌 Connecting to ${m.toUpperCase()}...`;
      modelTabIds[m] = await ensureTab(m);
    }

    // Build anonymization map
    models.forEach((key, idx) => {
      const label = `Candidate ${idx + 1}`;
      allResults.candidateLabels[key] = label;
      allResults.mapping[label] = key.toUpperCase();
    });

    // ── STAGE 1: PROPOSALS ──────────────────────────────────────
    const proposals = {};
    for (const m of models) {
      progressText.textContent = `📝 [Stage 1] Querying ${m.toUpperCase()}...`;
      const text = await sendTabPrompt(modelTabIds[m], applyLanguage(task));
      proposals[m] = text;
    }

    // ── STAGE 2: PEER DEBATES ────────────────────────────────────
    let lastResponses = { ...proposals };

    for (let r = 1; r <= rounds; r++) {
      const roundCritiques = {};

      for (const reviewer of models) {
        let peerText = "";
        for (const target of models) {
          if (target !== reviewer) {
            const label = allResults.candidateLabels[target];
            peerText += `\n--- ${label} ---\n${lastResponses[target]}\n`;
          }
        }

        const rawDebate =
          `Please provide an objective evaluation of these proposed solutions:\n` +
          `Task: "${task}"\n\n` +
          `Candidate Solutions:\n${peerText}\n\n` +
          `Instructions:\n1. Identify factual flaws or hallucinations.\n2. Highlight strong points.\n3. Provide your refined solution.`;

        progressText.textContent = `🔍 [Round ${r}] ${reviewer.toUpperCase()} reviewing peers...`;
        const critiqueText = await sendTabPrompt(modelTabIds[reviewer], applyLanguage(rawDebate));
        roundCritiques[reviewer] = critiqueText;
      }

      lastResponses = roundCritiques;
    }

    // ── STAGE 3: CONSENSUS ───────────────────────────────────────
    progressText.textContent = "⚖️ [Stage 3] Chairman synthesizing consensus...";

    const chairmanKey = getChosenChairman(models);
    let historySummary = "";
    models.forEach(k => {
      historySummary += `\n[${allResults.candidateLabels[k]} Review]:\n${lastResponses[k]}\n`;
    });

    const rawConsensus =
      `You are acting as Chairman of the AI Council.\n` +
      `Task: "${task}"\n\n` +
      `Deliberation History:\n${historySummary}\n\n` +
      `Issue the COMPLETE Executive Board Consensus Resolution. Do NOT cut the response short.\n` +
      `Required sections:\n` +
      `1. Final Agreed Solution (complete and detailed)\n` +
      `2. Key Risks & Eliminated Flaws\n` +
      `3. Executive Summary & Action Plan.`;

    const finalConsensus = await sendTabPrompt(modelTabIds[chairmanKey], applyLanguage(rawConsensus));

    // Show Chairman Consensus card
    consensusCard.style.display = "flex";
    consensusCard.querySelector(".label").textContent = `🏆 Chairman Consensus Resolution (${chairmanKey.toUpperCase()})`;
    consensusText.textContent = finalConsensus;

    progressText.textContent = "✅ Deliberation Complete!";
    btnRun.disabled = false;

    // Save session state for follow-up use
    sessionTabIds   = modelTabIds;
    sessionModels   = models;
    sessionChairman = chairmanKey;
    followUpCount   = 0;

    // Reveal follow-up panel with slide-in animation
    followUpSection.style.display = "flex";
    followUpSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── FOLLOW-UP HANDLER (Mini-Council) ──────────────────────────
  btnFollowUp.addEventListener("click", async () => {
    const q = followUpPrompt.value.trim();
    if (!q) return;

    // Get models currently checked in the UI
    const activeChecked = Array.from(document.querySelectorAll(".model-chips input:checked")).map(cb => cb.value);

    if (activeChecked.length === 0) {
      followUpStatus.style.display = "block";
      followUpStatus.textContent = "⚠️ Please select at least one AI model checkbox above.";
      return;
    }

    btnFollowUp.disabled = true;
    followUpStatus.style.display = "block";

    // Ensure tabs & labels exist for all currently checked models
    for (const m of activeChecked) {
      followUpStatus.textContent = `🔌 Connecting to ${m.toUpperCase()}...`;
      try {
        sessionTabIds[m] = await ensureTab(m);
        if (!allResults.candidateLabels[m]) {
          const count = Object.keys(allResults.candidateLabels).length + 1;
          const label = `Candidate ${count}`;
          allResults.candidateLabels[m] = label;
          allResults.mapping[label] = m.toUpperCase();
        }
      } catch (err) {
        followUpStatus.textContent = `⚠️ Failed to connect to ${m.toUpperCase()}: ${err.message || err}`;
        btnFollowUp.disabled = false;
        return;
      }
    }

    sessionModels = activeChecked;
    sessionChairman = getChosenChairman(activeChecked);

    const target = document.querySelector("input[name='followTarget']:checked").value;
    let targetModels = activeChecked;
    if (target === "chairman") {
      targetModels = [sessionChairman];
    }

    followUpCount += 1;

    try {
      await runFollowUpCouncil(q, targetModels);
    } catch (err) {
      followUpStatus.textContent = `⚠️ Error: ${err.message || err}`;
    }

    followUpPrompt.value = "";
    btnFollowUp.disabled = false;
  });

  async function runFollowUpCouncil(question, models) {
    // ── Step 1: Each model answers clarification in background ──────
    const answers = {};

    for (const m of models) {
      followUpStatus.textContent = `💬 [Step 1] ${m.toUpperCase()} answering...`;
      const resp = await sendTabPrompt(sessionTabIds[m], question);
      answers[m] = resp;
    }

    // ── Step 2: Cross-review in background (only if >1 model) ────────
    let lastResponses = { ...answers };

    if (models.length > 1) {
      const critiques = {};

      for (const reviewer of models) {
        let peerSummary = "";
        for (const target of models) {
          if (target !== reviewer) {
            const label = allResults.candidateLabels[target] || target.toUpperCase();
            peerSummary += `\n--- ${label} ---\n${answers[target]}\n`;
          }
        }
        const reviewPrompt =
          `The council received a follow-up question: "${question}"\n\n` +
          `Other council members answered:\n${peerSummary}\n\n` +
          `Evaluate their answers, correct any errors, highlight strengths, ` +
          `and provide your final refined answer to the follow-up question.`;

        followUpStatus.textContent = `🔍 [Step 2] ${reviewer.toUpperCase()} reviewing peers...`;
        const critique = await sendTabPrompt(sessionTabIds[reviewer], reviewPrompt);
        critiques[reviewer] = critique;
      }
      lastResponses = critiques;
    }

    // ── Step 3: Chairman rewrites consensus ───────────────────
    followUpStatus.textContent = `⚖️ [Step 3] Chairman rewriting consensus...`;

    const chairKey = getChosenChairman(models);
    let refined = "";
    models.forEach(m => {
      const label = allResults.candidateLabels[m] || m.toUpperCase();
      refined += `\n[${label}]:\n${lastResponses[m]}\n`;
    });

    const consensusPrompt =
      `You are the Chairman of the AI Council.\n` +
      `The council was asked a follow-up clarification: "${question}"\n\n` +
      `Council members' refined positions after peer review:\n${refined}\n\n` +
      `Rewrite and issue the COMPLETE UPDATED Executive Consensus Resolution. ` +
      `Do NOT cut the response short.\n` +
      `Required sections:\n` +
      `1. Updated Final Answer to the Clarification\n` +
      `2. Revised Key Points & Corrections\n` +
      `3. Updated Executive Summary & Action Plan.`;

    const newConsensus = await sendTabPrompt(sessionTabIds[chairKey], consensusPrompt);

    // Update the Chairman Consensus card directly
    consensusText.textContent = newConsensus;
    consensusCard.style.borderColor = "rgba(6, 182, 212, 0.55)";
    consensusCard.querySelector(".label").textContent =
      `🏆 Chairman Consensus Resolution (${chairKey.toUpperCase()}) · Follow-up #${followUpCount}`;
    consensusCard.scrollIntoView({ behavior: "smooth", block: "nearest" });

    followUpStatus.textContent = `✅ Consensus updated for follow-up #${followUpCount}!`;
  }

  // Ctrl+Enter shortcut inside follow-up textarea
  followUpPrompt.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      btnFollowUp.click();
    }
  });

  function addFollowUpDivider(label) {
    const div = document.createElement("div");
    div.className = "stage-title";
    div.style.color = "var(--accent-cyan)";
    div.textContent = label;
    historyStream.appendChild(div);
  }

  function addFollowUpSubDivider(label) {
    const div = document.createElement("div");
    div.className = "stage-title";
    div.style.cssText = "color:rgba(6,182,212,0.65); font-size:0.75rem; margin-top:0.25rem;";
    div.textContent = label;
    historyStream.appendChild(div);
  }

  function makeFollowUpAccordion(emoji, title, modelKey, bodyText) {
    const item = makeAccordion(emoji, title, modelKey, bodyText, false);
    item.classList.add("followup-response");
    return item;
  }
});
