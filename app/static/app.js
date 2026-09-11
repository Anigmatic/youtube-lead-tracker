const leadsBody = document.getElementById("leadsBody");
const channelInput = document.getElementById("channelInput");
const statusMsg = document.getElementById("statusMsg");
const settingsDialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");

const STATUS_OPTIONS = ["New", "Contacted", "Replied", "Not Interested", "Closed"];
const OUTREACH_OPTIONS = ["Email", "YouTube Comment", "Instagram DM", "Other"];

function renderRow(lead) {
  const tr = document.createElement("tr");
  tr.dataset.fit = lead.fit_assessment || "";
  tr.dataset.id = lead.id;

  const nameCell = `<a href="${lead.channel_url}" target="_blank">${lead.name || lead.channel_url}</a>`;
  const fitCell = `${lead.fit_assessment || ""} - ${lead.fit_reason || ""}`;

  tr.innerHTML = `
    <td>${lead.date || ""}</td>
    <td>${lead.language || ""}</td>
    <td>${nameCell}</td>
    <td>${lead.subscriber_count_display || ""}</td>
    <td>${lead.avg_views_display || ""}</td>
    <td>${lead.contact_info || ""}</td>
    <td class="fit">${fitCell}</td>
    <td class="status-cell"></td>
    <td class="outreach-cell"></td>
    <td class="notes-cell"><input type="text" value="${lead.notes || ""}"></td>
  `;

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

  return tr;
}

async function loadLeads() {
  const resp = await fetch("/api/leads");
  const leads = await resp.json();
  leadsBody.innerHTML = "";
  leads.forEach((lead) => leadsBody.appendChild(renderRow(lead)));
}

async function patchLead(id, fields) {
  await fetch(`/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

document.getElementById("submitBtn").addEventListener("click", async () => {
  const inputs = channelInput.value.split("\n").map((s) => s.trim()).filter(Boolean);
  if (!inputs.length) return;
  statusMsg.textContent = "Processing...";
  const resp = await fetch("/api/channels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  if (resp.ok) {
    channelInput.value = "";
    statusMsg.textContent = "Done.";
    await loadLeads();
  } else {
    statusMsg.textContent = "Error processing channels.";
  }
});

document.getElementById("exportBtn").addEventListener("click", () => {
  window.location.href = "/api/export?format=xlsx";
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
