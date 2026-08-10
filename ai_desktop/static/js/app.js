// ============================================================
// SkillHub — front-end interactions
// ============================================================

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));

// ---------- 模态框 ----------
const Modal = {
  current: null,
  open(html, { wide = false } = {}) {
    this.close();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `<div class="modal ${wide ? 'wide' : ''}" role="dialog">${html}</div>`;
    document.body.appendChild(backdrop);
    document.body.style.overflow = 'hidden';
    this.current = backdrop;
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) this.close();
    });
    return backdrop.querySelector('.modal');
  },
  close() {
    if (this.current) {
      this.current.remove();
      this.current = null;
      document.body.style.overflow = '';
    }
  },
};

// ---------- Toast ----------
function toast(msg, type = 'info') {
  const root = $('#toast-root') || (() => {
    const r = document.createElement('div');
    r.id = 'toast-root';
    document.body.appendChild(r);
    return r;
  })();
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ---------- 通用 fetch ----------
async function postForm(url, data) {
  const fd = data instanceof FormData ? data : toFormData(data);
  const res = await fetch(url, { method: 'POST', body: fd });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = await res.json();
      if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch (_) { /* noop */ }
    throw new Error(detail);
  }
  return res.json();
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  return res.json();
}

function toFormData(obj) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(obj)) {
    if (v === null || v === undefined) continue;
    fd.append(k, v);
  }
  return fd;
}

// ---------- 关闭模态框 ----------
document.addEventListener('click', (e) => {
  const closeBtn = e.target.closest('.modal-close');
  if (closeBtn) {
    Modal.close();
    return;
  }
});

// ---------- 新建 Skill 模态框 ----------
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-upload-skill]');
  if (!btn) return;
  e.preventDefault();

  const tpl = `
    <div class="modal-head">
      <h3>新建 Skill</h3>
      <button class="modal-close">×</button>
    </div>
    <form id="newSkillForm" enctype="multipart/form-data">
      <div class="modal-section">
        <div class="field-row">
          <div class="field">
            <label>Skill 名称</label>
            <input name="name" placeholder="例如：Release Notes Writer" required>
          </div>
          <div class="field">
            <label>版本号</label>
            <input name="version" value="1.0.0" required>
          </div>
        </div>
        <div class="field">
          <label>一句话简介</label>
          <input name="summary" placeholder="说明这个 Skill 能帮助谁完成什么工作" required>
        </div>
        <div class="field">
          <label>详细说明</label>
          <textarea name="detail" placeholder="说明输入、工作过程、输出和适用边界" required></textarea>
        </div>
      </div>
      <div class="modal-section">
        <div class="field-row">
          <div class="field">
            <label>分类</label>
            <select name="category">
              <option value="研发工具">研发工具</option>
              <option value="代码质量">代码质量</option>
              <option value="数据与分析">数据与分析</option>
              <option value="会议与协作">会议与协作</option>
              <option value="运营增长">运营增长</option>
              <option value="安全合规">安全合规</option>
              <option value="业务运营">业务运营</option>
              <option value="客服与支持">客服与支持</option>
            </select>
          </div>
          <div class="field">
            <label>标签</label>
            <input name="tags" placeholder="代码评审, Git, 质量">
          </div>
        </div>

        <div class="field">
          <label>权限范围</label>
          <div class="scope-choice" data-scope-group>
            <div class="scope-card is-active" data-scope-value="public">
              <div class="top"><input type="radio" name="scope" value="public" checked> 🌍 公开</div>
              <div class="desc">企业内部所有员工可见</div>
            </div>
            <div class="scope-card" data-scope-value="department">
              <div class="top"><input type="radio" name="scope" value="department"> 🏢 部门内可见</div>
              <div class="desc">仅数字化工作台员工可见</div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-section">
        <div class="field">
          <label>Skill 包 (可选 · 自动生成占位 zip)</label>
          <label class="upload-box" data-upload-box>
            <div class="icon">📦</div>
            <div class="title">点击可上传替换文件</div>
            <div class="sub">支持 .zip（≤ 20MB）</div>
            <input type="file" name="file" accept=".zip" style="display:none">
          </label>
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-ghost modal-close">取消</button>
        <button type="submit" class="btn btn-dark">提交审核</button>
      </div>
    </form>
  `;
  const m = Modal.open(tpl, { wide: true });

  // scope 单选
  const group = m.querySelector('[data-scope-group]');
  group.addEventListener('change', () => {
    $$('.scope-card', group).forEach((c) => {
      const checked = c.querySelector('input').checked;
      c.classList.toggle('is-active', checked);
    });
  });

  // upload box
  const ub = m.querySelector('[data-upload-box]');
  ub.addEventListener('click', (e) => {
    if (e.target.tagName === 'INPUT') return;
    ub.querySelector('input[type=file]').click();
  });
  ub.querySelector('input[type=file]').addEventListener('change', () => {
    const f = ub.querySelector('input[type=file]').files[0];
    if (f) {
      ub.classList.add('has-file');
      ub.querySelector('.title').textContent = `已选择：${f.name}`;
    }
  });

  m.querySelector('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      const res = await postForm('/api/skills/upload', fd);
      toast('已提交，当前状态：' + (res.status === 'published' ? '已发布' : '草稿'), 'success');
      Modal.close();
      setTimeout(() => location.reload(), 600);
    } catch (err) {
      toast('提交失败：' + err.message, 'error');
    }
  });
});

