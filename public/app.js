const $ = (id) => document.getElementById(id);

function fmt(v) {
  if (v === null || v === undefined) return "";
  return String(v);
}

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(v) {
  if (v === null || v === undefined || v === "") return "â€”";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  });
}


// ========== BCBS STATE FIELD TOGGLE ==========
function toggleBcbsState() {
  const payerInput = $("vobPayer");
  const bcbsField = $("vobBcbsStateField");
  const payerValue = payerInput.value.toLowerCase();
  
  if (payerValue.includes("bcbs") || payerValue.includes("blue") || payerValue.includes("anthem")) {
    bcbsField.style.display = "";
  } else {
    bcbsField.style.display = "none";
    $("vobBcbsState").value = ""; // Clear state when hidden
  }
}

function toggleReimbBcbsState() {
  const payerInput = $("reimbPayer");
  const bcbsField = $("reimbBcbsStateField");
  const payerValue = payerInput.value.toLowerCase();
  
  if (payerValue.includes("bcbs") || payerValue.includes("blue") || payerValue.includes("anthem")) {
    bcbsField.style.display = "";
  } else {
    bcbsField.style.display = "none";
    $("reimbBcbsState").value = ""; // Clear state when hidden
  }
}


function setHealth(ok, text) {
  const pill = $("healthPill");
  pill.textContent = text;
  pill.style.color = ok ? "rgba(23,195,178,0.95)" : "rgba(255,120,120,0.95)";
  pill.style.borderColor = ok ? "rgba(23,195,178,0.25)" : "rgba(255,120,120,0.25)";
}

async function health() {
  try {
    const r = await fetch("/api/health");
    await r.json();
    setHealth(true, "DB Connected");
  } catch (e) {
    setHealth(false, "DB Not Connected");
  }
}

// ========== TAB SWITCHING ==========
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;
    
    // Update tab buttons
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    
    // Update tab content
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    $(target + "Tab").classList.add("active");
  });
});

// ========== VOB FUNCTIONS ==========
function clearVOBUI() {
  $("vobResultsBody").innerHTML = "";
  $("vobResultsTable").style.display = "none";
  $("vobEmptyState").style.display = "block";
  $("vobCountText").textContent = "0 matches";
}

