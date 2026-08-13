/* Skill 安装弹窗：下载 ZIP + 下载后如何使用说明。
   浏览器无法操作用户电脑，故不再提供「安装到 WorkBuddy / Claude Code」的服务端安装选项，
   改为把压缩包交给用户，并说明两种本地安装方式。 */
(function () {
  "use strict";

  let current = { id: null, name: null, sourceCard: null };

  function triggerDownload(url) {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // 下载成功后，就地把来源卡片的下载数 +1（与后端 downloads += 1 保持一致）
  function bumpCardCount() {
    const card = current.sourceCard;
    if (!card) return;
    const countEl = card.querySelector(".download-count");
    if (countEl) {
      const cur = parseInt(countEl.textContent.replace(/,/g, ""), 10) || 0;
      countEl.textContent = (cur + 1).toLocaleString();
    }
    if (card.dataset.downloads) {
      card.dataset.downloads = String(parseInt(card.dataset.downloads, 10) + 1);
    }
  }

  function openInstallModal(id, name) {
    current = { id, name };
    const tpl = `
      <div class="modal-head">
        <h3>安装 ${name}</h3>
        <button class="modal-close" aria-label="关闭">×</button>
      </div>
      <div class="modal-section install-body">
        <button class="install-option" data-install="download">
          <span class="io-ico">⬇️</span>
          <span class="io-text"><b>下载 ZIP 压缩包</b><small>保存到本地，按下方说明完成安装</small></span>
        </button>

        <div class="install-help">
          <div class="install-help-title">下载后如何安装？</div>
          <ol class="install-steps">
            <li>
              <b>手动解压</b>
              <p>把 ZIP 解压到本机技能目录：</p>
              <p class="muted">Mac: <code class="install-path">~/.workbuddy/skills</code></p>
              <p class="muted">Windows：<code class="install-path">C:\\Users\\你的用户名\\.workbuddy\\skills</code></p>
            </li>
            <li>
              <b>WorkBuddy 客户端安装</b>
              <p>打开 WorkBuddy 客户端，依次点击 <b>技能 → 添加技能 → 上传技能</b>，选择刚下载的 ZIP 文件即可完成安装。</p>
            </li>
          </ol>
        </div>
      </div>`;
    Modal.open(tpl);
  }

  document.addEventListener("click", (e) => {
    const openBtn = e.target.closest("[data-skill-install]");
    if (openBtn) {
      e.preventDefault();
      openInstallModal(
        openBtn.getAttribute("data-skill-install"),
        openBtn.getAttribute("data-skill-name") || "Skill"
      );
      current.sourceCard = openBtn.closest(".skill-card");
      return;
    }

    const opt = e.target.closest("[data-install]");
    if (opt) {
      const mode = opt.getAttribute("data-install");
      if (mode === "download") {
        triggerDownload(`/api/skills/${current.id}/download`);
        bumpCardCount();
        Modal.close();
        return;
      }
    }
  });
})();
