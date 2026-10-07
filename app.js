document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const btnRun = document.getElementById('btnRun');
  const btnResume = document.getElementById('btnResume');
  const taskPrompt = document.getElementById('taskPrompt');
  const debateRounds = document.getElementById('debateRounds');
  const targetLang = document.getElementById('targetLang');
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');

  const step1 = document.getElementById('step1');
  const step2 = document.getElementById('step2');
  const step3 = document.getElementById('step3');
  const div1 = document.getElementById('div1');
  const div2 = document.getElementById('div2');

  const candidateGrid = document.getElementById('candidateGrid');
  const consensusSection = document.getElementById('consensusSection');
  const consensusBody = document.getElementById('consensusBody');
  const btnReveal = document.getElementById('btnReveal');

  const chatHistory = document.getElementById('chatHistory');
  const chatInput = document.getElementById('chatInput');
  const btnSendChat = document.getElementById('btnSendChat');
  const terminalConsole = document.getElementById('terminalConsole');

  const tabDashboard = document.getElementById('tabDashboard');
  const tabReports = document.getElementById('tabReports');
  const viewDashboard = document.getElementById('viewDashboard');
  const viewReports = document.getElementById('viewReports');
  const reportTextarea = document.getElementById('reportTextarea');

  let isUnblinded = false;
  let pollingInterval = null;

  // Tabs Switching
  tabDashboard.addEventListener('click', () => {
    tabDashboard.classList.add('active');
    tabReports.classList.remove('active');
    viewDashboard.style.display = 'flex';
    viewReports.style.display = 'none';
  });

  tabReports.addEventListener('click', () => {
    tabReports.classList.add('active');
    tabDashboard.classList.remove('active');
    viewReports.style.display = 'flex';
    viewDashboard.style.display = 'none';
    fetchReports();
  });

  // Reveal Anonymized Models Toggle
  btnReveal.addEventListener('click', () => {
    isUnblinded = !isUnblinded;
    btnReveal.textContent = isUnblinded ? '🔓 Model Identity Revealed' : '🔒 Double-Blind Active (Click to Reveal)';
    fetchStatus();
  });

  // Run Session
  btnRun.addEventListener('click', () => startSession(false));
  btnResume.addEventListener('click', () => startSession(true));

  function startSession(resume = false) {
    const prompt = taskPrompt.value.trim();
    if (!prompt && !resume) {
      alert('Please enter a task description prompt.');
      return;
    }

    const selectedModels = Array.from(document.querySelectorAll('.chip-checkbox:checked'))
      .map(cb => cb.value)
      .join(',');

    if (!selectedModels) {
      alert('Please select at least one AI Council model.');
      return;
    }

    btnRun.disabled = true;
    statusDot.className = 'status-dot running';
    statusText.textContent = 'Council Session Running...';

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: prompt,
        models: selectedModels,
        rounds: parseInt(debateRounds.value),
        lang: targetLang.value,
        resume: resume,
      }),
    })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          alert(`Error: ${data.error}`);
          btnRun.disabled = false;
        } else {
          startPolling();
        }
      })
      .catch(err => {
        console.error(err);
        btnRun.disabled = false;
      });
  }

  // Polling Server Status
  function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(fetchStatus, 1500);
    fetchStatus();
  }

  function fetchStatus() {
    fetch('/api/status')
      .then(res => res.json())
      .then(data => {
        updateUI(data);
      })
      .catch(err => console.error(err));
  }

  function updateUI(data) {
    // Status Dot
    if (data.status === 'running') {
      statusDot.className = 'status-dot running';
      statusText.textContent = `Running: ${data.current_stage}`;
      btnRun.disabled = true;
    } else if (data.status === 'completed') {
      statusDot.className = 'status-dot';
      statusText.textContent = 'Deliberations Completed';
      btnRun.disabled = false;
    } else if (data.status === 'error') {
      statusDot.className = 'status-dot';
      statusDot.style.backgroundColor = 'var(--accent-rose)';
      statusText.textContent = `Error: ${data.error || 'Failed'}`;
      btnRun.disabled = false;
    }

    // Pipeline Steps
    const stage = data.current_stage || '';
    step1.className = 'step-item completed';
    div1.className = 'step-divider active';
    step2.className = 'step-item';
    div2.className = 'step-divider';
    step3.className = 'step-item';

    if (stage.includes('Stage 2')) {
      step2.className = 'step-item active';
    } else if (stage.includes('Stage 3')) {
      step2.className = 'step-item completed';
      div2.className = 'step-divider active';
      step3.className = 'step-item active';
    } else if (stage.includes('Completed')) {
      step2.className = 'step-item completed';
      div2.className = 'step-divider active';
      step3.className = 'step-item completed';
    }

    // Terminal Logs
    if (data.logs && data.logs.length > 0) {
      terminalConsole.innerHTML = data.logs
        .map(l => `<div class="log-line">${escapeHtml(l)}</div>`)
        .join('');
      terminalConsole.scrollTop = terminalConsole.scrollHeight;
    }

    // Checkpoint Data Rendering
    const ckpt = data.checkpoint || {};

    // Task Prompt Autofill
    if (ckpt.task_prompt && !taskPrompt.value) {
      taskPrompt.value = ckpt.task_prompt;
    }

    // Proposals Rendering
    if (ckpt.proposals && Object.keys(ckpt.proposals).length > 0) {
      const mapping = ckpt.mapping || {};
      const labels = ckpt.candidate_labels || {};

      let html = '';
      for (const [key, text] of Object.entries(ckpt.proposals)) {
        const label = labels[key] || key;
        const realName = mapping[label] || key;
        const displayName = isUnblinded ? `${realName} (${label})` : label;

        html += `
          <div class="candidate-card">
            <div class="candidate-header">
              <span class="candidate-badge">${escapeHtml(displayName)}</span>
            </div>
            <div class="candidate-text">${escapeHtml(text)}</div>
          </div>
        `;
      }
      candidateGrid.innerHTML = html;
    }

    // Consensus Resolution Rendering
    if (ckpt.consensus) {
      consensusSection.style.display = 'flex';
      consensusBody.textContent = ckpt.consensus;
    }
  }

  // Interactive Follow-up Chat
  btnSendChat.addEventListener('click', sendInteractiveChat);
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendInteractiveChat();
  });

  function sendInteractiveChat() {
    const q = chatInput.value.trim();
    if (!q) return;

    // Append User Bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble user';
    userBubble.textContent = q;
    chatHistory.appendChild(userBubble);
    chatInput.value = '';
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Show waiting bubble
    const waitBubble = document.createElement('div');
    waitBubble.className = 'chat-bubble chairman';
    waitBubble.textContent = 'Thinking... (Chairman consulting context)';
    chatHistory.appendChild(waitBubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    fetch('/api/interactive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    })
      .then(res => res.json())
      .then(data => {
        waitBubble.textContent = 'Question submitted. Processing in browser context...';
      })
      .catch(err => {
        waitBubble.textContent = `Error: ${err}`;
      });
  }

  // Fetch Reports
  function fetchReports() {
    fetch('/api/reports')
      .then(res => res.json())
      .then(data => {
        if (data['council_output.md']) {
          reportTextarea.value = data['council_output.md'];
        } else {
          reportTextarea.value = 'No executive report generated yet.';
        }
      });
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Initial Check
  fetchStatus();
});