function renderVOB(rows) {
  clearVOBUI();
  $("vobCountText").textContent = `${rows.length} match${rows.length === 1 ? "" : "es"}`;

  if (!rows.length) return;

  $("vobEmptyState").style.display = "none";
  $("vobResultsTable").style.display = "table";

  const body = $("vobResultsBody");
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmt(r.id)}</td>
      <td>${fmt(r.created_at)}</td>
      <td>${fmt(r.first_name)} ${fmt(r.last_name)}</td>
      <td>${fmt(r.dob)}</td>
      <td>${fmt(r.payer_canonical || r.insurance_name_raw)}</td>
      <td>${fmt(r.in_out_network)}</td>
      <td>${fmt(r.self_or_commercial_funded)}</td>
      <td>${fmt(r.deductible_individual)}</td>
      <td>${fmt(r.oop_individual)}</td>
      <td>${fmt(r.facility_name)}</td>
    `;

    tr.addEventListener("click", () => {
      $("vobModalTitle").textContent =
        `${fmt(r.first_name)} ${fmt(r.last_name)}`.trim() || "Client Details";
      $("vobModalSubTitle").textContent =
        `${fmt(r.payer_canonical || r.insurance_name_raw)}  ${fmt(r.facility_name)}`.trim();
      $("vobModalBody").innerHTML = `<pre>${fmt(JSON.stringify(r, null, 2))}</pre>`;
      $("vobModalOverlay").style.display = "flex";
    });

    body.appendChild(tr);
  }
}

async function searchVOB() {
  const memberId = $("vobMemberId").value.trim();
  const dob = $("vobDob").value.trim();
  const payer = $("vobPayer").value.trim();
  const bcbsState = $("vobBcbsState").value.trim();
  const facility = $("vobFacility").value.trim();
  const employer = $("vobEmployer").value.trim();
  const firstName = $("vobFirstName").value.trim();
  const lastName = $("vobLastName").value.trim();
  const limit = $("vobLimit").value;

  const params = new URLSearchParams();
  if (memberId) params.set("memberId", memberId);
  if (dob) params.set("dob", dob);
  if (payer) params.set("payer", payer);
  if (bcbsState) params.set("bcbsState", bcbsState);
  if (facility) params.set("facility", facility);
  if (employer) params.set("employer", employer);
  if (firstName) params.set("firstName", firstName);
  if (lastName) params.set("lastName", lastName);
  params.set("limit", limit);

  if (!memberId && !dob && !payer && !bcbsState && !facility && !employer && !firstName && !lastName) {
    alert("Enter at least one filter.");
    return;
  }

  $("vobSearchBtn").textContent = "Searching...";
  $("vobSearchBtn").disabled = true;

  try {
    const r = await fetch(`/api/vob/search?${params.toString()}`);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Search failed");
    renderVOB(j.rows || []);
  } catch (e) {
    alert(e.message);
  } finally {
    $("vobSearchBtn").textContent = "Search";
    $("vobSearchBtn").disabled = false;
  }
}

function clearVOB() {
  $("vobMemberId").value = "";
  $("vobDob").value = "";
  $("vobPayer").value = "";
  $("vobBcbsState").value = "";
  $("vobBcbsStateField").style.display = "none";
  $("vobFacility").value = "";
  $("vobEmployer").value = "";
  $("vobFirstName").value = "";
  $("vobLastName").value = "";
  clearVOBUI();
}

function closeVOBModal() {
  $("vobModalOverlay").style.display = "none";
  $("vobModalBody").innerHTML = "";
  $("vobModalSubTitle").textContent = "";
  $("vobModalTitle").textContent = "Client Details";
}

// ========== REIMBURSEMENT FUNCTIONS ==========
let reimbActivePerson = null;

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }
}

function groupPeople(rows) {
  const map = new Map();
  for (const r of rows) {
    const key = `${r.member_id}||${r.payer_name || ""}||${r.last_name || ""}||${r.first_name || ""}`;
    if (!map.has(key)) {
      map.set(key, {
        member_id: r.member_id,
        payer_name: r.payer_name || "",
        last_name: r.last_name || "",
        first_name: r.first_name || "",
        locs: {}
      });
    }
    map.get(key).locs[r.loc] = { avg: r.avg_allowed, n: r.n_rows };
  }
  return [...map.values()];
}

function buildSummaryText(person) {
  const name = `${person.last_name}, ${person.first_name}`.replace(/^,\s*/, "").trim() || "(No name)";
  const locs = ["DTX", "RTC", "PHP", "IOP"];
  const lines = [];
  lines.push(`Reimbursement Summary`);
  lines.push(`Name: ${name}`);
  lines.push(`Member ID: ${person.member_id}`);
  if (person.payer_name) lines.push(`Payer: ${person.payer_name}`);
  lines.push("");
  for (const loc of locs) {
    const x = person.locs[loc];
    if (!x) lines.push(`${loc}:`);
    else lines.push(`${loc}: avg ${money(x.avg)} (${x.n} rows)`);
  }
  return lines.join("\n");
}

function locLine(person, loc) {
  const x = person.locs[loc];
  if (!x) return `<span><b>${loc}</b>: </span>`;
  return `<span><b>${loc}</b>: avg ${esc(money(x.avg))} (${esc(x.n)} rows)</span>`;
}

function showReimbModal() {
  $("reimbModalOverlay").style.display = "flex";
}

function closeReimbModal() {
  $("reimbModalOverlay").style.display = "none";
  $("reimbModalSubTitle").textContent = "";
  $("reimbModalTitle").textContent = "Client";
  $("reimbClientView").innerHTML = "";
  $("reimbLocView").innerHTML = "";
  $("reimbClientView").style.display = "";
  $("reimbLocView").style.display = "none";
  $("reimbModalBackBtn").style.display = "none";
  reimbActivePerson = null;
}

function showReimbClientView(person) {
  reimbActivePerson = person;
  $("reimbModalBackBtn").style.display = "none";
  $("reimbClientView").style.display = "";
  $("reimbLocView").style.display = "none";

  const name = `${person.last_name}, ${person.first_name}`.replace(/^,\s*/, "").trim() || "(No name)";
  $("reimbModalTitle").textContent = "Client";
  $("reimbModalSubTitle").textContent = `${name} • ${person.member_id} • ${person.payer_name || ""}`.trim();

  const summaryText = buildSummaryText(person);

  $("reimbClientView").innerHTML = `
    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px;">
      <button type="button" class="locBtn" data-loc="DTX">DTX</button>
      <button type="button" class="locBtn" data-loc="RTC">RTC</button>
      <button type="button" class="locBtn" data-loc="PHP">PHP</button>
      <button type="button" class="locBtn" data-loc="IOP">IOP</button>
    </div>
    <div style="margin-top:10px; display:flex; gap:14px; flex-wrap:wrap;">
      ${locLine(person, "DTX")}
      ${locLine(person, "RTC")}
      ${locLine(person, "PHP")}
      ${locLine(person, "IOP")}
    </div>
    <div style="margin-top:14px;">
      <pre style="white-space:pre-wrap; margin:0;">${esc(summaryText)}</pre>
    </div>
  `;

  $("reimbClientView").querySelectorAll("button[data-loc]").forEach((btn) => {
    btn.addEventListener("click", () => showReimbLocView(person, btn.dataset.loc));
  });

  showReimbModal();
}

async function showReimbLocView(person, loc) {
  reimbActivePerson = person;
  $("reimbModalBackBtn").style.display = "";
  $("reimbClientView").style.display = "none";
  $("reimbLocView").style.display = "";

  $("reimbModalTitle").textContent = `Daily rows: ${loc}`;
  $("reimbModalSubTitle").textContent = person.member_id;
  $("reimbLocView").innerHTML = `<div class="msg">Loadingâ€¦</div>`;
  showReimbModal();

  try {
    const qs = new URLSearchParams({ memberId: person.member_id, loc, limit: "500" });
    const res = await fetch(`/api/reimb/rows?${qs.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load rows");

    const rows = data.rows || [];
    $("reimbLocView").innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>From</th>
            <th>To</th>
            <th>Payer</th>
            <th>Allowed</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td>${esc(r.service_date_from)}</td>
              <td>${esc(r.service_date_to)}</td>
              <td>${esc(r.payer_name)}</td>
              <td>${esc(money(r.allowed_amount))}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {
    $("reimbLocView").innerHTML = `<div class="msg">${esc(e.message)}</div>`;
  }
}

