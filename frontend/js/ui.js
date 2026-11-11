/* Виджет в правом нижнем углу: палитра интерфейса и язык RU/EN.
 *
 * Что делает:
 *  1) ставит html[data-theme] (dark/light) и html[data-accent] (blue/emerald/violet/amber);
 *  2) запоминает выбор в localStorage, чтобы он сохранялся между страницами;
 *  3) переключает язык интерфейса через I18N (см. i18n.js).
 *
 * Сами цвета лежат в style.css, здесь только переключатели.
 */
(function () {
  "use strict";

  var KEY_THEME = "ekstrenka.theme";
  var KEY_ACCENT = "ekstrenka.accent";
  var KEY_LANG = "ekstrenka.lang";

  var PALETTES = [
    { id: "blue-dark", theme: "dark", accent: "blue", title: "Тёмная синяя", c1: "#0d1117", c2: "#4f8cff" },
    { id: "emerald-dark", theme: "dark", accent: "emerald", title: "Тёмная изумрудная", c1: "#0d1117", c2: "#12a97a" },
    { id: "violet-dark", theme: "dark", accent: "violet", title: "Тёмная фиолетовая", c1: "#0d1117", c2: "#7c5cff" },
    { id: "blue-light", theme: "light", accent: "blue", title: "Светлая синяя", c1: "#f6f7fb", c2: "#2f6fe4" },
    { id: "emerald-light", theme: "light", accent: "emerald", title: "Светлая изумрудная", c1: "#f6f7fb", c2: "#0e8f68" },
    { id: "amber-light", theme: "light", accent: "amber", title: "Светлая тёплая", c1: "#f6f7fb", c2: "#c96a05" },
    { id: "violet-light", theme: "light", accent: "violet", title: "Светлая фиолетовая", c1: "#f6f7fb", c2: "#6242e8" },
    { id: "graphite-dark", theme: "dark", accent: "graphite", title: "Тёмная графитовая", c1: "#0d1117", c2: "#9aa7b8" }
  ];

  // подписи виджета: RU -> EN (виджет должен переводиться сам себя)
  var T = {
    "Оформление и язык": "Appearance and language",
    "Палитра": "Palette",
    "Язык": "Language",
    "Выбор запоминается в этом браузере": "Your choice is saved in this browser",
    "Тёмная синяя": "Dark blue",
    "Тёмная изумрудная": "Dark emerald",
    "Тёмная фиолетовая": "Dark violet",
    "Тёмная графитовая": "Dark graphite",
    "Светлая синяя": "Light blue",
    "Светлая изумрудная": "Light emerald",
    "Светлая тёплая": "Light warm",
    "Светлая фиолетовая": "Light violet"
  };
  function t(ru) {
    var lang = read(KEY_LANG, "ru");
    return lang === "en" ? (T[ru] || ru) : ru;
  }

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* приватный режим */ }
  }
  function read(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
  }

  function applyPalette(theme, accent) {
    var html = document.documentElement;
    html.setAttribute("data-theme", theme);
    html.setAttribute("data-accent", accent);
    store(KEY_THEME, theme);
    store(KEY_ACCENT, accent);
  }

  function applyLang(lang) {
    store(KEY_LANG, lang);
    if (window.I18N) {
      window.I18N.apply(lang);
    } else {
      document.documentElement.lang = lang;
    }
    relabel();
    markActive(lang);
    // страницы, которым нужен серверный текст (видеотест), перезапрашивают данные
    document.dispatchEvent(new CustomEvent("ekstrenka:lang", { detail: { lang: lang } }));
  }

  // перерисовать подписи виджета под текущий язык
  function relabel() {
    var btn = document.getElementById("uiToggle");
    if (btn) {
      btn.title = t("Оформление и язык");
      btn.setAttribute("aria-label", t("Оформление и язык"));
    }
    document.querySelectorAll(".ui-menu .ui-title").forEach(function (el) {
      var ru = el.dataset.ru;
      if (ru) el.textContent = t(ru);
    });
    document.querySelectorAll(".sw").forEach(function (el) {
      var ru = el.dataset.ru;
      if (ru) {
        el.title = t(ru);
        el.setAttribute("aria-label", t(ru));
      }
    });
    var hint = document.querySelector(".ui-hint");
    if (hint && hint.dataset.ru) hint.textContent = t(hint.dataset.ru);
  }

  function markActive(lang) {
    document.querySelectorAll(".ui-lang button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.lang === lang);
    });
    var theme = document.documentElement.getAttribute("data-theme") || "dark";
    var accent = document.documentElement.getAttribute("data-accent") || "blue";
    document.querySelectorAll(".sw").forEach(function (b) {
      b.classList.toggle("active", b.dataset.id === theme + "-" + accent);
    });
  }

  function build() {
    var wrap = document.createElement("div");
    wrap.className = "ui-tools";

    var btn = document.createElement("button");
    btn.className = "ui-btn";
    btn.type = "button";
    btn.id = "uiToggle";
    btn.setAttribute("aria-label", "Оформление и язык");
    btn.title = "Оформление и язык";
    btn.textContent = "🎨";

    var menu = document.createElement("div");
    menu.className = "ui-menu";
    menu.id = "uiMenu";
    menu.hidden = true;

    var t1 = document.createElement("div");
    t1.className = "ui-title";
    t1.dataset.ru = "Палитра";
    t1.textContent = "Палитра";
    menu.appendChild(t1);

    var swatches = document.createElement("div");
    swatches.className = "ui-swatches";
    PALETTES.forEach(function (p) {
      var sw = document.createElement("button");
      sw.type = "button";
      sw.className = "sw";
      sw.dataset.id = p.id;
      sw.dataset.theme = p.theme;
      sw.dataset.accent = p.accent;
      sw.dataset.ru = p.title;
      sw.title = p.title;
      sw.setAttribute("aria-label", p.title);
      sw.style.setProperty("--c1", p.c1);
      sw.style.setProperty("--c2", p.c2);
      sw.addEventListener("click", function () {
        applyPalette(p.theme, p.accent);
        markActive(read(KEY_LANG, "ru"));
      });
      swatches.appendChild(sw);
    });
    menu.appendChild(swatches);

    var t2 = document.createElement("div");
    t2.className = "ui-title";
    t2.dataset.ru = "Язык";
    t2.textContent = "Язык";
    menu.appendChild(t2);

    var langs = document.createElement("div");
    langs.className = "ui-lang";
    [["ru", "Русский"], ["en", "English"]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.dataset.lang = pair[0];
      b.textContent = pair[0].toUpperCase();
      b.title = pair[1];
      b.addEventListener("click", function () { applyLang(pair[0]); });
      langs.appendChild(b);
    });
    menu.appendChild(langs);

    var hint = document.createElement("div");
    hint.className = "ui-hint";
    hint.dataset.ru = "Выбор запоминается в этом браузере";
    hint.textContent = "Выбор запоминается в этом браузере";
    menu.appendChild(hint);

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
    });
    document.addEventListener("click", function (e) {
      if (!menu.hidden && !wrap.contains(e.target)) menu.hidden = true;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") menu.hidden = true;
    });

    wrap.appendChild(btn);
    wrap.appendChild(menu);
    document.body.appendChild(wrap);
    markActive(read(KEY_LANG, "ru"));
  }

  function init() {
    // тема уже применена inline-скриптом в <head>, здесь только виджет и язык
    build();
    var lang = read(KEY_LANG, "ru");
    if (lang === "en") applyLang("en");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
