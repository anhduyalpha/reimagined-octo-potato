/* ============================================================
   Dotfiles Manager — Dashboard JS
   ============================================================ */

const API = "";   // same origin; change to e.g. "http://localhost:8000" for dev

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API + path, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  } catch (e) {
    throw e;
  }
}

function log(msg, type = "info") {
  const feed = document.getElementById("logFeed");
  const entry = document.createElement("div");
  entry.className = `log-entry log-${type}`;
  const ts = new Date().toLocaleTimeString();
  entry.textContent = `[${ts}] ${msg}`;
  feed.prepend(entry);
  // Keep feed tidy
  while (feed.children.length > 120) {
    feed.removeChild(feed.lastChild);
  }
}

function statusClass(status) {
  const map = {
    applied: "status-applied",
    synced:  "status-synced",
    missing: "status-missing",
    error:   "status-error",
    pending: "status-pending",
  };
  return map[status] || "status-pending";
}

function statusIcon(status) {
  const map = {
    applied: "✓",
    synced:  "⟳",
    missing: "✗",
    error:   "!",
    pending: "…",
  };
  return map[status] || "?";
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let dotfiles = [];

// ---------------------------------------------------------------------------
// Render dotfiles list
// ---------------------------------------------------------------------------

function renderDotfiles(data) {
  dotfiles = data;
  const list = document.getElementById("dotfilesList");

  if (!data.length) {
    list.innerHTML = `<div class="empty-state">No dotfiles registered yet.<br>Click <strong>+ Add Dotfile</strong> to get started.</div>`;
  } else {
    list.innerHTML = data.map(df => `
      <div class="dotfile-item" data-name="${escHtml(df.name)}">
        <div class="dotfile-icon">${statusIcon(df.status)}</div>
        <div class="dotfile-info">
          <div class="dotfile-name">${escHtml(df.name)}</div>
          <div class="dotfile-paths">${escHtml(df.source_path)} → ${escHtml(df.target_path)}</div>
        </div>
        <span class="badge ${statusBadgeClass(df.status)}">${escHtml(df.status)}</span>
        <div class="dotfile-actions">
          <button class="btn btn-sm btn-success apply-one-btn" data-name="${escHtml(df.name)}" title="Apply this dotfile">Apply</button>
          <button class="btn btn-sm btn-danger remove-btn" data-name="${escHtml(df.name)}" title="Remove">✕</button>
        </div>
      </div>
    `).join("");
  }

  updateStats(data);
}

function statusBadgeClass(status) {
  const map = {
    applied: "badge-ok",
    synced:  "badge-ok",
    missing: "badge-error",
    error:   "badge-error",
    pending: "badge-warn",
  };
  return map[status] || "badge-muted";
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

function updateStats(data) {
  document.getElementById("statTotal").textContent   = data.length;
  document.getElementById("statApplied").textContent = data.filter(d => d.status === "applied").length;
  document.getElementById("statSynced").textContent  = data.filter(d => d.status === "synced").length;
  document.getElementById("statMissing").textContent = data.filter(d => d.status === "missing").length;
}

// ---------------------------------------------------------------------------
// API actions
// ---------------------------------------------------------------------------

async function loadDotfiles() {
  try {
    const data = await apiFetch("/api/dotfiles");
    renderDotfiles(data);
    setConnected(true);
  } catch (e) {
    log("Failed to load dotfiles: " + e.message, "error");
    setConnected(false);
  }
}

async function syncDotfiles() {
  log("Syncing…", "info");
  const btn = document.getElementById("syncBtn");
  btn.disabled = true;
  try {
    const res = await apiFetch("/api/sync", { method: "POST" });
    log("Sync complete: " + (res.message || JSON.stringify(res)), "success");
    const dfs = res.dotfiles || [];
    dfs.forEach(d => log(`  ${d.name}: ${d.status}`, d.status === "missing" ? "warn" : "success"));
    await loadDotfiles();
  } catch (e) {
    log("Sync failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function applyAll() {
  log("Applying all dotfiles…", "info");
  const btn = document.getElementById("applyBtn");
  btn.disabled = true;
  try {
    const results = await apiFetch("/api/apply", { method: "POST", body: JSON.stringify({}) });
    results.forEach(r => {
      log(`  ${r.name}: ${r.status} — ${r.message}`, r.status === "applied" ? "success" : "error");
    });
    await loadDotfiles();
  } catch (e) {
    log("Apply failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function applyOne(name) {
  log(`Applying ${name}…`, "info");
  try {
    const results = await apiFetch("/api/apply", {
      method: "POST",
      body: JSON.stringify({ names: [name] }),
    });
    results.forEach(r => {
      log(`  ${r.name}: ${r.status} — ${r.message}`, r.status === "applied" ? "success" : "error");
    });
    await loadDotfiles();
  } catch (e) {
    log(`Apply ${name} failed: ` + e.message, "error");
  }
}

async function removeDotfile(name) {
  if (!confirm(`Remove "${name}"?`)) return;
  try {
    await apiFetch(`/api/dotfiles/${encodeURIComponent(name)}`, { method: "DELETE" });
    log(`Removed ${name}`, "warn");
    await loadDotfiles();
  } catch (e) {
    log(`Remove failed: ${e.message}`, "error");
  }
}

async function addDotfile(name, source, target) {
  try {
    await apiFetch("/api/dotfiles", {
      method: "POST",
      body: JSON.stringify({ name, source_path: source, target_path: target }),
    });
    log(`Added ${name}`, "success");
    await loadDotfiles();
  } catch (e) {
    log(`Add failed: ${e.message}`, "error");
    throw e;
  }
}

async function loadConfig() {
  try {
    const cfg = await apiFetch("/api/config");
    document.getElementById("cfgRemoteUrl").value = cfg.remote_url || "";
    document.getElementById("cfgLocalRepo").value = cfg.local_repo || "";
  } catch (e) {
    log("Config load failed: " + e.message, "error");
  }
}

async function saveConfig() {
  const remoteUrl = document.getElementById("cfgRemoteUrl").value.trim();
  const localRepo = document.getElementById("cfgLocalRepo").value.trim();
  try {
    if (remoteUrl) await apiFetch("/api/config", { method: "POST", body: JSON.stringify({ key: "remote_url", value: remoteUrl }) });
    if (localRepo) await apiFetch("/api/config", { method: "POST", body: JSON.stringify({ key: "local_repo", value: localRepo }) });
    log("Configuration saved.", "success");
  } catch (e) {
    log("Config save failed: " + e.message, "error");
    throw e;
  }
}

// ---------------------------------------------------------------------------
// Connection status
// ---------------------------------------------------------------------------

function setConnected(ok) {
  const badge = document.getElementById("statusBadge");
  if (ok) {
    badge.textContent = "● connected";
    badge.className = "badge badge-ok";
  } else {
    badge.textContent = "● offline";
    badge.className = "badge badge-error";
  }
}

// ---------------------------------------------------------------------------
// Event delegation for dynamic list buttons
// ---------------------------------------------------------------------------

document.getElementById("dotfilesList").addEventListener("click", (e) => {
  const removeBtn = e.target.closest(".remove-btn");
  if (removeBtn) {
    removeDotfile(removeBtn.dataset.name);
    return;
  }
  const applyBtn = e.target.closest(".apply-one-btn");
  if (applyBtn) {
    applyOne(applyBtn.dataset.name);
  }
});

// ---------------------------------------------------------------------------
// Button listeners
// ---------------------------------------------------------------------------

document.getElementById("refreshBtn").addEventListener("click", loadDotfiles);
document.getElementById("syncBtn").addEventListener("click", syncDotfiles);
document.getElementById("applyBtn").addEventListener("click", applyAll);

// Add modal
document.getElementById("addBtn").addEventListener("click", () => {
  document.getElementById("addModal").classList.remove("hidden");
});
document.getElementById("addCancelBtn").addEventListener("click", () => {
  document.getElementById("addModal").classList.add("hidden");
});
document.getElementById("addSubmitBtn").addEventListener("click", async () => {
  const name   = document.getElementById("addName").value.trim();
  const source = document.getElementById("addSource").value.trim();
  const target = document.getElementById("addTarget").value.trim();
  if (!name || !source || !target) { alert("All fields are required."); return; }
  try {
    await addDotfile(name, source, target);
    document.getElementById("addModal").classList.add("hidden");
    ["addName", "addSource", "addTarget"].forEach(id => { document.getElementById(id).value = ""; });
  } catch (_) { /* error already logged */ }
});

// Config modal
document.getElementById("configBtn").addEventListener("click", async () => {
  await loadConfig();
  document.getElementById("configModal").classList.remove("hidden");
});
document.getElementById("cfgCancelBtn").addEventListener("click", () => {
  document.getElementById("configModal").classList.add("hidden");
});
document.getElementById("cfgSaveBtn").addEventListener("click", async () => {
  try {
    await saveConfig();
    document.getElementById("configModal").classList.add("hidden");
  } catch (_) { /* error already logged */ }
});

// Close modals on overlay click
["addModal", "configModal"].forEach(id => {
  document.getElementById(id).addEventListener("click", (e) => {
    if (e.target === document.getElementById(id)) {
      document.getElementById(id).classList.add("hidden");
    }
  });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

loadDotfiles();