// ---------- 撤回审核 ----------
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-withdraw]');
  if (!btn) return;
  e.preventDefault();
  const vid = btn.getAttribute('data-withdraw');
  const ok = confirm('确认撤回这条待审核提交？撤回后会回到草稿状态，可再次编辑后提交。');
  if (!ok) return;
  try {
    const res = await postForm(`/api/skills/${vid}/withdraw`, new FormData());
    toast('已撤回，可重新编辑后再提交', 'success');
    setTimeout(() => location.reload(), 600);
  } catch (err) {
    toast('撤回失败：' + err.message, 'error');
  }
});

// ---------- 编辑草稿 ----------
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-edit-submission]');
  if (!btn) return;
  e.preventDefault();
  const vid = btn.getAttribute('data-edit-submission');
  try {
    const data = await getJson(`/api/reviews/${vid}`);
    const tpl = `
      <div class="modal-head">
        <h3>
          <span class="modal-icon" style="background:${escapeHtml(data.tags && data.tags.length ? '#5B6CFF' : '#5B6CFF')}">📝</span>
          编辑草稿
        </h3>
        <button class="modal-close">×</button>
      </div>
      <form id="editForm" enctype="multipart/form-data">
        <div class="modal-section">
          <p class="muted" style="margin: 0;">修改草稿内容后重新提交审核。</p>
        </div>

        <div class="modal-section">
          <div class="field-row">
            <div class="field">
              <label>分类</label>
              <select name="category">
                <option value="业务运营" ${data.tags && data.tags.includes('业务运营') ? '' : ''}>业务运营</option>
                <option value="研发工具">研发工具</option>
                <option value="代码质量">代码质量</option>
                <option value="数据与分析">数据与分析</option>
                <option value="会议与协作">会议与协作</option>
                <option value="运营增长">运营增长</option>
                <option value="安全合规">安全合规</option>
                <option value="客服与支持">客服与支持</option>
              </select>
            </div>
            <div class="field">
              <label>标签</label>
              <input name="tags" value="${escapeAttr((data.tags || []).join(', '))}" placeholder="用逗号分隔">
            </div>
          </div>

          <div class="field">
            <label>权限范围</label>
            <div class="scope-choice" data-scope-group>
              <div class="scope-card ${data.scope === 'public' ? 'is-active' : ''}" data-scope-value="public">
                <div class="top"><input type="radio" name="scope" value="public" ${data.scope === 'public' ? 'checked' : ''}> 🌍 公开</div>
                <div class="desc">企业内部所有员工可见</div>
              </div>
              <div class="scope-card ${data.scope === 'department' ? 'is-active' : ''}" data-scope-value="department">
                <div class="top"><input type="radio" name="scope" value="department" ${data.scope === 'department' ? 'checked' : ''}> 🏢 部门内可见</div>
                <div class="desc">仅数字化工作台员工可见</div>
              </div>
            </div>
          </div>

          <div class="field">
            <label>版本说明</label>
            <textarea name="changelog" placeholder="本次改动概述">${escapeHtml(data.changelog || '')}</textarea>
          </div>

          <div class="field">
            <label>Skill 包 (可选替换)</label>
            <label class="upload-box" data-upload-box>
              <div class="icon">📦</div>
              <div class="title">保留当前附件</div>
              <div class="sub">点击可上传替换文件</div>
              <input type="file" name="file" accept=".zip" style="display:none">
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-ghost modal-close">取消</button>
          <button type="submit" class="btn btn-dark">重新提交审核</button>
        </div>
      </form>
    `;
    const m = Modal.open(tpl, { wide: true });

    m.querySelector('[data-scope-group]').addEventListener('change', (ev) => {
      $$('.scope-card', m).forEach((c) => c.classList.toggle('is-active',
        c.querySelector('input').checked));
    });

    const ub = m.querySelector('[data-upload-box]');
    ub.addEventListener('click', (ev) => {
      if (ev.target.tagName === 'INPUT') return;
      ub.querySelector('input[type=file]').click();
    });
    ub.querySelector('input[type=file]').addEventListener('change', () => {
      const f = ub.querySelector('input[type=file]').files[0];
      if (f) {
        ub.classList.add('has-file');
        ub.querySelector('.title').textContent = `已选择：${f.name}`;
      }
    });

    m.querySelector('form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const form = ev.currentTarget;
      const fd = new FormData(form);
      fd.append('detail', data.detail || '');
      try {
        await postForm(`/api/skills/${vid}/edit`, fd);
        toast('已重新提交审核', 'success');
        Modal.close();
        setTimeout(() => location.reload(), 600);
      } catch (err) {
        toast('提交失败：' + err.message, 'error');
      }
    });
  } catch (err) {
    toast('加载失败：' + err.message, 'error');
  }
});

