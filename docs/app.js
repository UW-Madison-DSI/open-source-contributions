/* DSI Open Source Contributions — dashboard front end.
 * Loads the generated data.json and renders cards, charts, and tables.
 * No build step: plain ES modules-free JS + Chart.js from CDN. */

const REPO_URL = "https://github.com/moros2/open-source-contributions";
const MAX_CONTRIB_ROWS = 100;

const state = {
  data: null,
  memberSort: { key: "total", dir: "desc" },
};

init();

async function init() {
  // Wire repo links (works regardless of where this is hosted).
  for (const id of ["repo-link", "footer-repo"]) {
    const el = document.getElementById(id);
    if (el) el.href = REPO_URL + (id === "repo-link" ? "/blob/main/CONTRIBUTING.md" : "");
  }

  try {
    const res = await fetch("data.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();
  } catch (err) {
    document.querySelector("main").innerHTML =
      `<div class="panel empty">Could not load data.json (${err.message}).<br>
       Run <code>python scripts/build_data.py</code> to generate it.</div>`;
    return;
  }

  renderMeta();
  renderCards();
  renderProjectsChart();
  renderTimeChart();
  renderMembers();
  renderContributions();
  wireControls();
}

function renderMeta() {
  const d = state.data;
  const ts = d.generated_at ? new Date(d.generated_at) : null;
  document.getElementById("generated-at").textContent = ts
    ? ts.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "unknown";
}

function renderCards() {
  const s = state.data.summary;
  const cards = [
    { value: s.contributions, label: "Total contributions" },
    { value: s.external_contributions, label: "External contributions" },
    { value: s.projects, label: "Projects touched" },
    { value: s.active_members, label: "Active members" },
  ];
  document.getElementById("cards").innerHTML = cards
    .map((c) => `<div class="card"><div class="value">${fmt(c.value)}</div><div class="label">${c.label}</div></div>`)
    .join("");
}

function renderProjectsChart() {
  const top = (state.data.summary.top_projects || []).slice(0, 10);
  if (!top.length) return;
  new Chart(document.getElementById("projectsChart"), {
    type: "bar",
    data: {
      labels: top.map((t) => t[0]),
      datasets: [{ data: top.map((t) => t[1]), backgroundColor: "#c5050c", borderRadius: 4 }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderTimeChart() {
  const byMonth = state.data.summary.by_month || {};
  const labels = Object.keys(byMonth).sort();
  if (!labels.length) return;
  // Running cumulative total reads better than spiky monthly counts.
  let running = 0;
  const cumulative = labels.map((m) => (running += byMonth[m]));
  new Chart(document.getElementById("timeChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Cumulative",
          data: cumulative,
          borderColor: "#0479a8",
          backgroundColor: "rgba(4,121,168,0.12)",
          fill: true,
          tension: 0.25,
          pointRadius: 2,
        },
      ],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}

function renderMembers() {
  const tbody = document.querySelector("#membersTable tbody");
  const q = document.getElementById("memberSearch").value.trim().toLowerCase();
  const { key, dir } = state.memberSort;

  let rows = [...state.data.members];
  if (q) {
    rows = rows.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.github.toLowerCase().includes(q) ||
        (m.affiliation || "").toLowerCase().includes(q)
    );
  }
  rows.sort((a, b) => {
    const av = sortVal(a, key);
    const bv = sortVal(b, key);
    const cmp = typeof av === "string" ? av.localeCompare(bv) : av - bv;
    return dir === "asc" ? cmp : -cmp;
  });

  tbody.innerHTML = rows.length
    ? rows.map(memberRow).join("")
    : `<tr><td colspan="6" class="empty">No members match “${escapeHtml(q)}”.</td></tr>`;

  // Reflect sort indicators in the header.
  document.querySelectorAll("#membersTable th[data-sort]").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === key) th.classList.add(dir === "asc" ? "sorted-asc" : "sorted-desc");
  });
}

function sortVal(m, key) {
  if (key === "name") return m.name.toLowerCase();
  if (key === "role") return (m.role || "").toLowerCase();
  return m.stats[key] || 0;
}

function memberRow(m) {
  const ext = state.data.summary; // unused; keep signature simple
  const profile = `https://github.com/${encodeURIComponent(m.github)}`;
  const avatar = `${profile}.png?size=48`;
  return `<tr>
    <td>
      <div class="member-cell">
        <img class="avatar" src="${avatar}" alt="" loading="lazy" />
        <div>
          <a href="${profile}" target="_blank" rel="noopener">${escapeHtml(m.name)}</a>
          <div class="sub">@${escapeHtml(m.github)}${m.affiliation ? " · " + escapeHtml(m.affiliation) : ""}</div>
        </div>
      </div>
    </td>
    <td><span class="badge">${escapeHtml(m.role || "member")}</span></td>
    <td class="num">${fmt(m.stats.total)}</td>
    <td class="num">${fmt(m.stats.merged_prs)}</td>
    <td class="num">${fmt(m.stats.external)}</td>
    <td class="num">${fmt(m.stats.projects)}</td>
  </tr>`;
}

function renderContributions() {
  const tbody = document.querySelector("#contribTable tbody");
  const q = document.getElementById("contribSearch").value.trim().toLowerCase();
  let rows = state.data.contributions;
  if (q) {
    rows = rows.filter(
      (c) =>
        (c.project || "").toLowerCase().includes(q) ||
        (c.title || "").toLowerCase().includes(q) ||
        (c.member || "").toLowerCase().includes(q)
    );
  }
  const shown = rows.slice(0, MAX_CONTRIB_ROWS);
  tbody.innerHTML = shown.length
    ? shown.map(contribRow).join("")
    : `<tr><td colspan="5" class="empty">No contributions match “${escapeHtml(q)}”.</td></tr>`;

  const more = document.getElementById("contribMore");
  more.textContent =
    rows.length > MAX_CONTRIB_ROWS ? `Showing ${MAX_CONTRIB_ROWS} of ${rows.length} matching contributions.` : "";
}

function contribRow(c) {
  const type = (c.type || "other").toLowerCase();
  const proj = `https://github.com/${c.project}`;
  return `<tr>
    <td>${escapeHtml(c.date || "")}</td>
    <td><a href="https://github.com/${encodeURIComponent(c.member)}" target="_blank" rel="noopener">@${escapeHtml(c.member)}</a></td>
    <td>${c.source === "github" ? `<a href="${proj}" target="_blank" rel="noopener">${escapeHtml(c.project)}</a>` : escapeHtml(c.project)}</td>
    <td>${c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.title || "(untitled)")}</a>` : escapeHtml(c.title || "")}</td>
    <td><span class="badge ${type}">${escapeHtml(type)}</span></td>
  </tr>`;
}

function wireControls() {
  document.getElementById("memberSearch").addEventListener("input", renderMembers);
  document.getElementById("contribSearch").addEventListener("input", renderContributions);
  document.querySelectorAll("#membersTable th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.memberSort.key === key) {
        state.memberSort.dir = state.memberSort.dir === "asc" ? "desc" : "asc";
      } else {
        state.memberSort = { key, dir: key === "name" || key === "role" ? "asc" : "desc" };
      }
      renderMembers();
    });
  });
}

function fmt(n) {
  return (n ?? 0).toLocaleString();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
