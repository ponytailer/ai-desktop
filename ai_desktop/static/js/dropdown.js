/* =========================================================
 * 全站统一下拉组件（基线：技能广场「全部分类」）
 * ---------------------------------------------------------
 * 结构约定（所有 .dropdown 必须满足）：
 *   <div class="dropdown" id="xxx">
 *     <button class="dropdown-trigger" type="button">
 *       <span class="dropdown-label">当前值</span>
 *       <svg class="dropdown-arrow">…chevron…</svg>
 *     </button>
 *     <input type="hidden" name="表单字段名" value="当前值">
 *     <div class="dropdown-menu">
 *       <div class="dropdown-item is-active" data-value="v1">文案1</div>
 *       <div class="dropdown-item" data-value="v2">文案2</div>
 *     </div>
 *   </div>
 *
 * 要点：
 *   - 隐藏域 name 与旧原生 <select> 同名，FormData 提交链路不变；
 *   - 选中 item 时自动同步隐藏域值并派发 change 事件（可监听联动）；
 *   - 页面加载自动初始化所有未初始化的 .dropdown；
 *   - 弹窗/动态渲染的 .dropdown 需在插入 DOM 后手动 initDropdown(el)；
 *   - initDropdown(el, cb) / initDropdown(el, {onChange}) 均可绑定回调。
 * ========================================================= */
(function (global) {
  'use strict';

  function initDropdown(el, opts) {
    if (!el || !el.querySelector) return null;

    // 已初始化：仅允许补绑回调，返回既有实例
    if (el.dataset.ddInit && el.__dd) {
      const cb = typeof opts === 'function' ? opts : (opts && opts.onChange);
      if (cb) el.__dd.setChange(cb);
      return el.__dd;
    }

    const trigger = el.querySelector('.dropdown-trigger');
    const label = el.querySelector('.dropdown-label');
    const hidden = el.querySelector('input[type="hidden"]');
    const items = Array.from(el.querySelectorAll('.dropdown-item'));
    const activeItem = el.querySelector('.dropdown-item.is-active');
    let currentValue = activeItem ? (activeItem.dataset.value || '') : '';
    let onChange = (typeof opts === 'function' ? opts : (opts && opts.onChange)) || null;

    function syncLabel() {
      if (!label) return;
      const it = items.find((i) => i.dataset.value === currentValue);
      if (it) label.textContent = it.textContent;
    }

    function emit() {
      if (hidden) {
        hidden.value = currentValue;
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (onChange) onChange(currentValue);
    }

    function closeOthers() {
      document.querySelectorAll('.dropdown.open').forEach((d) => {
        if (d !== el) {
          d.classList.remove('open');
          const t = d.querySelector('.dropdown-trigger');
          if (t) t.setAttribute('aria-expanded', 'false');
        }
      });
    }

    function open() {
      closeOthers();
      el.classList.add('open');
      if (trigger) trigger.setAttribute('aria-expanded', 'true');
    }

    function close() {
      el.classList.remove('open');
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }

    function setValue(v) {
      currentValue = v;
      items.forEach((i) => i.classList.toggle('is-active', i.dataset.value === v));
      syncLabel();
      emit();
    }

    if (trigger) {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        el.classList.contains('open') ? close() : open();
      });
    }
    items.forEach((item) => {
      item.addEventListener('click', () => {
        setValue(item.dataset.value);
        close();
      });
    });

    el.dataset.ddInit = '1';
    const api = {
      get value() { return currentValue; },
      setValue,
      open,
      close,
      setChange(c) { onChange = c; },
    };
    el.__dd = api;
    return api;
  }

  /** 初始化容器内所有尚未初始化的 .dropdown（弹窗插入后调用） */
  function initDropdowns(root) {
    const r = root || document;
    const list = r.querySelectorAll ? r.querySelectorAll('.dropdown:not([data-dd-init])') : [];
    const out = [];
    list.forEach((el) => out.push(initDropdown(el)));
    return out;
  }

  // 全局点击外部关闭（事件委托，动态元素同样生效）
  if (!global.__ddBound) {
    global.__ddBound = true;
    document.addEventListener('click', (e) => {
      document.querySelectorAll('.dropdown.open').forEach((d) => {
        if (!d.contains(e.target)) {
          d.classList.remove('open');
          const t = d.querySelector('.dropdown-trigger');
          if (t) t.setAttribute('aria-expanded', 'false');
        }
      });
    });
  }

  // 页面加载完成后自动初始化全部 .dropdown（已显式初始化的跳过）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initDropdowns());
  } else {
    initDropdowns();
  }

  global.initDropdown = initDropdown;
  global.initDropdowns = initDropdowns;
})(window);
