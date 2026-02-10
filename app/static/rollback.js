let rollbackViewMode = "simple";
let lastRollbackData = null;

async function loadEnvs() {
  const res = await fetch("/api/envs");
  const envs = await res.json();

  const select = document.getElementById("envSelect");
  select.innerHTML = '<option value="">— Select an environment —</option>';

  envs.forEach(e => {
    const opt = document.createElement("option");
    opt.value = e.name;
    opt.textContent = e.name;
    select.appendChild(opt);
  });
}

function formatExecutionDate(iso) {
  if (!iso) return "Unknown date";

  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit"
  });
}

async function loadExecutions() {
  const res = await fetch("/api/executions");
  const data = await res.json();

  const plans = data.executions || [];

  const select = document.getElementById("planSelect");
  select.innerHTML = "";

  // Placeholder option
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "— Select a rollback plan —";
  placeholder.disabled = true;
  placeholder.selected = true;
  select.appendChild(placeholder);

  if (plans.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "No executions found";
    opt.disabled = true;
    select.appendChild(opt);
    return;
  }

  plans.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.plan_id;

    const when = formatExecutionDate(p.started_at || p.finished_at);
    const status = p.status || "unknown";

    opt.textContent = `${when} — ${p.env_name} — ${status}`;
    opt.dataset.envName = p.env_name;

    select.appendChild(opt);
  });
}

const rollbackViewSimpleBtn = document.getElementById("planViewSimple");
const rollbackViewJsonBtn = document.getElementById("planViewJson");

if (rollbackViewSimpleBtn && rollbackViewJsonBtn) {
  rollbackViewSimpleBtn.onclick = () => {
    rollbackViewMode = "simple";
    rollbackViewSimpleBtn.classList.add("active");
    rollbackViewJsonBtn.classList.remove("active");
    renderRollbackPreview();
  };

  rollbackViewJsonBtn.onclick = () => {
    rollbackViewMode = "json";
    rollbackViewJsonBtn.classList.add("active");
    rollbackViewSimpleBtn.classList.remove("active");
    renderRollbackPreview();
  };
}


function toggleView(simpleBtn, jsonBtn, simpleEl, jsonEl) {
  simpleBtn.onclick = () => {
    simpleBtn.classList.add("active");
    jsonBtn.classList.remove("active");
    simpleEl.style.display = "block";
    jsonEl.style.display = "none";
  };

  jsonBtn.onclick = () => {
    jsonBtn.classList.add("active");
    simpleBtn.classList.remove("active");
    jsonEl.style.display = "block";
    simpleEl.style.display = "none";
  };
}

function summarizeRollback(rollbackJson) {
  const summary = {};

  rollbackJson.rollback_steps.forEach(step => {
    summary[step.type] ||= [];
    summary[step.type].push(step.name);
  });

  return summary;
}

function renderRollbackSummary(summary) {
  let lines = [];

  for (const [type, names] of Object.entries(summary)) {
    lines.push(`${type.replace("_", " ")} (${names.length}) ⚠️ DELETE`);
    names.forEach(n => lines.push(`  • ${n}`));
    lines.push("");
  }

  return lines.join("\n");
}

function renderRollbackPreview() {
  if (!lastRollbackData) return;

  const simpleEl = document.getElementById("planSimple");
  const jsonEl = document.getElementById("planJson");

  if (rollbackViewMode === "simple") {
    const summary = summarizeRollback(lastRollbackData);
    simpleEl.textContent = renderRollbackSummary(summary);
    simpleEl.classList.remove("hidden");
    jsonEl.classList.add("hidden");
  } else {
    jsonEl.textContent = JSON.stringify(lastRollbackData, null, 2);
    jsonEl.classList.remove("hidden");
    simpleEl.classList.add("hidden");
  }
}

function startProgressPoll(url) {
  const box = document.getElementById("progressBox");
  const fill = document.getElementById("progressFill");
  const text = document.getElementById("progressText");

  box.classList.remove("hidden");

  const timer = setInterval(async () => {
    const res = await fetch(url);

    if (!res.ok) {
      text.textContent = `Waiting for status... (${res.status})`;
      return; // DON'T force complete
    }

    const data = await res.json();

    const total = data.total_steps || 1;
    const done = data.completed_steps || 0;
    const pct = Math.floor((done / total) * 100);

    fill.style.width = pct + "%";

    if (data.current_step) {
      text.textContent =
        `${done} / ${total} — ${data.current_step.type}: ${data.current_step.name}`;
    } else {
      text.textContent = `${done} / ${total}`;
    }

    if (data.status && data.status !== "IN_PROGRESS") {
      clearInterval(timer);
      fill.style.width = "100%";
      text.textContent = data.status === "SUCCESS" ? "Completed" : `Done (${data.status})`;
    }
  }, 750);
}

