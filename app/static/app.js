let uploadId = null;
let planId = null;
let selectedEnv = null;
let planViewMode = "simple";
let lastPlanData = null;

console.log("app.js loaded");
window.onerror = (msg, src, line, col, err) => {
  console.error("GLOBAL JS ERROR:", msg, err);
};

async function loadEnvs() {
  const r = await fetch("/api/envs");
  if (!r.ok) {
    console.error(await r.text());
    return;
  }
  const envs = await r.json();
  console.log("loading envs", envs);
  const sel = document.getElementById("envSelect");
  sel.innerHTML = '<option value="">— Select an environment —</option>';

  envs.forEach(e => {
    const opt = document.createElement("option");
    opt.value = e.name;
    opt.textContent =
      (e.env_type === "test" ? "🧪 " : "🚨 ") + e.name;
    sel.appendChild(opt);
  });

  if (envs.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(create an env below)";
    sel.appendChild(opt);
  }
}

function setText(id, html) {
  const el = document.getElementById(id);
  if (!el) {
    console.warn(`setText(): element '${id}' not found`);
    return;
  }
  el.innerHTML = html;
}

function requireEnv(actionName) {
  if (!selectedEnv) {
    setText("planStatus", `<p class="error">Select an environment before ${actionName}.</p>`);
    return false;
  }
  return true;
}

function updatePlanButton() {
  const hasEnv = !!currentEnvName;
  const hasCsv = !!uploadedCsvName;
  document.getElementById("planBtn").disabled = !(hasEnv && hasCsv);
}

function showError(msg) {
  setText("planStatus", `<p class="err">${msg}</p>`);
}

function updateUiState() {
  const uploadBtn = document.getElementById("uploadBtn");
  const planBtn = document.getElementById("planBtn");
  const executeBtn = document.getElementById("executeBtn");

  // Upload requires env
  uploadBtn.disabled = false;

  // Build plan requires env + CSV
  planBtn.disabled = !(selectedEnv && uploadId);

  // Execute requires plan
  executeBtn.disabled = !planId;
}

const planViewSimpleBtn = document.getElementById("planViewSimple");
const planViewJsonBtn = document.getElementById("planViewJson");

if (planViewSimpleBtn && planViewJsonBtn) {
  planViewSimpleBtn.onclick = () => {
    planViewMode = "simple";
    setActive("planViewSimple", "planViewJson");
    renderPlanPreview();
  };

  planViewJsonBtn.onclick = () => {
    planViewMode = "json";
    setActive("planViewJson", "planViewSimple");
    renderPlanPreview();
  };
}

function setActive(activeId, inactiveId) {
  document.getElementById(activeId).classList.add("active");
  document.getElementById(inactiveId).classList.remove("active");
}

function renderPlanPreview() {
  if (!lastPlanData) return;

  const simpleEl = document.getElementById("planSimple");
  const jsonEl = document.getElementById("planJson");

  if (planViewMode === "simple") {
    const summary = summarizePlan(lastPlanData);

    simpleEl.textContent = renderPlanSummary(summary);
    simpleEl.classList.remove("hidden");

    jsonEl.textContent = "";
    jsonEl.classList.add("hidden");
  } else {
    jsonEl.textContent = JSON.stringify(lastPlanData, null, 2);
    jsonEl.classList.remove("hidden");

    simpleEl.textContent = "";
    simpleEl.classList.add("hidden");
  }
}

function summarizePlan(planJson) {
  const summary = {};

  planJson.sites.forEach(site => {
    site.objects.forEach(obj => {
      if (obj.action !== "create") return;

      summary[obj.type] ||= [];
      summary[obj.type].push(obj.name);
    });
  });

  return summary;
}

function renderPlanSummary(summary) {
  let lines = [];

  for (const [type, names] of Object.entries(summary)) {
    lines.push(`${type.replace("_", " ")} (${names.length})`);
    names.forEach(n => lines.push(`  • ${n}`));
    lines.push(""); // blank line between groups
  }

  return lines.join("\n");
}

document.getElementById("csvFile").onchange = () => {
  if (!selectedEnv) {
    setText("uploadStatus", `<p class="err">Select an environment before choosing a CSV.</p>`);
    document.getElementById("csvFile").value = "";
  }
};

