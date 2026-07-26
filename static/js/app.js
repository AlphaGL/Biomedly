/* Biomedly frontend */

/** Inline ECG-trace loading indicator — used wherever the app is waiting
 * on a request, instead of a generic chat-app spinner. */
const ECG_TRACE_SVG =
  '<svg class="ecg-trace" viewBox="0 0 100 40" aria-hidden="true">' +
  '<path d="M0,20 H30 L36,6 L42,34 L48,14 L54,20 H100" /></svg>';

/** Sprite-icon markup — used instead of emoji throughout the UI. */
function icon(name, extraClass) {
  return `<svg class="icon${extraClass ? " " + extraClass : ""}"><use href="#icon-${name}"></use></svg>`;
}

/* ---------- tiny markdown renderer (headings, bold, lists, code) ---------- */
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(s) {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function renderMarkdown(md) {
  const lines = escapeHtml(md).split(/\r?\n/);
  let html = "", inList = false, inOl = false, inCode = false;

  const closeLists = () => {
    if (inList) { html += "</ul>"; inList = false; }
    if (inOl) { html += "</ol>"; inOl = false; }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      closeLists();
      html += inCode ? "</code></pre>" : "<pre><code>";
      inCode = !inCode;
      continue;
    }
    if (inCode) { html += line + "\n"; continue; }

    const img = line.match(/^!\[([^\]]*)\]\((https?:[^)\s]+)\)\s*$/);
    if (img) {
      closeLists();
      html += `<figure class="answer-figure"><img src="${img[2]}" alt="${img[1]}" loading="lazy" onerror="this.closest('figure').remove()"></figure>`;
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) {
      closeLists();
      const lvl = Math.min(h[1].length + 2, 5);
      html += `<h${lvl}>${renderInline(h[2])}</h${lvl}>`;
      continue;
    }
    const ul = line.match(/^\s*[-*]\s+(.*)/);
    if (ul) {
      if (inOl) { html += "</ol>"; inOl = false; }
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${renderInline(ul[1])}</li>`;
      continue;
    }
    const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (ol) {
      if (inList) { html += "</ul>"; inList = false; }
      if (!inOl) { html += "<ol>"; inOl = true; }
      html += `<li>${renderInline(ol[1])}</li>`;
      continue;
    }
    if (line.trim() === "") { closeLists(); continue; }
    closeLists();
    html += `<p>${renderInline(line)}</p>`;
  }
  closeLists();
  if (inCode) html += "</code></pre>";
  return html;
}

/* ---------- helpers ---------- */
function getCookie(name) {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

function setStatus(el, msg, kind) {
  el.hidden = !msg;
  el.className = "status" + (kind ? " " + kind : "");
  if (kind === "loading" && msg) {
    // Safe: msg is always an app-authored string in loading calls, never
    // user/server content, so the small ECG-trace markup can go via innerHTML.
    el.innerHTML = ECG_TRACE_SVG + "<span>" + msg + "</span>";
  } else {
    el.textContent = msg || ""; // error/plain text — never render as HTML
  }
}

/* ---------- View tabs (Assistant / Research) ---------- */
const viewTabs = document.getElementById("view-tabs");
function showTab(panelId) {
  if (!viewTabs) return;
  document.querySelectorAll(".workbench > .panel").forEach(p => {
    p.classList.toggle("hidden", p.id !== panelId);
  });
  viewTabs.querySelectorAll(".view-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.tab === panelId);
  });
  try { sessionStorage.setItem("biomedly-tab", panelId); } catch (e) {}
}
if (viewTabs) {
  viewTabs.addEventListener("click", e => {
    const tab = e.target.closest(".view-tab");
    if (tab) showTab(tab.dataset.tab);
  });
  // Restore the last-used tab within this browser session
  try {
    const saved = sessionStorage.getItem("biomedly-tab");
    if (saved && document.getElementById(saved)) showTab(saved);
  } catch (e) {}
}

// An asset page's "Ask the Assistant about this" link arrives as
// ?equipment_name=... — prefill the field and land on the Assistant tab.
(function prefillFromQueryString() {
  const params = new URLSearchParams(window.location.search);
  const eqName = params.get("equipment_name");
  const eqField = document.getElementById("equipment-name");
  if (eqName && eqField) {
    eqField.value = eqName;
    if (typeof showTab === "function") showTab("ask-panel");
    document.getElementById("question")?.focus();
  }
})();

/* ---------- Snap & Ask ---------- */
const MAX_PHOTOS = 4;
const MAX_VIDEOS = 1;
const MAX_VIDEO_BYTES = 18 * 1024 * 1024;

const form = document.getElementById("analyze-form");
if (form) {
  const panel = document.getElementById("ask-panel");
  const input = document.getElementById("media-input");
  const attachBtn = document.getElementById("attach-btn");
  const thumbs = document.getElementById("dz-thumbs");
  const statusEl = document.getElementById("analyze-status");
  const btn = document.getElementById("analyze-btn");
  const questionEl = document.getElementById("question");

  /** Selected media (photos + video), kept in memory only. */
  let attachments = [];

  function renderThumbs() {
    thumbs.innerHTML = "";
    attachments.forEach((a, i) => {
      const wrap = document.createElement("div");
      wrap.className = "thumb";
      if (a.kind === "video") {
        const vid = document.createElement("video");
        vid.src = a.url;
        vid.muted = true;
        wrap.appendChild(vid);
        const tag = document.createElement("span");
        tag.className = "thumb-tag";
        tag.innerHTML = '<svg class="icon icon-sm"><use href="#icon-video"></use></svg> video';
        wrap.appendChild(tag);
      } else {
        const img = document.createElement("img");
        img.src = a.url;
        img.alt = a.file.name;
        wrap.appendChild(img);
      }
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "thumb-remove";
      rm.title = "Remove";
      rm.innerHTML = '<svg class="icon"><use href="#icon-x"></use></svg>';
      rm.addEventListener("click", e => {
        e.stopPropagation();
        URL.revokeObjectURL(a.url);
        attachments.splice(i, 1);
        renderThumbs();
      });
      wrap.appendChild(rm);
      thumbs.appendChild(wrap);
    });
  }

  function addFiles(fileList) {
    for (const file of fileList) {
      const isVideo = file.type.startsWith("video/");
      const isImage = file.type.startsWith("image/");
      if (!isVideo && !isImage) continue;
      if (isVideo) {
        if (attachments.filter(a => a.kind === "video").length >= MAX_VIDEOS) {
          setStatus(statusEl, "Only one video per question.", "error");
          continue;
        }
        if (file.size > MAX_VIDEO_BYTES) {
          setStatus(statusEl, "Video too large — keep it under 18 MB (~30-60 s).", "error");
          continue;
        }
      } else if (attachments.filter(a => a.kind === "image").length >= MAX_PHOTOS) {
        setStatus(statusEl, `Maximum ${MAX_PHOTOS} photos.`, "error");
        continue;
      }
      attachments.push({
        file,
        url: URL.createObjectURL(file),
        kind: isVideo ? "video" : "image",
      });
    }
    renderThumbs();
  }

  attachBtn.addEventListener("click", () => input.click());
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  panel.addEventListener("dragover", e => { e.preventDefault(); panel.classList.add("drag"); });
  panel.addEventListener("dragleave", e => {
    if (!panel.contains(e.relatedTarget)) panel.classList.remove("drag");
  });
  panel.addEventListener("drop", e => {
    e.preventDefault();
    panel.classList.remove("drag");
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });

  // Enter sends; Shift+Enter makes a newline.
  questionEl.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // The equipment-name field is a plain <input>, which submits the form
  // natively on Enter (bypassing the handler above) with an EMPTY question —
  // that's the "it sent nothing" bug. Redirect Enter there into the message
  // box instead, so Enter always means "send what's in the message box."
  const equipmentNameEl = document.getElementById("equipment-name");
  if (equipmentNameEl) {
    equipmentNameEl.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (questionEl.value.trim()) {
          form.requestSubmit();
        } else {
          questionEl.focus();
        }
      }
    });
  }

  /* --- conversation thread --- */
  const thread = document.getElementById("thread");
  const newSessionBtn = document.getElementById("new-session");
  let chatHistory = [];  // [{role: "user"|"assistant", text: raw}]

  function addBubble(role, html) {
    const el = document.createElement("div");
    el.className = "bubble " + role;
    el.innerHTML = html;
    thread.appendChild(el);
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    return el;
  }

  function addFollowups(questions) {
    if (!questions || !questions.length) return;
    const wrap = document.createElement("div");
    wrap.className = "followups";
    wrap.innerHTML = "<span class='field-label'>Ask next:</span>";
    for (const q of questions) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip followup";
      b.textContent = q;
      b.addEventListener("click", () => {
        document.getElementById("question").value = q;
        form.requestSubmit();
      });
      wrap.appendChild(b);
    }
    thread.appendChild(wrap);
  }

  newSessionBtn.addEventListener("click", () => {
    chatHistory = [];
    thread.innerHTML = `<div class="bubble assistant welcome">
      New conversation started. Attach photos or a short video and ask away.</div>`;
    newSessionBtn.hidden = true;
    setStatus(statusEl, "");
    // Full reset — a new conversation shouldn't inherit the last one's
    // equipment/mode/attachments.
    equipmentNameEl.value = "";
    questionEl.value = "";
    attachments.forEach(a => URL.revokeObjectURL(a.url));
    attachments = [];
    renderThumbs();
  });

  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (btn.disabled) return;
    const question = questionEl.value.trim();
    btn.disabled = true;
    thread.querySelectorAll(".followups").forEach(el => el.remove());
    const welcome = thread.querySelector(".welcome");
    if (welcome) welcome.remove();

    const nImg = attachments.filter(a => a.kind === "image").length;
    const nVid = attachments.filter(a => a.kind === "video").length;
    let note = "";
    if (nImg) note += ` <span class="badge">${nImg} photo${nImg > 1 ? "s" : ""}</span>`;
    if (nVid) note += ` <span class="badge">video</span>`;
    addBubble("user", escapeHtml(question || "(standard answer for the selected mode)") + note);
    const loadingText = chatHistory.length
      ? "Analyzing…"
      : (nVid ? "Reading video + analyzing — this can take 1-2 minutes."
              : "Checking reference data + analyzing — up to a minute.");
    const pending = addBubble("assistant loading-bubble", ECG_TRACE_SVG + "<span>" + loadingText + "</span>");

    const data = new FormData(form);
    data.set("history", JSON.stringify(chatHistory));
    for (const a of attachments) {
      data.append(a.kind === "video" ? "videos" : "images", a.file, a.file.name);
    }

    try {
      const res = await fetch("/api/analyze/", {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
        body: data,
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Request failed");
      pending.className = "bubble assistant answer";
      pending.innerHTML = renderMarkdown(json.answer);
      chatHistory.push({ role: "user", text: question || "(standard answer)" });
      chatHistory.push({ role: "assistant", text: json.answer });
      addFollowups(json.followups);
      questionEl.value = "";
      newSessionBtn.hidden = false;
      setStatus(statusEl, "");
    } catch (err) {
      pending.remove();
      setStatus(statusEl, "Error: " + err.message, "error");
    } finally {
      btn.disabled = false;
    }
  });
}

/* ---------- Research search ---------- */
const searchForm = document.getElementById("search-form");
if (searchForm) {
  const results = document.getElementById("search-results");
  const statusEl = document.getElementById("search-status");
  let lastSearchHtml = "";

  function askAssistant(name) {
    showTab("ask-panel");
    const eq = document.getElementById("equipment-name");
    const q = document.getElementById("question");
    if (eq) eq.value = name;
    if (q) {
      q.value = `Tell me about the ${name}: what it is, its components, and common faults.`;
      q.focus();
    }
    document.getElementById("ask-panel").scrollIntoView({ behavior: "smooth" });
  }

  // Event delegation for everything rendered inside the results area
  results.addEventListener("click", e => {
    const ask = e.target.closest("[data-ask]");
    if (ask) { askAssistant(ask.dataset.ask); return; }
    const back = e.target.closest("[data-back]");
    if (back) { results.innerHTML = lastSearchHtml; return; }
    const dev = e.target.closest("[data-device]");
    if (dev && !e.target.closest("a")) { loadDevice(dev.dataset.device); return; }
    const gd = e.target.closest("[data-guide]");
    if (gd && !e.target.closest("a")) { loadGuide(gd.dataset.guide); return; }
    const fm = e.target.closest("[data-find-manual]");
    if (fm) { loadManualsInto(fm, fm.dataset.findManual); return; }
  });

  /** Replaces a "Find manual" button in place with the results it found. */
  async function loadManualsInto(button, model) {
    button.disabled = true;
    button.innerHTML = icon("search") + " Searching the web…";
    try {
      const res = await fetch("/api/manuals/?model=" + encodeURIComponent(model));
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Search failed");
      const wrap = document.createElement("div");
      wrap.className = "manual-results";
      if (json.manuals.length) {
        wrap.innerHTML = `<h4>${icon("document")} Manuals found for "${escapeHtml(json.model)}"</h4><div class="doc-list">` +
          json.manuals.map(m => `<a class="doc-row" href="${m.url}" target="_blank" rel="noopener">
            <span class="doc-icon">${icon("document")}</span>
            <span class="doc-title">${escapeHtml(m.title)}</span>
            <span class="badge">${escapeHtml(m.source)}</span>
          </a>`).join("") +
          `</div><p class="muted">Not the right one? <a href="${json.google_url}" target="_blank" rel="noopener">Search Google directly${icon("external-link", "icon-sm")}</a></p>`;
      } else {
        wrap.innerHTML = `<p class="muted">No manual auto-found for "${escapeHtml(json.model)}" yet.
          <a href="${json.google_url}" target="_blank" rel="noopener">Search Google directly${icon("external-link", "icon-sm")}</a></p>`;
      }
      button.replaceWith(wrap);
    } catch (err) {
      button.disabled = false;
      button.textContent = "Search failed — click to retry";
    }
  }

  async function loadDevice(title) {
    setStatus(statusEl, "Loading device page from iFixit…", "loading");
    try {
      const res = await fetch("/api/device/?title=" + encodeURIComponent(title));
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to load device");
      setStatus(statusEl, "");
      results.innerHTML = renderDevice(json.device);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setStatus(statusEl, "Error: " + err.message, "error");
    }
  }

  async function loadGuide(guideid) {
    setStatus(statusEl, "Loading full repair guide from iFixit…", "loading");
    try {
      const res = await fetch("/api/guide/?id=" + encodeURIComponent(guideid));
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to load guide");
      setStatus(statusEl, "");
      results.innerHTML = renderGuide(json.guide);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setStatus(statusEl, "Error: " + err.message, "error");
    }
  }

  function renderDevice(d) {
    let html = `<button type="button" class="btn-ghost" data-back>${icon("arrow-left", "icon-sm")} Back to results</button>
      <div class="device-detail">
        <div class="device-head">
          ${d.image ? `<img src="${d.image}" alt="">` : ""}
          <div>
            <h3>${escapeHtml(d.title)}</h3>
            <p class="muted">${escapeHtml(d.summary)}</p>
            <button type="button" class="chip followup" data-ask="${escapeHtml(d.title)}">${icon("chat")} Ask the Assistant about this</button>
            <a class="chip" href="${d.url}" target="_blank" rel="noopener">Open on iFixit${icon("external-link", "icon-sm")}</a>
          </div>
        </div>`;
    if (d.flags && d.flags.length) {
      html += "<p>" + d.flags.map(f => `<span class="badge">${escapeHtml(f)}</span>`).join(" ") + "</p>";
    }
    if (d.contents) {
      html += `<div class="wiki-content">${d.contents}</div>`;
    }
    if (d.tools && d.tools.length) {
      html += "<h4>Common tools</h4><ul>" + d.tools.map(t => `<li>${escapeHtml(t)}</li>`).join("") + "</ul>";
    }
    if (d.documents && d.documents.length) {
      html += `<h4>${icon("document")} Service documents &amp; manuals (${d.documents.length})</h4><div class="doc-list">`;
      for (const doc of d.documents) {
        html += `<a class="doc-row" href="${doc.url}" target="_blank" rel="noopener">
          <span class="doc-icon">${icon("document")}</span>
          <span class="doc-title">${escapeHtml(doc.title)}</span>
          <span class="badge">${doc.pages ? doc.pages + " pages" : "PDF"}${doc.size_mb ? " · " + doc.size_mb + " MB" : ""}</span>
        </a>`;
      }
      html += `</div><button type="button" class="chip followup" data-find-manual="${escapeHtml(d.title)}">${icon("search")} Search the web for more manuals</button>`;
    } else {
      html += `<h4>${icon("document")} Service documents &amp; manuals</h4>
        <p class="muted">iFixit has none for this device.</p>
        <button type="button" class="chip followup" data-find-manual="${escapeHtml(d.title)}">${icon("search")} Search the web for a manual</button>`;
    }
    if (d.guides && d.guides.length) {
      html += `<h4>${icon("wrench")} Repair &amp; maintenance guides (${d.guides.length}) — click to read here</h4><div class="card-grid">`;
      for (const g of d.guides) {
        html += `<div class="card card-link" data-guide="${g.guideid}">
          ${g.image ? `<img src="${g.image}" alt="" loading="lazy">` : ""}
          <strong>${escapeHtml(g.title)}</strong>
          <p>${g.difficulty ? `<span class="badge">${escapeHtml(g.difficulty)}</span>` : ""}
             ${g.time ? `<span class="badge">${icon("clock", "icon-sm")} ${escapeHtml(g.time)}</span>` : ""}</p>
        </div>`;
      }
      html += "</div>";
    }
    if (d.children && d.children.length) {
      html += `<h4>${icon("box")} Models in this family (${d.children.length}) — click to open</h4><div class="card-grid">`;
      for (const c of d.children) {
        html += `<div class="card card-link" data-device="${escapeHtml(c.title)}">
          ${c.image ? `<img src="${c.image}" alt="" loading="lazy">` : ""}
          <strong>${escapeHtml(c.title)}</strong>
        </div>`;
      }
      html += "</div>";
    }
    if (!(d.guides && d.guides.length) && !(d.documents && d.documents.length) && !(d.children && d.children.length)) {
      html += `<p class="muted">No guides or documents on iFixit for this device yet — try
        <button type="button" class="chip followup" data-ask="${escapeHtml(d.title)}">asking the Assistant</button>.</p>`;
    }
    html += `<p class="attribution">Content from <a href="${d.url}" target="_blank" rel="noopener">iFixit</a>, licensed CC BY-NC-SA.</p></div>`;
    return html;
  }

  function renderGuide(g) {
    let html = `<button type="button" class="btn-ghost" data-back>${icon("arrow-left", "icon-sm")} Back to results</button>
      <div class="guide-detail">
        <h3>${escapeHtml(g.title)}</h3>
        <p>
          ${g.difficulty ? `<span class="badge">${escapeHtml(g.difficulty)}</span>` : ""}
          ${g.time ? `<span class="badge">${icon("clock", "icon-sm")} ${escapeHtml(g.time)}</span>` : ""}
          <a class="chip" href="${g.url}" target="_blank" rel="noopener">Open on iFixit${icon("external-link", "icon-sm")}</a>
        </p>`;
    if (g.intro) html += `<div class="wiki-content">${g.intro}</div>`;
    if (g.tools && g.tools.length) {
      html += "<h4>Tools</h4><ul>" + g.tools.map(t => `<li>${escapeHtml(t)}</li>`).join("") + "</ul>";
    }
    if (g.parts && g.parts.length) {
      html += "<h4>Parts</h4><ul>" + g.parts.map(p => `<li>${escapeHtml(p)}</li>`).join("") + "</ul>";
    }
    g.steps.forEach((s, i) => {
      html += `<div class="guide-step">
        <h4>Step ${i + 1}${s.title ? ": " + escapeHtml(s.title) : ""}</h4>
        ${s.images.map(u => `<img src="${u}" alt="Step ${i + 1}" loading="lazy">`).join("")}
        <ul>${s.lines.map(l => `<li>${l}</li>`).join("")}</ul>
      </div>`;
    });
    if (g.conclusion) html += `<div class="wiki-content">${g.conclusion}</div>`;
    html += `<p class="attribution">Guide from <a href="${g.url}" target="_blank" rel="noopener">iFixit</a>, licensed CC BY-NC-SA.</p></div>`;
    return html;
  }

  searchForm.addEventListener("submit", async e => {
    e.preventDefault();
    const q = document.getElementById("search-input").value.trim();
    if (!q) return;
    results.innerHTML = "";
    setStatus(statusEl, "Searching iFixit and FDA databases…", "loading");
    try {
      const res = await fetch("/api/search/?q=" + encodeURIComponent(q));
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Search failed");
      setStatus(statusEl, "");
      results.innerHTML = renderSearchResults(json);
      lastSearchHtml = results.innerHTML;
    } catch (err) {
      setStatus(statusEl, "Error: " + err.message, "error");
    }
  });

  const udiForm = document.getElementById("udi-form");
  udiForm.addEventListener("submit", async e => {
    e.preventDefault();
    const udi = document.getElementById("udi-input").value.trim();
    if (!udi) return;
    results.innerHTML = "";
    setStatus(statusEl, "Looking up UDI in NIH AccessGUDID…", "loading");
    try {
      const res = await fetch("/api/udi/?udi=" + encodeURIComponent(udi));
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lookup failed");
      setStatus(statusEl, "");
      const d = json.device;
      results.innerHTML = `
        <h3>Device identified</h3>
        <div class="card">
          <strong>${escapeHtml(d.brand_name || "Unknown brand")}</strong>
          ${d.model ? `<span class="badge">Model ${escapeHtml(d.model)}</span>` : ""}
          <p>${escapeHtml(d.description || "")}</p>
          <p class="muted">Manufacturer: ${escapeHtml(d.company || "—")}
             ${d.catalog_number ? " · Catalog #" + escapeHtml(d.catalog_number) : ""}</p>
        </div>`;
    } catch (err) {
      setStatus(statusEl, "Error: " + err.message, "error");
    }
  });
}

function renderSearchResults(data) {
  let html = "";

  if (!data.exact) {
    const closest = data.effective_query !== data.query
      ? `closest results for “<strong>${escapeHtml(data.effective_query)}</strong>”`
      : "closest related models";
    html += `<div class="status notice"><div>${icon("alert-triangle")} No exact match for
      “<strong>${escapeHtml(data.query)}</strong>” — showing the ${closest}.
      Related models often share the same platform, so their guides can still help.
      <br>
      <button type="button" class="chip followup" data-ask="${escapeHtml(data.query)}">
        ${icon("chat")} Ask the Assistant about ${escapeHtml(data.query)}</button>
      <button type="button" class="chip followup" data-find-manual="${escapeHtml(data.query)}">
        ${icon("document")} Find manual for ${escapeHtml(data.query)}</button></div></div>`;
  }

  if (data.classification.length) {
    html += "<h3>FDA classification (official)</h3>";
    for (const c of data.classification) {
      html += `<div class="card">
        <strong>${escapeHtml(c.device_name)}</strong>
        <span class="badge">Class ${escapeHtml(c.device_class)}</span>
        <span class="badge">${escapeHtml(c.medical_specialty)}</span>
        <p>${escapeHtml(c.definition || "")}</p>
      </div>`;
    }
  }

  if (data.devices.length) {
    html += "<h3>Device pages (iFixit) — click to open here</h3><div class='card-grid'>";
    for (const d of data.devices) {
      html += `<div class="card card-link" data-device="${escapeHtml(d.title)}">
        ${d.image ? `<img src="${d.image}" alt="" loading="lazy">` : ""}
        <strong>${escapeHtml(d.title)}</strong>
        <p>${escapeHtml((d.summary || "").slice(0, 110))}</p>
      </div>`;
    }
    html += "</div>";
  }

  if (data.guides.length) {
    html += "<h3>Repair guides (iFixit) — click to read here</h3><div class='card-grid'>";
    for (const g of data.guides) {
      html += `<div class="card card-link" ${g.guideid ? `data-guide="${g.guideid}"` : ""}>
        ${g.image ? `<img src="${g.image}" alt="" loading="lazy">` : ""}
        <strong>${escapeHtml(g.title)}</strong>
        ${g.difficulty ? `<span class="badge">${escapeHtml(g.difficulty)}</span>` : ""}
      </div>`;
    }
    html += "</div>";
  }

  if (data.recalls.length) {
    html += "<h3>Recent FDA recalls</h3>";
    for (const r of data.recalls) {
      html += `<div class="card recall">
        <strong>${escapeHtml(r.product)}</strong>
        <p>${escapeHtml(r.reason)}</p>
        <p class="muted">${escapeHtml(r.firm)} ${r.date ? "· " + escapeHtml(r.date) : ""}</p>
      </div>`;
    }
  }

  return html || `<p class='muted'>No results found anywhere. Try a more general name
    (e.g. “patient monitor” instead of the full model number), or
    <button type="button" class="chip followup" data-ask="${escapeHtml(data.query)}">${icon("chat")} ask the Assistant</button>
    — it answers even when the databases have nothing.</p>`;
}
