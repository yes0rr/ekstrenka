/* Мобильное меню в шапке: бургер, панель, Esc, блокировка прокрутки.
   Разметка — в base.html, показ на узких экранах — в css/style.css. */

(function () {
  const root = document.getElementById('mobileMenu');
  if (!root) return;

  const toggle = document.querySelector('[data-mobile-menu-open]');
  const panel = root.querySelector('.mobile-menu-panel');
  if (!toggle || !panel) return;

  const closers = root.querySelectorAll('[data-mobile-menu-close]');
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

  let lastFocused = null;

  function isOpen() {
    return root.classList.contains('open');
  }

  function openMenu() {
    if (isOpen()) return;
    lastFocused = document.activeElement;
    root.classList.add('open');
    root.removeAttribute('aria-hidden');
    toggle.setAttribute('aria-expanded', 'true');
    document.body.classList.add('menu-open');
    const first = panel.querySelector(FOCUSABLE);
    if (first) first.focus();
  }

  function closeMenu(restoreFocus = true) {
    if (!isOpen()) return;
    root.classList.remove('open');
    root.setAttribute('aria-hidden', 'true');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
    if (restoreFocus) {
      const target = lastFocused && lastFocused !== document.body
        ? lastFocused
        : toggle;
      if (target && typeof target.focus === 'function') target.focus();
    }
    lastFocused = null;
  }

  toggle.addEventListener('click', function () {
    if (isOpen()) closeMenu();
    else openMenu();
  });

  closers.forEach(function (el) {
    el.addEventListener('click', function () {
      closeMenu();
    });
  });

  document.addEventListener('keydown', function (event) {
    if (!isOpen()) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      closeMenu();
      return;
    }

    // держим Tab внутри панели, пока она открыта
    if (event.key !== 'Tab') return;
    const items = Array.from(panel.querySelectorAll(FOCUSABLE)).filter(function (el) {
      return el.offsetParent !== null;
    });
    if (!items.length) return;

    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // если экран стал широким, пока меню открыто, — закрываем без возврата фокуса
  const desktop = window.matchMedia('(min-width: 861px)');
  const onBreakpoint = function (event) {
    if (event.matches) closeMenu(false);
  };
  if (desktop.addEventListener) desktop.addEventListener('change', onBreakpoint);
  else desktop.addListener(onBreakpoint);
})();
