/* Skill 详情弹窗：拉取 /api/skills/{version_id}/detail，渲染元信息 + SKILL.md（marked + DOMPurify）。 */
(function () {
  const escapeHtml = (str) =>
    (str || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  function detailTemplate(d) {
    const tags = (d.tags || [])
      .map((t) => `<span class="chip">${escapeHtml(t)}</span>`)
      .join("");
    const mdSection = d.has_md
      ? `<div class="md-body" id="skillMdBody">渲染中…</div>`
      : `<div class="md-empty">该版本附件中未包含 SKILL.md</div>`;

    return `
      <button class="modal-close-x" aria-label="关闭">×</button>
      <div class="skill-detail-head">
        <div class="icon-tile" style="background:${escapeHtml(d.accent_color)}">${escapeHtml(d.icon)}</div>
        <div>
          <h2 style="color:${escapeHtml(d.accent_color)}; margin:0;">${escapeHtml(d.name)} <span class="tag-version">${escapeHtml(d.version)}</span></h2>
          <div class="skill-detail-sub">
            <span>${escapeHtml(d.category)}</span>
            <span>·</span>
            <span>${escapeHtml(d.owner_name)}（${escapeHtml(d.owner_team)}）</span>
            <span class="scope-chip scope-public">${escapeHtml(d.scope_label)}</span>
            <span class="status-badge">${escapeHtml(d.status_label)}</span>
          </div>
        </div>
      </div>

      <p class="skill-detail-desc">${escapeHtml(d.short_description)}</p>

      <div class="skill-detail-meta">
        <div><span class="k">简介</span><span class="v">${escapeHtml(d.summary) || "—"}</span></div>
        <div><span class="k">详细说明</span><span class="v">${escapeHtml(d.detail) || "—"}</span></div>
        <div><span class="k">版本说明</span><span class="v">${escapeHtml(d.changelog) || "—"}</span></div>
        <div><span class="k">下载 / 点赞</span><span class="v">${d.downloads || 0} / ${d.likes || 0}</span></div>
        <div><span class="k">提交时间</span><span class="v">${escapeHtml(d.submitted_at) || "—"}</span></div>
        ${tags ? `<div class="skill-detail-tags"><span class="k">标签</span><span class="v chips">${tags}</span></div>` : ""}
      </div>

      <h3 class="md-title">SKILL.md</h3>
      ${mdSection}
    `;
  }

  async function openDetail(versionId) {
    const m = Modal.open("<div class='skill-detail-loading'>加载中…</div>", { wide: true });
    m.querySelector(".modal-close-x")?.addEventListener("click", () => Modal.close());
    try {
      const res = await fetch(`/api/skills/${versionId}/detail`);
      if (!res.ok) throw new Error(`加载失败 (${res.status})`);
      const d = await res.json();
      m.innerHTML = detailTemplate(d);
      m.querySelector(".modal-close-x")?.addEventListener("click", () => Modal.close());
      const mdBox = m.querySelector("#skillMdBody");
      if (mdBox && d.has_md && window.marked && window.DOMPurify) {
        const raw = marked.parse(d.skill_md || "");
        mdBox.innerHTML = DOMPurify.sanitize(raw);
      } else if (mdBox) {
        mdBox.textContent = d.skill_md || "";
      }
    } catch (e) {
      m.innerHTML = `<div class="skill-detail-loading">${escapeHtml(e.message)}</div>`;
    }
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-skill-detail]");
    if (!btn) return;
    e.preventDefault();
    openDetail(btn.getAttribute("data-skill-detail"));
  });
})();