// ---------- 审核操作 ----------
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-review]');
  if (!btn) return;
  e.preventDefault();
  const vid = btn.getAttribute('data-review');
  try {
    const data = await getJson(`/api/reviews/${vid}`);
    const tpl = `
      <div class="modal-head">
        <h3>
          ${escapeHtml(data.name)}
          <span class="modal-meta">
            <span class="version-tag">${escapeHtml(data.version)}</span>
            <span class="status-badge pending">${escapeHtml(data.status_label)}</span>
          </span>
        </h3>
        <button class="modal-close">×</button>
      </div>

      <div class="modal-section">
        <p class="muted" style="margin: 0;">由 ${escapeHtml(data.submitted_by || '—')} 于 ${escapeHtml(data.submitted_at || '')} 提交</p>
        <div class="field" style="margin-top:10px;">
          <label>版本说明</label>
          <div style="font-size: 13px; color: var(--ink-2);">${escapeHtml(data.changelog || data.summary || '—')}</div>
        </div>
      </div>

      <div class="review-meta">
        <div class="cell"><div class="label">文件大小</div><div class="value">${escapeHtml(data.attachment_size_human)}</div></div>
        <div class="cell"><div class="label">提交方式</div><div class="value">${escapeHtml(data.submission_source)}</div></div>
        <div class="cell"><div class="label">版本</div><div class="value">${escapeHtml(data.version)}</div></div>
        <div class="cell"><div class="label">权限范围</div><div class="value">${escapeHtml(data.scope_label)}</div></div>
        <div class="cell"><div class="label">提交人</div><div class="value">${escapeHtml(data.submitted_by || '—')}</div></div>
      </div>

      <div class="modal-section">
        <div class="review-grid">
          <div class="field">
            <label>展示标识</label>
            <select name="feature_badge" data-modal-feature>
              <option value="false">不设置</option>
              <option value="true">设为精选</option>
            </select>
          </div>
          <div class="field">
            <label>审核意见</label>
            <textarea name="note" placeholder="通过时可选，拒绝时请说明修改要求"></textarea>
          </div>
        </div>
        <div class="confirm-row" style="margin-top:10px;">
          <input type="checkbox" id="publishCheck" checked>
          <label for="publishCheck" style="margin:0; color:var(--ink-3); font-weight:normal;">
            发布前请确认来源可信，不包含密钥或敏感数据，并符合内部使用规范。
          </label>
        </div>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-danger" data-reject>拒绝</button>
        <button type="button" class="btn btn-success" data-approve>通过并发布</button>
      </div>
    `;
    const m = Modal.open(tpl, { wide: true });

    m.querySelector('[data-reject]').addEventListener('click', async () => {
      const note = m.querySelector('[name="note"]').value.trim();
      if (!note) { toast('拒绝时必须填写审核意见', 'error'); return; }
      try {
        await postForm(`/api/reviews/${vid}/decide`, {
          decision: 'reject',
          note,
          feature_badge: 'false',
        });
        toast('已拒绝', 'success');
        Modal.close();
        setTimeout(() => location.reload(), 500);
      } catch (err) { toast('操作失败：' + err.message, 'error'); }
    });

    m.querySelector('[data-approve]').addEventListener('click', async () => {
      const note = m.querySelector('[name="note"]').value.trim();
      const feature = m.querySelector('[name="feature_badge"]').value;
      try {
        await postForm(`/api/reviews/${vid}/decide`, {
          decision: 'approve',
          note,
          feature_badge: feature,
        });
        toast('已通过并发布', 'success');
        Modal.close();
        setTimeout(() => location.reload(), 500);
      } catch (err) { toast('操作失败：' + err.message, 'error'); }
    });
  } catch (err) {
    toast('加载失败：' + err.message, 'error');
  }
});

