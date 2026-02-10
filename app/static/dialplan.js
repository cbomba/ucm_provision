/* =========================
   Element references
   ========================= */
const envSelect = document.getElementById("envSelect");
const passphraseInput = document.getElementById("passphrase");
const testEnvBtn = document.getElementById("testEnvBtn");
const loadBtn = document.getElementById("loadDialplanBtn");
const verifyBtn = document.getElementById("verifyGlobalsBtn");
const statusEl = document.getElementById("dialplanStatus");

const exampleCard = document.getElementById("exampleSiteCard");
const partitionsCard = document.getElementById("partitionsCard");
const cssCard = document.getElementById("cssCard");
const globalsCard = document.getElementById("globalsCard");

let currentEnv = null;
let dialplanLoaded = false;
let connectionVerified = false;
let sitePartitionMap = {};
let globalVerification = {
  verified: new Set(),
  missing: new Set()
};

/* =========================
   Initial locked state
   ========================= */
envSelect.disabled = true;
testEnvBtn.disabled = true;
loadBtn.disabled = true;
verifyBtn.disabled = true;

/* =========================
   Passphrase gatekeeper
   ========================= */
passphraseInput.addEventListener("input", () => {
  const hasPassphrase = passphraseInput.value.trim().length > 0;

  envSelect.disabled = !hasPassphrase;
  testEnvBtn.disabled = true;
  loadBtn.disabled = true;
  verifyBtn.disabled = true;

  connectionVerified = false;
  dialplanLoaded = false;
  statusEl.textContent = "";

  if (!hasPassphrase) {
    envSelect.value = "";
    currentEnv = null;
  }
});

/* =========================
   Environment selection
   ========================= */
envSelect.addEventListener("change", () => {
  currentEnv = envSelect.value || null;

  testEnvBtn.disabled = !(currentEnv && passphraseInput.value.trim());
  loadBtn.disabled = true;
  verifyBtn.disabled = true;

  connectionVerified = false;
  dialplanLoaded = false;
  statusEl.textContent = "";
});

/* =========================
   Load environments
   ========================= */
async function loadEnvs() {
  const res = await fetch("/api/envs");
  const envs = await res.json();

  envSelect.innerHTML = '<option value="">— Select an environment —</option>';

  envs.forEach(e => {
    const opt = document.createElement("option");
    opt.value = e.name;
    opt.textContent = e.name;
    envSelect.appendChild(opt);
  });
}

/* =========================
   Test connection
   ========================= */
testEnvBtn.addEventListener("click", async () => {
  if (!currentEnv) return;

  const passphrase = passphraseInput.value.trim();
  statusEl.textContent = "Testing connection…";

  try {
    const res = await fetch(
      `/api/envs/test?name=${encodeURIComponent(currentEnv)}&passphrase=${encodeURIComponent(passphrase)}`,
      { method: "POST" }
    );

    const data = await res.json();

    if (res.ok) {
      statusEl.textContent = "✅ Connection successful";
      connectionVerified = true;
      loadBtn.disabled = false;
    } else {
      statusEl.textContent = `❌ ${data.detail || data.message}`;
      connectionVerified = false;
      loadBtn.disabled = true;
    }

  } catch (e) {
    statusEl.textContent = "❌ Connection failed";
    connectionVerified = false;
    loadBtn.disabled = true;
  }
});

/* =========================
   Load dialplan
   ========================= */
loadBtn.addEventListener("click", async () => {
  if (!connectionVerified) return;

  statusEl.textContent = "Loading dial plan…";

  const res = await fetch(`/api/dialplans/${encodeURIComponent(currentEnv)}`);

  if (!res.ok) {
    statusEl.textContent = "❌ Dial plan not found";
    return;
  }

  dialplanLoaded = true;
  exampleCard.classList.remove("hidden");
  verifyBtn.disabled = false;
  statusEl.textContent = "✅ Dial plan loaded";
});

/* =========================
   Render example site
   ========================= */
document.getElementById("renderExampleBtn").addEventListener("click", async () => {
  if (!dialplanLoaded) return;

  const payload = {
    site: document.getElementById("siteCode").value,
    site_code: document.getElementById("siteCode").value,
    site_name: document.getElementById("siteName").value,
    city: document.getElementById("city").value,
    state: document.getElementById("state").value,
    org: "US"
  };

  const res = await fetch(
    `/api/dialplans/${encodeURIComponent(currentEnv)}/render`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );

  const data = await res.json();
  renderPartitions(data.partitions);
  renderCss(data.css);
});

/* =========================
   Render partitions
   ========================= */
function renderPartitions(partitions) {
  partitionsCard.classList.remove("hidden");

  const tbody = document.getElementById("partitionsTable");
  tbody.innerHTML = "";

  // 🔑 Build key → resolved name map
  sitePartitionMap = {};
  partitions.forEach(p => {
    sitePartitionMap[p.key] = p.name;
  });

  partitions.forEach(p => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.key}</td>
      <td><strong>${p.name}</strong></td>
      <td>${p.description}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* =========================
   Render CSS
   ========================= */
function renderCss(cssList) {
  cssCard.classList.remove("hidden");

  const container = document.getElementById("cssList");
  container.innerHTML = "";

  cssList.forEach(c => {
    const div = document.createElement("div");
    div.className = "css-card";

    const members = c.members.map(m => {
      const icon = m.type === "global" ? "🌐" : "🏢";

      const resolvedName =
        m.type === "site"
          ? sitePartitionMap[m.name] || m.name
          : m.name;

      let statusClass = "unverified";
      if (globalVerification.missing.has(resolvedName)) {
        statusClass = "missing";
      } else if (globalVerification.verified.has(resolvedName)) {
        statusClass = "verified";
      }

      return `
        <li
          class="css-member ${statusClass}"
          data-partition-name="${resolvedName}">
          ${icon} ${resolvedName}
        </li>
      `;
    }).join("");

    div.innerHTML = `
      <h3>${c.name}</h3>
      <p class="muted">${c.description}</p>
      <ul>${members}</ul>
    `;

    container.appendChild(div);
  });
}

/* =========================
   Verify globals
   ========================= */
verifyBtn.addEventListener("click", async () => {
  if (!dialplanLoaded) return;

  const passphrase = passphraseInput.value.trim();
  if (!passphrase) return;

  const res = await fetch(
    `/api/dialplans/${encodeURIComponent(currentEnv)}/verify-globals`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passphrase })
    }
  );

  const data = await res.json();

  globalVerification.verified = new Set(data.found || []);
  globalVerification.missing  = new Set(data.missing || []);

  document.querySelectorAll(".css-member").forEach(el => {
    const name = el.dataset.partitionName;
    if (!name) return;

    el.classList.remove("verified", "missing", "unverified");

    if (globalVerification.missing.has(name)) {
      el.classList.add("missing");
    } else if (globalVerification.verified.has(name)) {
      el.classList.add("verified");
    } else {
      el.classList.add("unverified");
    }
  });

  globalsCard.classList.remove("hidden");
  document.getElementById("globalsOut").textContent =
    JSON.stringify(data, null, 2);
});

/* =========================
   Init
   ========================= */
loadEnvs();