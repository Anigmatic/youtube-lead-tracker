const leadsBody = document.getElementById("leadsBody");
const channelInput = document.getElementById("channelInput");
const statusMsg = document.getElementById("statusMsg");
const settingsDialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");
const submitBtn = document.getElementById("submitBtn");

const STATUS_OPTIONS = ["New", "Contacted", "Replied", "Not Interested", "Closed"];
const OUTREACH_OPTIONS = ["Email", "YouTube Comment", "Instagram DM", "Other"];
const LANGUAGE_OPTIONS = [
  "English", "Unknown", "Spanish", "Portuguese", "French", "German",
  "Hindi", "Arabic", "Japanese", "Korean", "Chinese", "Other",
];
const EMPTY_TABLE_COLUMNS = 12;

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  // div.innerHTML (per the HTML fragment serialization spec) only escapes
  // &, <, > (and nbsp) on a text node — it does NOT escape quote
  // characters. Since several call sites below interpolate into a
  // double-quoted HTML attribute (value="${...}"), quotes must be escaped
  // explicitly or a value containing `"` could break out of the attribute.
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderEmptyRow() {
  const tr = document.createElement("tr");
  tr.className = "empty-row";
  const td = document.createElement("td");
  td.colSpan = EMPTY_TABLE_COLUMNS;
  td.textContent = "No leads yet — paste a channel URL or @handle above to get started.";
  tr.appendChild(td);
  return tr;
}

function renderRow(lead) {
  const tr = document.createElement("tr");
  tr.dataset.fit = lead.fit_assessment || "";
  tr.dataset.id = lead.id;

  const nameCell = `<a href="${escapeHtml(lead.channel_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(lead.name || lead.channel_url)}</a>`;
  const contactValue = lead.contact_info || "";
  const linksValue = lead.links || "";

  tr.innerHTML = `
    <td>${escapeHtml(lead.date || "")}</td>
    <td class="language-cell"></td>
    <td class="name-cell">${nameCell}</td>
    <td>${escapeHtml(lead.subscriber_count_display || "")}</td>
    <td>${escapeHtml(lead.avg_views_display || "")}</td>
    <td class="truncate" title="${escapeHtml(contactValue)}">${escapeHtml(contactValue)}</td>
    <td class="truncate" title="${escapeHtml(linksValue)}">${escapeHtml(linksValue)}</td>
    <td class="fit-cell">
      <span class="fit-badge" data-fit="${escapeHtml(lead.fit_assessment || "")}">${escapeHtml(lead.fit_assessment || "Unscored")}</span>
      <span class="fit-reason">${escapeHtml(lead.fit_reason || "")}</span>
    </td>
    <td class="status-cell"></td>
    <td class="outreach-cell"></td>
    <td class="notes-cell"><input type="text" placeholder="Add a note…" value="${escapeHtml(lead.notes || "")}"></td>
    <td class="delete-cell"></td>
  `;

  const languageSelect = document.createElement("select");
  LANGUAGE_OPTIONS.forEach((opt) => {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    if (opt === lead.language) o.selected = true;
    languageSelect.appendChild(o);
  });
  languageSelect.addEventListener("change", () => patchLead(lead.id, { language: languageSelect.value }));
  tr.querySelector(".language-cell").appendChild(languageSelect);

  const statusSelect = document.createElement("select");
  STATUS_OPTIONS.forEach((opt) => {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    if (opt === lead.status) o.selected = true;
    statusSelect.appendChild(o);
  });
  statusSelect.addEventListener("change", () => patchLead(lead.id, { status: statusSelect.value }));
  tr.querySelector(".status-cell").appendChild(statusSelect);

  const outreachSelect = document.createElement("select");
  OUTREACH_OPTIONS.forEach((opt) => {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    if (opt === lead.outreach_method) o.selected = true;
    outreachSelect.appendChild(o);
  });
  outreachSelect.addEventListener("change", () => patchLead(lead.id, { outreach_method: outreachSelect.value }));
  tr.querySelector(".outreach-cell").appendChild(outreachSelect);

  const notesInput = tr.querySelector(".notes-cell input");
  notesInput.addEventListener("change", () => patchLead(lead.id, { notes: notesInput.value }));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "row-delete-btn danger-ghost";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => deleteLead(lead.id, lead.name || lead.channel_url));
  tr.querySelector(".delete-cell").appendChild(deleteBtn);

  return tr;
}

async function loadLeads() {
  const resp = await fetch("/api/leads");
  const leads = await resp.json();
  leadsBody.innerHTML = "";
  if (!leads.length) {
    leadsBody.appendChild(renderEmptyRow());
    return;
  }
  leads.forEach((lead) => leadsBody.appendChild(renderRow(lead)));
}

async function patchLead(id, fields) {
  await fetch(`/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

async function deleteLead(id, label) {
  if (!window.confirm(`Delete "${label}" from the tracker? This cannot be undone.`)) return;
  await fetch(`/api/leads/${id}`, { method: "DELETE" });
  await loadLeads();
}

function setStatus(html, isError) {
  statusMsg.innerHTML = html;
  statusMsg.classList.toggle("is-error", Boolean(isError));
}

submitBtn.addEventListener("click", async () => {
  const inputs = channelInput.value.split("\n").map((s) => s.trim()).filter(Boolean);
  if (!inputs.length) return;
  submitBtn.disabled = true;
  setStatus(`<span class="spinner"></span> Processing ${inputs.length} channel${inputs.length > 1 ? "s" : ""}…`, false);
  try {
    const resp = await fetch("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs }),
    });
    if (resp.ok) {
      const body = await resp.json();
      channelInput.value = "";
      const skippedCount = (body.skipped || []).length;
      if (skippedCount) {
        const names = body.skipped.map((s) => s.name || s.channel_url).join(", ");
        setStatus(`Done. Skipped ${skippedCount} outside your subscriber range: ${escapeHtml(names)}.`, false);
      } else {
        setStatus("Done.", false);
      }
      await loadLeads();
    } else {
      setStatus("Error processing channels.", true);
    }
  } catch (err) {
    setStatus("Error processing channels.", true);
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("exportBtn").addEventListener("click", () => {
  window.location.href = "/api/export?format=xlsx";
});

document.getElementById("clearAllBtn").addEventListener("click", async () => {
  const leads = await (await fetch("/api/leads")).json();
  if (!leads.length) return;
  if (!window.confirm(`Delete all ${leads.length} lead(s) from the tracker? This cannot be undone.`)) return;
  await fetch("/api/leads", { method: "DELETE" });
  await loadLeads();
});

document.getElementById("settingsBtn").addEventListener("click", async () => {
  const resp = await fetch("/api/settings");
  const settings = await resp.json();
  for (const [key, value] of Object.entries(settings)) {
    const field = settingsForm.elements[key];
    if (!field) continue;
    field.value = Array.isArray(value) ? value.join(", ") : value;
  }
  settingsDialog.showModal();
});

document.getElementById("closeSettingsBtn").addEventListener("click", () => settingsDialog.close());

settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(settingsForm);
  const payload = Object.fromEntries(formData.entries());
  payload.niche_keywords = payload.niche_keywords.split(",").map((s) => s.trim()).filter(Boolean);
  payload.target_sub_min = Number(payload.target_sub_min) || 0;
  payload.target_sub_max = Number(payload.target_sub_max) || 10000000;
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  settingsDialog.close();
});

loadLeads();