// ---------- 我的上传：统计卡过滤 + 分页 ----------
const MyUploadsPager = (function () {
  let _items = [];
  let _perPage = 10;
  let _page = 1;
  let _filter = 'all';
  let _container = null;
  let _pager = null;

  function init(opts = {}) {
    _container = document.querySelector(opts.container || '.page');
    _pager = document.getElementById(opts.pagerId || 'pagination');
    _perPage = opts.perPage || 10;
    _items = $$(opts.itemSelector || '.record[data-status]');
    if (!_items.length || !_pager) return;
    _pager.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-page]');
      if (!btn || btn.disabled) return;
      _page = parseInt(btn.dataset.page, 10);
      render();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    render();
  }

  function setFilter(f) {
    _filter = f;
    _page = 1;
    render();
  }

  function visibleItems() {
    return _items.filter((r) => {
      const st = r.getAttribute('data-status');
      return _filter === 'all' || st === _filter;
    });
  }

  function render() {
    const vis = visibleItems();
    const total = vis.length;
    const totalPages = Math.max(1, Math.ceil(total / _perPage));
    if (_page > totalPages) _page = totalPages;
    const start = (_page - 1) * _perPage;
    const end = start + _perPage;

    _items.forEach((r) => { r.style.display = 'none'; });
    vis.slice(start, end).forEach((r) => { r.style.display = ''; });

    if (totalPages <= 1) { _pager.innerHTML = ''; return; }
    let html = `<span class="page-info">${total} 条 · 第 ${_page}/${totalPages} 页</span>`;
    html += `<button class="page-btn" data-page="${_page - 1}" ${_page === 1 ? 'disabled' : ''}>‹</button>`;
    pageNumbers(_page, totalPages).forEach((p) => {
      if (p === '...') html += `<span class="page-dots">…</span>`;
      else html += `<button class="page-btn ${p === _page ? 'is-active' : ''}" data-page="${p}">${p}</button>`;
    });
    html += `<button class="page-btn" data-page="${_page + 1}" ${_page === totalPages ? 'disabled' : ''}>›</button>`;
    _pager.innerHTML = html;
  }

  function pageNumbers(cur, total) {
    const max = 7;
    if (total <= max) return Array.from({length: total}, (_, i) => i + 1);
    const pages = [1];
    const left = Math.max(2, cur - 2);
    const right = Math.min(total - 1, cur + 2);
    if (left > 2) pages.push('...');
    for (let i = left; i <= right; i++) pages.push(i);
    if (right < total - 1) pages.push('...');
    pages.push(total);
    return pages;
  }

  return { init, setFilter };
})();