function renderReimbPeople(people) {
  const host = $("reimbPeopleList");
  host.innerHTML = "";
  $("reimbEmptyState").style.display = "none";

  for (const p of people) {
    const el = document.createElement("div");
    el.className = "person";
    const name = `${p.last_name}, ${p.first_name}`.replace(/^,\s*/, "").trim() || "(No name)";

    el.innerHTML = `
      <div class="name" style="cursor:pointer;">${esc(name)} • ${esc(p.member_id)}</div>
      <div class="msg">${esc(p.payer_name)}</div>
      <div class="row" style="margin-top:10px;">
        <button class="secondary" data-copy="1" type="button">Copy summary</button>
        <div class="msg" data-copymsg=""></div>
      </div>
      <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
        <button type="button" class="locBtn" data-loc="DTX">DTX</button>
        <button type="button" class="locBtn" data-loc="RTC">RTC</button>
        <button type="button" class="locBtn" data-loc="PHP">PHP</button>
        <button type="button" class="locBtn" data-loc="IOP">IOP</button>
      </div>
      <div style="margin-top:10px; display:flex; gap:14px; flex-wrap:wrap;">
        ${locLine(p, "DTX")}
        ${locLine(p, "RTC")}
        ${locLine(p, "PHP")}
        ${locLine(p, "IOP")}
      </div>
    `;

    el.querySelector(".name").addEventListener("click", () => showReimbClientView(p));

    const copyBtn = el.querySelector('button[data-copy="1"]');
    const copyMsg = el.querySelector('[data-copymsg]');
    copyBtn.addEventListener("click", async () => {
      const text = buildSummaryText(p);
      const ok = await copyText(text);
      copyMsg.textContent = ok ? "Copied." : "Copy failed.";
      setTimeout(() => (copyMsg.textContent = ""), 1200);
    });

    el.querySelectorAll("button[data-loc]").forEach((btn) => {
      btn.addEventListener("click", () => showReimbLocView(p, btn.dataset.loc));
    });

    host.appendChild(el);
  }
}

