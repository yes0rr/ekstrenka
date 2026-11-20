/* Правка вопросов видеотеста преподавателем.
   Один запрос за списком, дальше каждая карточка правится и сохраняется отдельно.
   Песочница «как проверится» обращается к тому же матчеру, что и настоящий ответ. */
(function () {
  'use strict';

  var state = { items: [], byId: {} };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function api(url, options) {
    return fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}))
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(t || r.status); });
        return r.json();
      });
  }

  function form(url, data) {
    return api(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  }

  var VERDICT = {
    correct: 'Верно',
    partial: 'Принято частично',
    wrong: 'Неверно',
    retry: 'Не разобрал — попросит сказать иначе'
  };

  function card(item) {
    var wrap = el('div', 'panel quiz-edit-card');
    wrap.dataset.id = item.id;

    var head = el('div', 'quiz-edit-head');
    var badge = el('span', 'quiz-edit-badge',
      (item.section === 'diagnostics' ? 'Диагностика' : 'Лечение') + ' · ' + item.scenario_title);
    head.appendChild(badge);
    if (item.edited) head.appendChild(el('span', 'quiz-edit-flag', 'изменён'));
    if (item.hidden) head.appendChild(el('span', 'quiz-edit-flag is-off', 'скрыт из тестов'));
    head.appendChild(el('span', 'muted small', '№ ' + item.id));
    wrap.appendChild(head);

    var grid = el('div', 'quiz-edit-grid');

    function field(label, name, value, multiline, hint) {
      var box = el('label', 'quiz-edit-field');
      box.appendChild(el('span', 'muted small', label));
      var input = document.createElement(multiline ? 'textarea' : 'input');
      if (!multiline) input.type = 'text';
      input.name = name;
      input.value = value || '';
      if (multiline) input.rows = 2;
      box.appendChild(input);
      if (hint) box.appendChild(el('span', 'quiz-edit-hint muted small', hint));
      grid.appendChild(box);
      return input;
    }

    field('Вопрос', 'text', item.text, true);
    field('Эталонный ответ (как надо)', 'reference', item.reference, true);
    field('Ключевые слова: группы через «|», синонимы через запятую', 'keys', item.keys, true,
      'Например: эпинефрин, адреналин | в/м, внутримышечно | бедро');
    field('Пояснение (видно после ответа)', 'explain', item.explain, true);
    wrap.appendChild(grid);

    var actions = el('div', 'quiz-edit-actions');
    var save = el('button', 'btn small', 'Сохранить');
    save.type = 'button';
    var reset = el('button', 'btn ghost small', 'Вернуть исходный');
    reset.type = 'button';
    var hide = el('label', 'muted small quiz-edit-hide');
    var hideBox = document.createElement('input');
    hideBox.type = 'checkbox';
    hideBox.checked = !!item.hidden;
    hide.appendChild(hideBox);
    hide.appendChild(document.createTextNode(' убрать из тестов'));
    var status = el('span', 'quiz-edit-status muted small');

    actions.appendChild(save);
    actions.appendChild(reset);
    actions.appendChild(hide);
    actions.appendChild(status);
    wrap.appendChild(actions);

    // песочница проверки ответа
    var sandbox = el('div', 'quiz-edit-sandbox');
    var sandboxInput = document.createElement('input');
    sandboxInput.type = 'text';
    sandboxInput.placeholder = 'Проверить ответ учащегося: впишите фразу и нажмите «Проверить»';
    var sandboxBtn = el('button', 'btn ghost small', 'Проверить');
    sandboxBtn.type = 'button';
    var sandboxOut = el('div', 'quiz-edit-result muted small');
    sandbox.appendChild(sandboxInput);
    sandbox.appendChild(sandboxBtn);
    sandbox.appendChild(sandboxOut);
    wrap.appendChild(sandbox);

    function collect() {
      return {
        text: wrap.querySelector('[name=text]').value,
        reference: wrap.querySelector('[name=reference]').value,
        keys: wrap.querySelector('[name=keys]').value,
        explain: wrap.querySelector('[name=explain]').value,
        hidden: hideBox.checked
      };
    }

    save.addEventListener('click', function () {
      status.textContent = 'Сохраняю…';
      form('/api/quiz-edit/' + item.id, collect()).then(function (data) {
        item = data.question;
        state.byId[item.id] = item;
        status.textContent = 'Сохранено ✓';
        wrap.classList.add('is-edited');
        setTimeout(function () { status.textContent = ''; }, 2500);
        refreshCounter();
      }).catch(function (e) {
        status.textContent = 'Ошибка: ' + e.message;
      });
    });

    reset.addEventListener('click', function () {
      if (!window.confirm('Вернуть исходный вопрос из банка?')) return;
      api('/api/quiz-edit/' + item.id, { method: 'DELETE' }).then(function () {
        status.textContent = 'Возвращён исходный';
        return api('/api/quiz-edit/questions');
      }).then(function (data) {
        state.items = data.items;
        state.byId = {};
        data.items.forEach(function (it) { state.byId[it.id] = it; });
        render();
      }).catch(function (e) { status.textContent = 'Ошибка: ' + e.message; });
    });

    sandboxBtn.addEventListener('click', function () {
      var answer = sandboxInput.value.trim();
      if (!answer) return;
      var url = '/api/quiz-edit/check/' + item.id + '?answer=' + encodeURIComponent(answer);
      api(url).then(function (r) {
        var text = (VERDICT[r.verdict] || r.verdict) +
          ' · покрытие ' + Math.round((r.coverage || 0) * 100) + ' %';
        if (r.matched && r.matched.length) text += ' · распознано: ' + r.matched.join(', ');
        if (r.missed && r.missed.length) text += ' · не хватило: ' + r.missed.join(', ');
        if (r.blocked && r.blocked.length) text += ' · запрещено: ' + r.blocked.join(', ');
        sandboxOut.textContent = text;
        sandboxOut.className = 'quiz-edit-result small is-' + r.verdict;
      }).catch(function (e) { sandboxOut.textContent = 'Ошибка: ' + e.message; });
    });

    return wrap;
  }

  function matches(item) {
    var section = document.getElementById('editSection').value;
    var scenario = document.getElementById('editScenario').value;
    var search = document.getElementById('editSearch').value.trim().toLowerCase();
    var onlyChanged = document.getElementById('editOnlyChanged').checked;
    if (section && item.section !== section) return false;
    if (scenario && String(item.scenario) !== scenario) return false;
    if (onlyChanged && !item.edited) return false;
    if (search) {
      var hay = (item.text + ' ' + item.reference + ' ' + item.keys).toLowerCase();
      if (hay.indexOf(search) === -1) return false;
    }
    return true;
  }

  function render() {
    var list = document.getElementById('editList');
    var empty = document.getElementById('editEmpty');
    if (!list) return;
    list.innerHTML = '';
    var shown = state.items.filter(matches);
    shown.forEach(function (item) { list.appendChild(card(item)); });
    empty.hidden = shown.length > 0;
    refreshCounter(shown.length);
  }

  function refreshCounter(shown) {
    var counter = document.getElementById('editCounter');
    if (!counter) return;
    var changed = state.items.filter(function (i) { return i.edited; }).length;
    var total = shown === undefined ? state.items.filter(matches).length : shown;
    counter.textContent = 'показано ' + total + ' из ' + state.items.length +
      ' · изменено ' + changed;
  }

  function fillScenarios() {
    var select = document.getElementById('editScenario');
    if (!select) return;
    var seen = {};
    state.items.forEach(function (item) {
      if (seen[item.scenario]) return;
      seen[item.scenario] = true;
      var option = document.createElement('option');
      option.value = String(item.scenario);
      option.textContent = item.scenario_title;
      select.appendChild(option);
    });
  }

  function init() {
    if (!document.getElementById('editList')) return;
    api('/api/quiz-edit/questions').then(function (data) {
      state.items = data.items || [];
      data.items.forEach(function (it) { state.byId[it.id] = it; });
      fillScenarios();
      render();
      ['editSection', 'editScenario', 'editSearch', 'editOnlyChanged'].forEach(function (id) {
        var node = document.getElementById(id);
        if (node) node.addEventListener('input', render);
        if (node) node.addEventListener('change', render);
      });
    }).catch(function (e) {
      document.getElementById('editList').innerHTML =
        '<div class="alert error">Не удалось загрузить вопросы: ' + e.message + '</div>';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
