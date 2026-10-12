/* Shared custom menus for the detailed usage controls and per-card models. */
(function (root) {
  'use strict';
  var buttonClass = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-surface-container-low hover:bg-surface-container-high border border-border-dark font-mono text-xs transition-all active:scale-95';
  var itemClass = 'w-full text-left px-3 py-2 hover:bg-surface-container-high flex items-center justify-between gap-2 transition-colors';

  function icon(name, classes) {
    var node = document.createElement('span');
    node.className = 'material-symbols-outlined ' + classes;
    node.textContent = name;
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  function close(menu, restoreFocus) {
    if (!menu) return;
    var button = menu.querySelector('[aria-haspopup]');
    button.setAttribute('aria-expanded', 'false');
    button.querySelector('[data-chevron]').classList.remove('rotate-180');
    var options = menu.querySelector('[role="listbox"]');
    options.classList.add('opacity-0', 'scale-95');
    setTimeout(function () {
      if (button.getAttribute('aria-expanded') === 'false') options.classList.add('hidden');
    }, 150);
    if (restoreFocus) button.focus();
  }

  function closeAll(except) {
    document.querySelectorAll('[data-custom-dropdown]').forEach(function (menu) {
      if (menu !== except) close(menu, false);
    });
  }

  function open(menu) {
    closeAll(menu);
    document.dispatchEvent(new CustomEvent('tokenly:dropdown-open'));
    var button = menu.querySelector('[aria-haspopup]');
    button.setAttribute('aria-expanded', 'true');
    button.querySelector('[data-chevron]').classList.add('rotate-180');
    var options = menu.querySelector('[role="listbox"]');
    options.classList.remove('hidden');
    requestAnimationFrame(function () { options.classList.remove('opacity-0', 'scale-95'); });
  }

  function choose(select, menu, value) {
    close(menu, true);
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function renderOptions(select, menu) {
    var list = menu.querySelector('[role="listbox"]');
    list.replaceChildren();
    Array.from(select.options).forEach(function (option) {
      var item = document.createElement('button');
      item.type = 'button';
      item.className = itemClass + (option.selected ? ' text-opencode-purple font-medium' : ' text-muted-foreground hover:text-foreground-dark');
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', String(option.selected));
      item.dataset.value = option.value;
      item.disabled = option.disabled;
      var label = document.createElement('span');
      label.className = 'truncate';
      label.textContent = option.textContent;
      item.title = option.textContent;
      item.appendChild(label);
      if (option.selected) item.appendChild(icon('check', 'text-[14px] shrink-0'));
      item.addEventListener('click', function (event) {
        event.stopPropagation();
        choose(select, menu, option.value);
      });
      list.appendChild(item);
    });
    var selected = select.selectedOptions[0];
    menu.querySelector('[data-selected-label]').textContent = selected ? selected.textContent : 'All platforms';
  }

  function handleKeyboard(event, menu) {
    if (event.key === 'Escape') { event.preventDefault(); close(menu, true); return; }
    if (event.key === 'Tab') { close(menu, false); return; }
    var keys = ['ArrowDown', 'ArrowUp', 'Home', 'End'];
    if (keys.indexOf(event.key) === -1) return;
    event.preventDefault();
    if (menu.querySelector('[aria-haspopup]').getAttribute('aria-expanded') !== 'true') open(menu);
    var items = Array.from(menu.querySelectorAll('[role="option"]:not(:disabled)'));
    var index = items.indexOf(document.activeElement);
    if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = items.length - 1;
    else if (index === -1) index = event.key === 'ArrowUp' ? items.length - 1 : 0;
    else index = (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    if (items[index]) items[index].focus();
  }

  function createTrigger(select) {
    var model = select.classList.contains('usage-model-select');
    var duration = select.id === 'usage-range-filter';
    var button = document.createElement('button');
    button.type = 'button';
    button.id = select.id + '-trigger';
    button.className = buttonClass + (model ? ' w-full' : ' w-full sm:w-auto');
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', select.id + '-menu');
    var accessibleLabel = select.parentElement.querySelector('label');
    button.setAttribute('aria-label', accessibleLabel ? accessibleLabel.textContent : 'Choose an option');
    button.appendChild(icon(duration ? 'calendar_today' : model ? 'neurology' : 'hub', 'text-[16px] shrink-0 ' + (duration ? 'text-muted-foreground' : 'text-opencode-purple')));
    button.appendChild(createSelectedLabel(model));
    var chevron = icon('expand_more', 'text-[16px] text-muted-foreground shrink-0 transition-transform duration-200');
    chevron.dataset.chevron = '';
    button.appendChild(chevron);
    return button;
  }

  function createSelectedLabel(model) {
    var label = document.createElement('span');
    label.dataset.selectedLabel = '';
    label.className = 'truncate' + (model ? ' flex-1 text-left' : '');
    return label;
  }

  function createOptionList(select, button) {
    var model = select.classList.contains('usage-model-select');
    var duration = select.id === 'usage-range-filter';
    var list = document.createElement('div');
    list.id = select.id + '-menu';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', button.getAttribute('aria-label'));
    list.className = 'hidden opacity-0 scale-95 transition-all duration-200 absolute mt-1.5 rounded-lg bg-surface-dark/95 border border-border-dark shadow-2xl py-1 z-30 text-xs backdrop-blur-md max-h-64 overflow-y-auto ' + (duration ? 'origin-top-right right-0 ' : 'origin-top-left left-0 ') + (model ? 'w-full min-w-[220px]' : duration ? 'w-44' : 'w-48');
    return list;
  }

  function bindMenu(menu, button) {
    button.addEventListener('click', function (event) {
      event.stopPropagation();
      if (button.getAttribute('aria-expanded') === 'true') close(menu, false);
      else open(menu);
    });
    menu.addEventListener('keydown', function (event) { handleKeyboard(event, menu); });
  }

  function mountMenu(select, menu) {
    select.hidden = true;
    select.setAttribute('aria-hidden', 'true');
    select.tabIndex = -1;
    var oldIcon = select.parentElement.querySelector('.material-symbols-outlined.absolute');
    if (oldIcon) oldIcon.classList.add('hidden');
    select.insertAdjacentElement('afterend', menu);
  }

  function createMenu(select) {
    var menu = document.createElement('div');
    menu.className = 'relative min-w-0' + (select.classList.contains('usage-model-select') ? ' w-full' : '');
    menu.dataset.customDropdown = select.id;
    var button = createTrigger(select);
    menu.appendChild(button);
    menu.appendChild(createOptionList(select, button));
    bindMenu(menu, button);
    mountMenu(select, menu);
    return menu;
  }

  function enhance() {
    document.querySelectorAll('#usage-platform-filter, #usage-range-filter, .usage-model-select').forEach(function (select) {
      var menu = select.parentElement.querySelector('[data-custom-dropdown]') || createMenu(select);
      renderOptions(select, menu);
    });
  }

  document.addEventListener('click', function (event) {
    if (!event.target.closest('[data-custom-dropdown]')) closeAll();
  }, true);
  root.TokenlyDropdowns = {enhance: enhance};
})(window);