document.addEventListener('click', (e) => {
  const bar = e.target.closest('[data-filter-bar]');
  if (!bar) return;
  const card = e.target.closest('[data-filter]');
  if (!card) return;
  const filter = card.getAttribute('data-filter');
  $$('[data-filter]', bar).forEach((c) => c.classList.toggle('is-active', c === card));
  MyUploadsPager.setFilter(filter);
});

// ---------- 更新迭代 ----------
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-iterate]');
  if (!btn) return;
  e.preventDefault();
  const vid = btn.getAttribute('data-iterate');
  try {
    const data = await getJson(`/api/reviews/${vid}`);
    const suggestedVersion = suggestNextVersion(data.version);
    const tpl = `
      <div class="modal-head">
        <h3>
          <span class="modal-icon" style="background:${escapeHtml(data.accent_color || '#5B6CFF')}">${escapeHtml(data.icon || '📦')}</span>
          更新迭代 · ${escapeHtml(data.name)}
        </h3>
        <button class="modal-close">×</button>
      </div>
      <form id="iterateForm" enctype="multipart/form-data">
        <div class="modal-section">
          <p class="muted" style="margin: 0;">基于已发布版本 ${escapeHtml(data.version)} 创建新版本，提交后进入审核流程。原版本在新版本发布后将自动标记为"已替代"。</p>
        </div>

        <div class="modal-section">
          <div class="field-row">
            <div class="field">
              <label>Skill 名称</label>
              <input value="${escapeAttr(data.name)}" disabled style="background: var(--bg-mute); color: var(--ink-3);">
              <input type="hidden" name="name" value="${escapeAttr(data.name)}">
            </div>
            <div class="field">
              <label>新版本号</label>
              <input name="version" value="${escapeAttr(suggestedVersion)}" required>
              <div class="hint">基于 ${escapeHtml(data.version)} 自动迭代，可手动调整</div>
            </div>
          </div>

          <div class="field">
            <label>一句话简介</label>
            <input name="summary" value="${escapeAttr(data.summary || '')}" placeholder="说明这个 Skill 能帮助谁完成什么工作" required>
          </div>

          <div class="field">
            <label>详细说明</label>
            <textarea name="detail" placeholder="说明输入、工作过程、输出和适用边界" required>${escapeHtml(data.detail || '')}</textarea>
          </div>
        </div>

        <div class="modal-section">
          <div class="field-row">
            <div class="field">
              <label>分类</label>
              <select name="category">
                ${['研发工具','代码质量','数据与分析','会议与协作','运营增长','安全合规','业务运营','客服与支持']
                  .map((c) => `<option value="${c}" ${c === escapeHtml(data.category) ? 'selected' : ''}>${c}</option>`).join('')}
              </select>
            </div>
            <div class="field">
              <label>标签</label>
              <input name="tags" value="${escapeAttr((data.tags || []).join(', '))}" placeholder="用逗号分隔">
            </div>
          </div>

          <div class="field">
            <label>权限范围</label>
            <div class="scope-choice" data-scope-group>
              <div class="scope-card ${data.scope === 'public' ? 'is-active' : ''}" data-scope-value="public">
                <div class="top"><input type="radio" name="scope" value="public" ${data.scope === 'public' ? 'checked' : ''}> 🌍 公开</div>
                <div class="desc">企业内部所有员工可见</div>
              </div>
              <div class="scope-card ${data.scope === 'department' ? 'is-active' : ''}" data-scope-value="department">
                <div class="top"><input type="radio" name="scope" value="department" ${data.scope === 'department' ? 'checked' : ''}> 🏢 部门内可见</div>
                <div class="desc">仅数字化工作台员工可见</div>
              </div>
            </div>
          </div>

          <div class="field">
            <label>版本说明 <span style="color: var(--accent-red);">*</span></label>
            <textarea name="changelog" placeholder="本次迭代改了什么" required></textarea>
          </div>

          <div class="field">
            <label>Skill 包 (可选替换，否则沿用上一个版本的包)</label>
            <label class="upload-box" data-upload-box>
              <div class="icon">📦</div>
              <div class="title">保留当前附件</div>
              <div class="sub">点击可上传替换文件</div>
              <input type="file" name="file" accept=".zip" style="display:none">
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-ghost modal-close">取消</button>
          <button type="submit" class="btn btn-dark">提交迭代版本</button>
        </div>
      </form>
    `;
    const m = Modal.open(tpl, { wide: true });

    m.querySelector('[data-scope-group]').addEventListener('change', () => {
      $$('.scope-card', m).forEach((c) => c.classList.toggle('is-active',
        c.querySelector('input').checked));
    });

    const ub = m.querySelector('[data-upload-box]');
    ub.addEventListener('click', (ev) => {
      if (ev.target.tagName === 'INPUT') return;
      ub.querySelector('input[type=file]').click();
    });
    ub.querySelector('input[type=file]').addEventListener('change', () => {
      const f = ub.querySelector('input[type=file]').files[0];
      if (f) {
        ub.classList.add('has-file');
        ub.querySelector('.title').textContent = `已选择：${f.name}`;
      }
    });

    m.querySelector('form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const form = ev.currentTarget;
      const fd = new FormData(form);
      try {
        const res = await postForm(`/api/skills/${vid}/iterate`, fd);
        toast('迭代版本已提交审核', 'success');
        Modal.close();
        setTimeout(() => location.reload(), 600);
      } catch (err) {
        toast('提交失败：' + err.message, 'error');
      }
    });
  } catch (err) {
    toast('加载失败：' + err.message, 'error');
  }
});

