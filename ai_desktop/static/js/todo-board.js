/* 首页工作看板：待办的新增 / 编辑 / 完成 / 删除
   - 添加/编辑复用同一弹窗（对齐项目 modal-head/body/footer 框架）
   - 添加：取消 | 暂定 | 添加；编辑：取消 | 保存
   - 列表展示 due 时间（已逾期红 / 今天橙 / 未来紫）+ 相对时间
   - 进度环 SVG stroke 动画；添加 slideIn、删除 collapse 动画
*/
(function () {
  "use strict";

  const form = document.getElementById("todoAddForm");
  const input = document.getElementById("todoAddInput");
  const pendingList = document.getElementById("pendingList");
  const doneList = document.getElementById("doneList");
  if (!form || !pendingList || !doneList) return;

  const pendingEmpty = document.getElementById("pendingEmpty");
  const doneEmpty = document.getElementById("doneEmpty");
  const ringValue = document.getElementById("ringValue");
  const ringPercent = document.getElementById("ringPercent");
  const ringRatio = document.getElementById("ringRatio");
  const todayDate = document.getElementById("todayDate");

  const RING_C = 2 * Math.PI * 26;

  /* ---------- 工具 ---------- */
  function pad(n) { return String(n).padStart(2, "0"); }

  function toLocalDTInput(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function isoToDTInput(iso) {
    if (!iso) return "";
    return String(iso).slice(0, 16);
  }

  function defaultDT() {
    const d = new Date();
    d.setHours(18, 0, 0, 0);
    return toLocalDTInput(d);
  }

  async function api(method, url, body) {
    const opts = { method, headers: {} };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "请求失败");
    return data;
  }

  function formatRel(iso) {
    const t = new Date(iso);
    if (isNaN(t)) return "";
    const diff = Date.now() - t.getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return "刚刚";
    if (m < 60) return `${m} 分钟前`;
    const h = Math.floor(m / 60);
    if (h < 24 && t.toDateString() === new Date().toDateString()) return `${h} 小时前`;
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (t.toDateString() === yesterday.toDateString()) return "昨天";
    return `${t.getMonth() + 1}月${t.getDate()}日`;
  }

  // 把毫秒格式化为「x天y小时 / x小时 / x分钟」
  function formatDur(ms) {
    ms = Math.max(0, ms);
    const min = Math.floor(ms / 60000);
    const hr = Math.floor(ms / 3600000);
    const day = Math.floor(ms / 86400000);
    if (day >= 1) {
      const h = hr - day * 24;
      return h > 0 ? `${day}天${h}小时` : `${day}天`;
    }
    if (hr >= 1) return `${hr}小时`;
    return `${Math.max(1, min)}分钟`;
  }

  function formatMeta(item) {
    // 进行中：显示预计完成日期 + 倒计时
    if (!item.done) {
      if (item.due_at) {
        const d = new Date(item.due_at);
        if (!isNaN(d)) {
          const when = `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
          const diff = d.getTime() - Date.now();
          if (diff < 0) {
            return { text: `⏰ ${when} · 已逾期 ${formatDur(-diff)}`, cls: "is-overdue" };
          }
          if (diff < 86400000) {
            return { text: `⏰ ${when} · 今天到期 · 还剩 ${formatDur(diff)}`, cls: "is-today" };
          }
          return { text: `⏰ ${when} · 还剩 ${formatDur(diff)}`, cls: "is-future" };
        }
      }
      return { text: formatRel(item.created_at), cls: "" };
    }
    // 已完成：显示完成时间 + 比原计划提前/延后
    const completed = item.completed_at || item.created_at;
    const base = `✓ 完成于 ${formatRel(completed)}`;
    if (item.due_at) {
      const due = new Date(item.due_at);
      const comp = new Date(completed);
      if (!isNaN(due) && !isNaN(comp)) {
        const diff = comp.getTime() - due.getTime(); // 正=延后，负=提前
        if (diff > 0) {
          return { text: `${base} · 比计划晚 ${formatDur(diff)}`, cls: "is-overdue" };
        }
        if (diff < 0) {
          return { text: `${base} · 比计划早 ${formatDur(-diff)}`, cls: "is-early" };
        }
        return { text: `${base} · 准时完成`, cls: "is-early" };
      }
    }
    return { text: base, cls: "" };
  }

  function renderTodayDate() {
    if (!todayDate) return;
    const d = new Date();
    const wk = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
    todayDate.textContent = `· 今天是${d.getMonth() + 1}月${d.getDate()}日 周${wk}`;
  }

  function itemFromLi(li) {
    return {
      done: li.classList.contains("is-done"),
      created_at: li.dataset.created || null,
      completed_at: li.dataset.completed || null,
      due_at: li.dataset.due || null,
    };
  }

  const EDIT_SVG = '<svg viewBox="0 0 20 20"><path d="M4.5 13.5l.7-2.2L11 5.5l2 2-5.8 5.8-2.2.7zM14 4l2 2" /></svg>';
  const DEL_SVG = '<svg viewBox="0 0 20 20"><path d="M6 6l8 8M14 6l-8 8" /></svg>';
  const CHECK_SVG = '<svg viewBox="0 0 20 20"><path d="M5 10.5l3.2 3.2L15 7.2" /></svg>';
  const TRASH_SVG = '<svg viewBox="0 0 20 20"><path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10" /></svg>';

  function makeItem(item) {
    const li = document.createElement("li");
    li.className = "todo-item is-entering" + (item.done ? " is-done" : "");
    li.dataset.id = item.id;
    li.dataset.created = item.created_at || "";
    li.dataset.completed = item.completed_at || "";
    li.dataset.due = item.due_at || "";
    if (item.done) li.dataset.done = "1";

    const check = document.createElement("button");
    check.className = "todo-check";
    check.dataset.toggle = "";
    check.title = item.done ? "标记未完成" : "标记完成";
    check.setAttribute("aria-label", check.title);
    check.innerHTML = CHECK_SVG;

    const body = document.createElement("div");
    body.className = "todo-body";
    const title = document.createElement("span");
    title.className = "todo-title";
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "todo-meta";
    const m = formatMeta(item);
    meta.textContent = m.text;
    if (m.cls) meta.classList.add(m.cls);
    body.append(title, meta);

    const acts = document.createElement("div");
    acts.className = "todo-acts";
    const edit = document.createElement("button");
    edit.className = "todo-act todo-edit";
    edit.dataset.edit = "";
    edit.title = "编辑";
    edit.setAttribute("aria-label", "编辑");
    edit.innerHTML = EDIT_SVG;
    const del = document.createElement("button");
    del.className = "todo-act todo-del";
    del.dataset.delete = "";
    del.title = "删除";
    del.setAttribute("aria-label", "删除");
    del.innerHTML = DEL_SVG;
    acts.append(edit, del);

    li.append(check, body, acts);
    requestAnimationFrame(() => requestAnimationFrame(() => li.classList.remove("is-entering")));
    return li;
  }

  function refreshMeta() {
    document.querySelectorAll("#pendingList .todo-item, #doneList .todo-item").forEach((li) => {
      const meta = li.querySelector(".todo-meta");
      if (!meta) return;
      const m = formatMeta(itemFromLi(li));
      meta.textContent = m.text;
      meta.classList.remove("is-overdue", "is-today", "is-future");
      if (m.cls) meta.classList.add(m.cls);
    });
  }

  function refreshRing() {
    const p = pendingList.querySelectorAll(".todo-item").length;
    const d = doneList.querySelectorAll(".todo-item").length;
    const total = p + d;
    const rate = total > 0 ? d / total : 0;
    if (ringValue) {
      ringValue.style.strokeDasharray = String(RING_C);
      ringValue.style.strokeDashoffset = String(RING_C * (1 - rate));
    }
    if (ringPercent) ringPercent.textContent = Math.round(rate * 100) + "%";
    if (ringRatio) ringRatio.textContent = `${d} / ${total}`;

    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v;
    };
    set("pendingCount", p);
    set("doneCount", d);
    if (pendingEmpty) pendingEmpty.hidden = p > 0;
    if (doneEmpty) doneEmpty.hidden = d > 0;
  }

  /* ---------- 添加/编辑弹窗（对齐项目 modal 框架） ---------- */
  function openTodoModal(opts) {
    const isEdit = opts.mode === "edit";
    const tpl = `
      <div class="modal-head">
        <h3>
          <span class="modal-icon" style="background:var(--accent-purple)">${isEdit ? "✎" : "＋"}</span>
          ${isEdit ? "编辑待办" : "新建待办"}
        </h3>
        <button class="modal-close" type="button" data-todo-cancel title="取消">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-section">
          <p class="label">待办内容</p>
          <input class="todo-field" id="todoFieldTitle" type="text" maxlength="100"
                 placeholder="写点什么…" autocomplete="off">
        </div>
        <div class="modal-section">
          <p class="label">⏰ 预期完成时间（可选，留空即暂定）</p>
          <input type="datetime-local" class="todo-field" id="todoFieldDue">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" data-todo-cancel>取消</button>
        ${isEdit ? "" : '<button class="btn btn-soft" type="button" data-todo-tentative>📝 暂定</button>'}
        <button class="btn btn-dark" type="button" data-todo-confirm>${isEdit ? "保存" : "添加待办"}</button>
      </div>`;

    const m = Modal.open(tpl);
    const titleInput = m.querySelector("#todoFieldTitle");
    const dueInput = m.querySelector("#todoFieldDue");
    if (titleInput) {
      titleInput.value = opts.title || "";
      setTimeout(() => { titleInput.focus(); titleInput.select(); }, 60);
    }
    if (dueInput) {
      dueInput.value = opts.dueAt ? isoToDTInput(opts.dueAt) : defaultDT();
    }

    const cancelBtns = m.querySelectorAll("[data-todo-cancel]");
    const confirmBtn = m.querySelector("[data-todo-confirm]");
    const tentBtn = m.querySelector("[data-todo-tentative]");

    const doCancel = () => Modal.close();
    cancelBtns.forEach((b) => b.addEventListener("click", doCancel));
    const doSubmit = (isTentative) =>
      submitTodo({ mode: opts.mode, id: opts.id, titleInput, dueInput, isTentative, confirmBtn, tentBtn });
    confirmBtn?.addEventListener("click", () => doSubmit(false));
    tentBtn?.addEventListener("click", () => doSubmit(true));
    titleInput?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); doSubmit(false); }
    });
    dueInput?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); doSubmit(false); }
    });
  }

  async function submitTodo({ mode, id, titleInput, dueInput, isTentative, confirmBtn, tentBtn }) {
    const title = (titleInput.value || "").trim();
    if (!title) { toast("待办内容不能为空", "error"); titleInput.focus(); return; }
    const dueAt = isTentative ? "" : (dueInput.value || "");

    if (confirmBtn) confirmBtn.disabled = true;
    if (tentBtn) tentBtn.disabled = true;
    try {
      if (mode === "add") {
        const fd = new FormData();
        fd.append("title", title);
        fd.append("due_at", dueAt);
        const data = await api("POST", "/api/todos", fd);
        pendingList.prepend(makeItem(data.item));
        input.value = "";
        Modal.close();
        refreshRing();
        refreshMeta();
        toast("已添加", "success");
        input.focus();
      } else {
        const data = await api("PATCH", `/api/todos/${id}`, { title, due_at: dueAt });
        const newLi = makeItem(data.item);
        const old = document.querySelector(`.todo-item[data-id="${id}"]`);
        if (old) old.replaceWith(newLi);
        Modal.close();
        refreshRing();
        refreshMeta();
        toast("已保存", "success");
      }
    } catch (err) {
      toast(err.message, "error");
      if (confirmBtn) confirmBtn.disabled = false;
      if (tentBtn) tentBtn.disabled = false;
    }
  }

  /* ---------- 删除确认弹窗（对齐 modal 框架 + 危险色调） ---------- */
  function openDeleteModal(li, title) {
    const tpl = `
      <div class="modal-head">
        <h3>
          <span class="modal-icon" style="background:var(--accent-red)">🗑</span>
          删除待办
        </h3>
        <button class="modal-close" type="button" data-todo-cancel title="取消">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-section">
          <p class="todo-del-warn">此操作不可撤销，确认要删除这条待办吗？</p>
          <div class="todo-del-preview">
            <span class="todo-del-preview-ico">${TRASH_SVG}</span>
            <span class="todo-del-preview-title"></span>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" data-todo-cancel>取消</button>
        <button class="btn btn-danger" type="button" data-todo-del-confirm>删除</button>
      </div>`;

    const m = Modal.open(tpl);
    const previewTitle = m.querySelector(".todo-del-preview-title");
    if (previewTitle) previewTitle.textContent = title; // textContent 防 XSS

    let busy = false;
    const close = () => Modal.close();
    m.querySelectorAll("[data-todo-cancel]").forEach((b) => b.addEventListener("click", close));

    const confirmBtn = m.querySelector("[data-todo-del-confirm]");
    confirmBtn?.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      confirmBtn.disabled = true;
      try {
        await api("DELETE", `/api/todos/${li.dataset.id}`);
        Modal.close();
        collapseRemove(li);
        setTimeout(refreshRing, 60);
        toast("已删除", "success");
      } catch (err) {
        toast(err.message, "error");
        confirmBtn.disabled = false;
        busy = false;
      }
    });
  }

  /* ---------- 动画辅助 ---------- */
  function collapseRemove(li) {
    li.classList.add("is-leaving");
    const done = () => li.remove();
    li.addEventListener("transitionend", done, { once: true });
    setTimeout(done, 340);
  }

  /* ---------- 事件 ---------- */
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = (input.value || "").trim();
    if (!title) return;
    openTodoModal({ mode: "add", title });
  });

  document.addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]");
    if (edit) {
      e.preventDefault();
      const li = edit.closest(".todo-item");
      if (!li) return;
      openTodoModal({
        mode: "edit",
        id: li.dataset.id,
        title: li.querySelector(".todo-title")?.textContent || "",
        dueAt: li.dataset.due || "",
      });
      return;
    }

    const toggle = e.target.closest("[data-toggle]");
    if (toggle) {
      e.preventDefault();
      const li = toggle.closest(".todo-item");
      if (!li || li.classList.contains("is-busy")) return;
      const wasDone = li.classList.contains("is-done");
      li.classList.add("is-busy");
      try {
        const data = await api("PATCH", `/api/todos/${li.dataset.id}`, { done: !wasDone });
        const newLi = makeItem(data.item);
        li.replaceWith(newLi);
        refreshRing();
        toast(data.item.done ? "已完成 🎉" : "已重新打开", "success");
      } catch (err) {
        toast(err.message, "error");
        li.classList.remove("is-busy");
      }
      return;
    }

    const del = e.target.closest("[data-delete]");
    if (del) {
      e.preventDefault();
      const li = del.closest(".todo-item");
      if (!li) return;
      const title = li.querySelector(".todo-title")?.textContent || "";
      openDeleteModal(li, title);
    }
  });

  /* ---------- 初始化 ---------- */
  renderTodayDate();
  refreshRing();
  refreshMeta();
  setInterval(refreshMeta, 60000);
})();