document.getElementById("uploadBtn").onclick = async () => {
  if (!selectedEnv) {
    return setText("uploadStatus", `<p class="err">Select an environment first.</p>`);
  }

  const f = document.getElementById("csvFile").files[0];
  if (!f) {
    return setText("uploadStatus", `<p class="err">Select a CSV first.</p>`);
  }

  const fd = new FormData();
  fd.append("file", f);

  setText("uploadStatus", "Uploading...");
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) {
    setText("uploadStatus", `<p class="err">${JSON.stringify(j)}</p>`);
    return;
  }
  uploadId = j.upload_id;
  setText("uploadStatus", `<p class="ok">Uploaded: ${j.filename}<br/>upload_id: ${uploadId}</p>`)
  
  updateUiState();
};

document.getElementById("planBtn").onclick = async () => {
  if (!uploadId) return setText("planStatus", `<p class="err">Upload a CSV first.</p>`);
  const envName = document.getElementById("envSelect").value;
  if (!envName) return setText("planStatus", `<p class="err">Select or create an environment.</p>`);
  const org = (document.getElementById("orgInput").value || "").trim();

  setText("planStatus", "Building plan...");
  const r = await fetch("/api/plan", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ upload_id: uploadId, env_name: envName, org: org || null })
  });
  const j = await r.json();
  if (!r.ok) {
    setText("planStatus", `<p class="err">${JSON.stringify(j)}</p>`);
    return;
  }
  planId = j.plan_id;
  lastPlan = j.plan;
  lastPlanData = j.plan;
  updateUiState();

  const errs = (j.errors || []).map(x => `<li class="err">${x}</li>`).join("");
  const warns = (j.warnings || []).map(x => `<li class="warn">${x}</li>`).join("");

  const summary = j.plan.summary || {};
  const summaryHtml = Object.keys(summary).map(k => {
    const c = summary[k];
    return `<li><b>${k}</b> create:${c.create||0} skip:${c.skip||0}</li>`;
  }).join("");

  setText("planStatus", `<p class="ok">Plan built: ${planId}</p>` + (errs||warns ? `<ul>${errs}${warns}</ul>` : ""));
  setText("planSummary", `<p><b>Sites:</b> ${j.plan.site_count}</p><ul>${summaryHtml}</ul>`);
  renderPlanPreview();
};

document.getElementById("executeBtn").onclick = async () => {
  if (!planId) return;

  const passphrase = document.getElementById("passphrase").value;
  if (!passphrase) {
    return setText("executeOut", `<p class="err">Enter passphrase before executing.</p>`);
  }

  startProgressPoll(planId);

  const r = await fetch("/api/execute", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ plan_id: planId, passphrase })
  });

  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    document.getElementById("executeOut").textContent = JSON.stringify(j, null, 2);
    return;
  }

  document.getElementById("executeOut").textContent = JSON.stringify(j, null, 2);
};

function setPill(name, envType) {
  const pill = document.getElementById("selectedEnvLabel");
  if (!name) {
    pill.textContent = "None";
    pill.className = "env-pill prod";
    return;
  }
  pill.textContent = name;
  pill.className = "env-pill " + (envType === "test" ? "test" : "prod");
}

async function refreshEnvDropdown(selectName = "") {
  const r = await fetch("/api/envs");
  if (!r.ok) {
    // avoid throwing JSON parse errors if backend returns HTML
    return;
  }
  const envs = await r.json();

  const sel = document.getElementById("envSelect");
  sel.innerHTML = "";

  // Placeholder option
  const ph = document.createElement("option");
  ph.value = "";
  ph.textContent = "— Select an environment —";
  sel.appendChild(ph);

  envs.forEach(e => {
    const opt = document.createElement("option");
    opt.value = e.name;
    opt.textContent = e.name;
    sel.appendChild(opt);
  });

  sel.value = selectName || "";
}