// 版本号自动迭代：patch +1，若 patch 不存在则补 .0
function suggestNextVersion(ver) {
  const parts = String(ver || '1.0.0').split('.');
  if (parts.length < 3) {
    while (parts.length < 3) parts.push('0');
  }
  const patch = parseInt(parts[2], 10);
  parts[2] = isNaN(patch) ? '1' : String(patch + 1);
  return parts.slice(0, 3).join('.');
}

// ---------- 新建 Skill：名称查重 ----------
document.addEventListener('input', async (e) => {
  const inp = e.target.closest('#newSkillForm input[name="name"]');
  if (!inp) return;
  const val = inp.value.trim();
  const hint = inp.closest('.field').querySelector('.name-hint');
  if (val.length < 2) {
    if (hint) hint.remove();
    inp.setCustomValidity('');
    return;
  }
  try {
    const r = await fetch(`/api/skills/check-name?name=${encodeURIComponent(val)}`);
    const j = await r.json();
    if (j.exists) {
      if (!hint) {
        const h = document.createElement('div');
        h.className = 'name-hint hint';
        h.style.color = 'var(--accent-red)';
        h.textContent = `「${val}」已存在，请换个名字`;
        inp.closest('.field').appendChild(h);
      } else {
        hint.textContent = `「${val}」已存在，请换个名字`;
      }
      inp.setCustomValidity('名称已存在');
    } else {
      if (hint) hint.remove();
      inp.setCustomValidity('');
    }
  } catch (_) { /* 静默 */ }
});

// ---------- 点赞 / 取消点赞 ----------
function _getLikedSet() {
  try { return new Set(JSON.parse(localStorage.getItem('skillhub_liked') || '[]')); }
  catch (_) { return new Set(); }
}
function _saveLikedSet(set) {
  localStorage.setItem('skillhub_liked', JSON.stringify([...set]));
}

// 页面加载时恢复点赞状态
document.addEventListener('DOMContentLoaded', () => {
  const liked = _getLikedSet();
  document.querySelectorAll('[data-like]').forEach(el => {
    if (liked.has(el.getAttribute('data-like'))) el.classList.add('is-liked');
  });
});