/* =========================
   Preview rollback (SAFE)
   ========================= */
async function previewRollback() {
  const select = document.getElementById("planSelect");
  const planId = select.value;
  const envName = select.selectedOptions[0].dataset.envName;

  rollbackViewMode = "simple";
  document.getElementById("planViewSimple").classList.add("active");
  document.getElementById("planViewJson").classList.remove("active");

  if (!planId) {
    alert("Select a plan first");
    return;
  }

  const url =
    `/api/rollback/${encodeURIComponent(planId)}/preview` +
    `?env_name=${encodeURIComponent(envName)}`;

  const res = await fetch(url);
  const data = await res.json();

  lastRollbackData = data;
  renderRollbackPreview();
}


function getPassphrase() {
  const el = document.getElementById("passphrase");
  return el ? el.value.trim() : "";
}

/* =========================
   Apply rollback (DESTRUCTIVE)
   ========================= */
async function applyRollback() {
  if (!confirm("THIS WILL DELETE OBJECTS. Are you absolutely sure?")) return;

  const select = document.getElementById("planSelect");
  const planId = select.value;
  const envName = select.options[select.selectedIndex]?.dataset.envName;
  const passphrase = getPassphrase();

  if (!planId) {
  alert("Select a plan to roll back.");
  return;
}

if (!envName) {
  alert("Select an environment before executing rollback.");
  return;
}

if (!passphrase) {
  alert("Enter the passphrase to unlock credentials.");
  return;
}

  startProgressPoll(`/api/rollback/${encodeURIComponent(planId)}/status`);

  const res = await fetch("/api/rollback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_id: planId,
      env_name: envName,
      passphrase: passphrase,
      apply: true
    })
  });

  const raw = await res.text();   // 👈 ALWAYS read as text first
  console.log("RAW ROLLBACK RESPONSE:", raw);

  let output;
  try {
    output = JSON.stringify(JSON.parse(raw), null, 2);
  } catch (e) {
    output =
      "❌ Server did not return JSON\n\n" +
      "HTTP " + res.status + "\n\n" +
      raw;
  }

  const outEl = document.getElementById("executeOut");
  outEl.textContent = output;
  outEl.scrollTop = outEl.scrollHeight;
}

document.addEventListener("DOMContentLoaded", () => {
  // Load data
  loadExecutions();
  loadEnvs();

  const passphraseInput = document.getElementById("passphrase");
  const envSelect = document.getElementById("envSelect");
  const testBtn = document.getElementById("testEnvBtn");
  const applyBtn = document.getElementById("applyRollbackBtn");
  const statusEl = document.getElementById("testEnvStatus");

  // 🔒 Lock everything until passphrase is entered
  envSelect.disabled = true;
  testBtn.disabled = true;

  // Passphrase gatekeeper
  passphraseInput.addEventListener("input", e => {
    const hasPassphrase = e.target.value.trim().length > 0;

    envSelect.disabled = !hasPassphrase;
    testBtn.disabled = !hasPassphrase;
    applyBtn.disabled = !hasPassphrase;

    if (!hasPassphrase) {
      envSelect.value = "";
      statusEl.textContent = "";
    }
  });

  // Test connection handler
  testBtn.addEventListener("click", async () => {
    const envName = envSelect.value;
    const passphrase = getPassphrase();

    if (!envName || !passphrase) {
      statusEl.textContent = "Environment and passphrase required";
      return;
    }

    statusEl.textContent = "Testing…";

    try {
      const res = await fetch(
        `/api/envs/test?name=${encodeURIComponent(envName)}&passphrase=${encodeURIComponent(passphrase)}`,
        { method: "POST" }
      );

      const data = await res.json();

      statusEl.textContent =
        res.ok
          ? "✅ Connection successful"
          : `❌ ${data.detail || data.message}`;

    } catch (e) {
      statusEl.textContent = "❌ Connection failed";
    }
  });
});

const warningEl = document.getElementById("rollbackWarning");

document.getElementById("applyRollbackBtn").addEventListener("mouseenter", () => {
  warningEl.style.display = "block";
});

document.getElementById("applyRollbackBtn").addEventListener("mouseleave", () => {
  warningEl.style.display = "none";
});