document.getElementById("saveEnvBtn").onclick = async () => {
  const name = document.getElementById("envName").value.trim();
  const cucm_url = document.getElementById("cucmUrl").value.trim();
  const cucm_username = document.getElementById("cucmUser").value.trim();
  const cucm_password = document.getElementById("cucmPass").value;
  const cucm_verify_tls = document.getElementById("verifyTls").checked;
  const passphrase = document.getElementById("passphrase").value;

  if (!name || !cucm_url || !cucm_username || !cucm_password) {
    setText("envStatus", `<p class="err">Fill name, url, username, password.</p>`);
    return;
  }
  if (!passphrase) {
    setText("envStatus", `<p class="err">Enter a passphrase to save.</p>`);
    return;
  }

  const r = await fetch(`/api/envs/${encodeURIComponent(name)}?passphrase=${encodeURIComponent(passphrase)}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name, cucm_url, cucm_username, cucm_password, cucm_verify_tls })
  });

  if (!r.ok) {
    const err = await r.json();
    alert(err.detail || "Failed to load environment");

    return;
  }

  const env = await r.json();

  setText("envStatus", `<p class="ok">Saved environment '${name}'.</p>`);
  await refreshEnvDropdown(name);

  // Enable test button once env is saved
  document.getElementById("testEnvBtn").disabled = false;

  // Update pill
  const envType = document.getElementById("envType").value || "prod";
  setPill(name, envType);
};


document.getElementById("envSelect").onchange = async (e) => {
  const name = e.target.value;

  // If user chose placeholder, reset pill + disable testing
  if (!name) {
    selectedEnv = null;
    setPill("", "prod");
    document.getElementById("testEnvBtn").disabled = true;
    updateUiState();
    return;
  }

  const passphrase = document.getElementById("passphrase").value;
  if (!passphrase) {
    alert("Enter passphrase to load environment");
    // revert selection immediately
    e.target.value = "";
    setPill("", "prod");
    document.getElementById("testEnvBtn").disabled = true;
    return;
  }

  const r = await fetch(
    `/api/envs/${encodeURIComponent(name)}?passphrase=${encodeURIComponent(passphrase)}`
  );

  const j = await r.json().catch(() => ({}));

  if (!r.ok) {
    alert(j.detail || "Failed to load environment (wrong passphrase?)");
    // revert selection so user doesn't get stuck
    e.target.value = "";
    setPill("", "prod");
    document.getElementById("testEnvBtn").disabled = true;
    return;
  }

  // success
  const env = j;
  selectedEnv = env.name;

  document.getElementById("envName").value = env.name || name;
  document.getElementById("envType").value = env.env_type || "prod";
  document.getElementById("cucmUrl").value = env.cucm_url || "";
  document.getElementById("cucmUser").value = env.cucm_username || "";
  document.getElementById("verifyTls").checked = env.cucm_verify_tls === true;

  // Never auto-fill AXL password (you said you're ok with this)
  document.getElementById("cucmPass").value = "";

  setPill(name, env.env_type || "prod");
  document.getElementById("testEnvBtn").disabled = false;

  updateUiState();
};

document.getElementById("testEnvBtn").onclick = async () => {
  const name = document.getElementById("envName").value.trim();
  const passphrase = document.getElementById("passphrase").value;

  if (!name || !passphrase) {
    alert("Environment name and passphrase required");
    return;
  }

  const r = await fetch(
    `/api/envs/test?name=${encodeURIComponent(name)}&passphrase=${encodeURIComponent(passphrase)}`,
    { method: "POST" }
  );
  

  if (!r.ok) {
    const err = await r.json();
    testEnvStatus.textContent = err.detail || "Connection failed";
    testEnvStatus.style.color = "red";
    return;
  }

  const result = await r.json();
  testEnvStatus.textContent = result.message;
  testEnvStatus.style.color = "green";
};

async function maybeShowRollbackLink() {
  try {
    const res = await fetch("/api/executions");
    if (!res.ok) return;

    const data = await res.json();
    const executions = data.executions || [];

    if (executions.length > 0) {
      document.getElementById("rollbackLink").style.display = "inline-block";
    }
  } catch (e) {
    console.warn("Rollback link check failed:", e);
  }
}

function startProgressPoll(planId) {
  const box = document.getElementById("progressBox");
  const fill = document.getElementById("progressFill");
  const text = document.getElementById("progressText");

  box.classList.remove("hidden");

  const timer = setInterval(async () => {
    const res = await fetch(`/api/executions/${planId}`);
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

    if (data.status !== "IN_PROGRESS") {
      clearInterval(timer);
      fill.style.width = "100%";
      text.textContent = "Completed";
    }
  }, 750);
}


// initial load
refreshEnvDropdown().then(() => {
  setPill("", "prod");
  document.getElementById("testEnvBtn").disabled = true;
  updateUiState();
});

document.addEventListener("DOMContentLoaded", () => {
  maybeShowRollbackLink();
  });