document.addEventListener('click', async (e) => {
  const likeBtn = e.target.closest('[data-like]');
  if (!likeBtn) return;
  e.preventDefault();
  e.stopPropagation();
  const skillId = likeBtn.getAttribute('data-like');
  const wasLiked = likeBtn.classList.contains('is-liked');
  const action = wasLiked ? 'unlike' : 'like';
  try {
    const fd = new FormData();
    fd.append('action', action);
    const res = await fetch(`/api/skills/${skillId}/toggle-like`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error('request failed');
    const data = await res.json();
    likeBtn.classList.toggle('is-liked', !wasLiked);
    const countEl = likeBtn.querySelector('.like-count');
    if (countEl) countEl.textContent = data.likes;
    const liked = _getLikedSet();
    if (wasLiked) liked.delete(skillId); else liked.add(skillId);
    _saveLikedSet(liked);
  } catch (_) {
    toast('操作失败，请重试', 'error');
  }
});

// ---------- 下载计数实时更新 ----------
document.addEventListener('click', (e) => {
  const dl = e.target.closest('[data-card-download]');
  if (!dl) return;
  const card = dl.closest('.skill-card');
  if (card) {
    const countEl = card.querySelector('.download-count');
    if (countEl) {
      const current = parseInt(countEl.textContent.replace(/,/g, ''), 10) || 0;
      countEl.textContent = (current + 1).toLocaleString();
    }
    const dlAttr = card.dataset.downloads;
    if (dlAttr) card.dataset.downloads = String(parseInt(dlAttr, 10) + 1);
  }
  // 不阻止默认行为，让浏览器正常下载
});

// ---------- 工具：HTML 转义 ----------
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function escapeAttr(s) { return escapeHtml(s); }

// ---------- 关闭模态框：ESC ----------
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    Modal.close();
    // 关闭用户下拉
    const ud = document.getElementById('userDropdown');
    if (ud) ud.classList.remove('open');
  }
});

// ---------- 用户下拉菜单 ----------
document.addEventListener('click', (e) => {
  const ud = document.getElementById('userDropdown');
  if (!ud) return;
  const trigger = ud.querySelector('.user-chip-trigger');
  if (trigger && (e.target === trigger || trigger.contains(e.target))) {
    e.preventDefault();
    ud.classList.toggle('open');
    return;
  }
  if (!ud.contains(e.target)) {
    ud.classList.remove('open');
  }
});

// ---------- 反馈弹窗 ----------
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-action="feedback"]');
  if (!btn) return;
  e.preventDefault();
  // 关闭下拉
  const ud = document.getElementById('userDropdown');
  if (ud) ud.classList.remove('open');

  const tpl = `
    <div class="modal-head">
      <h3>💬 意见反馈</h3>
      <button class="modal-close" aria-label="关闭">×</button>
    </div>
    <div class="modal-body">
      <p style="margin: 0 0 14px; color: var(--ink-3); font-size: 14px;">
        您有什么好的建议可以反馈给我们，我们会认真阅读每一条反馈。
      </p>
      <div class="field">
        <label>您的建议</label>
        <textarea id="feedbackText" placeholder="请输入您的建议或意见…" style="min-height: 120px;"></textarea>
      </div>
      <div class="feedback-contact">
        <span>📱</span>
        <span>或者通过钉钉联系：</span>
        <span class="dingtalk-id">黄松</span>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-ghost modal-close">取消</button>
      <button type="button" class="btn btn-dark" id="feedbackSubmit">提交反馈</button>
    </div>
  `;
  const m = Modal.open(tpl);

  m.querySelector('#feedbackSubmit').addEventListener('click', async () => {
    const text = m.querySelector('#feedbackText').value.trim();
    if (!text) {
      toast('请输入反馈内容', 'error');
      return;
    }
    const btn = m.querySelector('#feedbackSubmit');
    btn.disabled = true;
    btn.textContent = '提交中…';
    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '提交失败');
      }
      toast('感谢您的反馈！我们已收到。', 'success');
      Modal.close();
    } catch (err) {
      toast(err.message || '提交失败', 'error');
      btn.disabled = false;
      btn.textContent = '提交反馈';
    }
  });
});

