/* Skill 安装弹窗：直接下载 / 安装到 WorkBuddy / 安装到 Claude Code（后者二次确认路径）。 */
(function () {
  "use strict";

  let current = { id: null, name: null, paths: null };

  function triggerDownload(url) {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function openInstallModal(id, name) {
    current = { id, name, paths: null };
    const tpl = `
      <div class="modal-head">
        <h3>安装 ${name}</h3>
        <button class="modal-close" aria-label="关闭">×</button>
      </div>
      <div class="modal-section install-body">
        <button class="install-option" data-install="download">
          <span class="io-ico">⬇️</span>
          <span class="io-text"><b>直接下载 ZIP</b><small>把压缩包保存到本地，自行解压</small></span>
        </button>
        <button class="install-option" data-install="workbuddy">
          <span class="io-ico">💎</span>
          <span class="io-text"><b>安装到 WorkBuddy</b><small>解压到本地 skills 目录，供本机 WorkBuddy 使用</small></span>
        </button>
        <button class="install-option" data-install="claudecode">
          <span class="io-ico">🤖</span>
          <span class="io-text"><b>安装到 Claude Code</b><small>解压到本地 skills 目录，供 Claude Code 使用</small></span>
        </button>
        <div class="install-confirm" hidden>
          <div class="install-confirm-head">将把该 Skill 解压安装到以下路径：</div>
          <input type="text" class="install-path-input" id="installPath" spellcheck="false" />
          <div class="install-confirm-note">🔧 若你的 skills 目录不是默认位置，可手动修改（支持 ~ 简写）。⚠️ 该目录若已存在同名 Skill，将被覆盖。</div>
          <div class="install-confirm-actions">
            <button type="button" class="btn btn-ghost" data-install-back>返回</button>
            <button type="button" class="btn btn-dark" data-install-confirm>确认安装</button>
          </div>
        </div>
        </div>`;
    Modal.open(tpl);
    // 预取按当前系统算出的真实默认路径（Windows 为 C:\Users\...，非 ~）
    try {
      const info = await getJson(`/api/skills/${id}/card`);
      if (info && info.install_paths) current.paths = info.install_paths;
    } catch (_) {
      /* 取不到则用 ~ 回退 */
    }
  }

  function defaultPathFor(target) {
    if (current.paths && current.paths[target]) return current.paths[target];
    const dir = target === "workbuddy" ? ".workbuddy/skills" : ".claude/skills";
    return `~/${dir}/${current.name}`;
  }

  function showConfirm(target) {
    const confirmBox = document.querySelector(".install-confirm");
    const pathEl = document.getElementById("installPath");
    if (!confirmBox || !pathEl) return;
    pathEl.value = defaultPathFor(target);
    confirmBox.dataset.target = target;
    confirmBox.hidden = false;
  }

  async function doInstall(target) {
    const confirmBtn = document.querySelector("[data-install-confirm]");
    if (confirmBtn) confirmBtn.disabled = true;
    const pathInput = document.getElementById("installPath");
    const payload = { target };
    if (pathInput && pathInput.value.trim()) {
      payload.custom_path = pathInput.value.trim();
    }
    try {
      const data = await postForm(
        `/api/skills/${current.id}/install`,
        payload
      );
      toast(`已安装到 ${data.path}`, "success");
      Modal.close();
    } catch (err) {
      toast(`安装失败：${err.message}`, "error");
      if (confirmBtn) confirmBtn.disabled = false;
    }
  }

  document.addEventListener("click", async (e) => {
    const openBtn = e.target.closest("[data-skill-install]");
    if (openBtn) {
      e.preventDefault();
      openInstallModal(
        openBtn.getAttribute("data-skill-install"),
        openBtn.getAttribute("data-skill-name") || "Skill"
      );
      return;
    }

    const opt = e.target.closest("[data-install]");
    if (opt) {
      const mode = opt.getAttribute("data-install");
      if (mode === "download") {
        triggerDownload(`/api/skills/${current.id}/download`);
        Modal.close();
        return;
      }
      showConfirm(mode);
      return;
    }

    if (e.target.closest("[data-install-back]")) {
      const box = document.querySelector(".install-confirm");
      if (box) box.hidden = true;
      return;
    }

    if (e.target.closest("[data-install-confirm]")) {
      const box = document.querySelector(".install-confirm");
      const target = box && box.dataset.target;
      if (target) await doInstall(target);
      return;
    }
  });
})();