async function loadReimbAverages() {
  $("reimbMsg").textContent = "";
  $("reimbPeopleList").innerHTML = "";
  $("reimbEmptyState").style.display = "none";
  $("reimbCountText").textContent = "0 matches";

  const firstName = $("reimbFirstName").value.trim();
  const lastName = $("reimbLastName").value.trim();
  const prefix = $("reimbPrefix").value.trim();
  const payer = $("reimbPayer").value.trim();
  const bcbsState = $("reimbBcbsState").value.trim();
  const employer = $("reimbEmployer").value.trim();

  const qs = new URLSearchParams();
  if (firstName) qs.set("firstName", firstName);
  if (lastName) qs.set("lastName", lastName);
  if (prefix) qs.set("prefix", prefix);
  if (payer) qs.set("payer", payer);
  if (bcbsState) qs.set("bcbsState", bcbsState);
  if (employer) qs.set("employer", employer);

  if (!qs.toString()) {
    $("reimbEmptyState").style.display = "";
    $("reimbMsg").textContent = "Provide at least one filter.";
    return;
  }

  try {
    const res = await fetch(`/api/reimb/summary?${qs.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load summary");

    const people = groupPeople(data.rows || []);
    $("reimbCountText").textContent = `${people.length} matches`;

    if (!people.length) {
      $("reimbEmptyState").style.display = "";
      $("reimbMsg").textContent = "No reimbursement data found.";
      return;
    }

    renderReimbPeople(people);
  } catch (e) {
    $("reimbEmptyState").style.display = "";
    $("reimbMsg").textContent = e.message;
  }
}

function clearReimb() {
  $("reimbFirstName").value = "";
  $("reimbLastName").value = "";
  $("reimbPrefix").value = "";
  $("reimbPayer").value = "";
  $("reimbBcbsState").value = "";
  $("reimbBcbsStateField").style.display = "none";
  $("reimbEmployer").value = "";
  $("reimbMsg").textContent = "";
  $("reimbCountText").textContent = "0 matches";
  $("reimbPeopleList").innerHTML = "";
  $("reimbEmptyState").style.display = "";
}

// ========== INITIALIZATION ==========
window.addEventListener("DOMContentLoaded", () => {
  // VOB events
  $("vobSearchBtn").addEventListener("click", searchVOB);
  $("vobClearBtn").addEventListener("click", clearVOB);
  $("vobPayer").addEventListener("input", toggleBcbsState);
  $("vobModalCloseBtn").addEventListener("click", closeVOBModal);
  $("vobModalOverlay").addEventListener("click", (e) => {
    if (e.target === $("vobModalOverlay")) closeVOBModal();
  });

  // Reimbursement events
  $("reimbGoBtn").addEventListener("click", loadReimbAverages);
  $("reimbClearBtn").addEventListener("click", clearReimb);
  $("reimbPayer").addEventListener("input", toggleReimbBcbsState);
  $("reimbModalBackBtn").addEventListener("click", () => {
    if (reimbActivePerson) showReimbClientView(reimbActivePerson);
  });
  $("reimbModalCloseBtn").addEventListener("click", closeReimbModal);
  $("reimbModalOverlay").addEventListener("click", (e) => {
    if (e.target === $("reimbModalOverlay")) closeReimbModal();
  });

  // Escape key for modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if ($("vobModalOverlay").style.display !== "none") closeVOBModal();
      if ($("reimbModalOverlay").style.display !== "none") closeReimbModal();
    }
  });

  health();
  clearVOBUI();
  clearReimb();
});