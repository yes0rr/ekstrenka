/* Видеотест «Экстренка» — v24.
 *
 * Что изменилось против прежнего варианта:
 *   1) Два раздела: «Диагностика» и «Лечение». В каждом девять тестов по сценариям
 *      станции и один общий тест по всем вопросам раздела.
 *   2) Вариантов ответа нет ни в обучении, ни в зачёте: учащийся пишет ответ словами
 *      или проговаривает его, сервер сравнивает ответ с эталоном по смыслу.
 *   3) Видео пока нет — на месте фрагмента пустое окно-заглушка; клипы вставим позже.
 */
(function () {
  'use strict';

  const state = {
    mode: 'training',
    lang: 'ru',
    sections: [],
    run: null,          // {run_id, mode, test, test_title, total, items}
    answers: {},
    testKey: null,      // какой тест открыт (для подсветки карточки)
    finished: false,
    voices: [],
  };

  /* ---------- мелкие помощники ---------- */

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function lang() {
    return (window.localStorage.getItem('ekstrenka.lang') || 'ru') === 'en' ? 'en' : 'ru';
  }

  function t(text) {
    try {
      if (window.I18N && typeof window.I18N.t === 'function') return window.I18N.t(text);
    } catch (error) { /* без словаря показываем как есть */ }
    return text;
  }

  async function api(url, options) {
    const response = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, options));
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.detail || ('Ошибка ' + response.status));
    return data;
  }

  function post(url, body) {
    return api(url, { method: 'POST', body: JSON.stringify(body) });
  }

  /* «5 вопросов», «45 вопросов», «1 вопрос» */
  function questionsWord(count) {
    if (lang() === 'en') return count === 1 ? 'question' : 'questions';
    const ten = count % 100;
    const one = count % 10;
    if (ten >= 11 && ten <= 14) return 'вопросов';
    if (one === 1) return 'вопрос';
    if (one >= 2 && one <= 4) return 'вопроса';
    return 'вопросов';
  }

  /* ---------- режим ---------- */

  function setupModes() {
    const panel = document.getElementById('modePanel');
    if (!panel) return;
    const buttons = panel.querySelectorAll('.seg');
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        state.mode = button.dataset.mode;
        buttons.forEach(function (other) {
          const on = other === button;
          other.classList.toggle('is-on', on);
          other.setAttribute('aria-selected', on ? 'true' : 'false');
          const check = other.querySelector('.seg-check');
          if (check) check.textContent = on ? '✓' : '';
        });
        const hint = document.getElementById('modeHint');
        if (hint) {
          hint.textContent = state.mode === 'training'
            ? t('Режим «Обучение»: пишете или говорите ответ — сразу видно, что верно, и эталон.')
            : t('Режим «Зачёт»: ответы проверяются, но вердикт и эталоны — только в конце.');
        }
      });
    });
  }

  /* ---------- каталог: разделы и тесты ---------- */

  function renderCatalog() {
    const catalog = document.getElementById('catalog');
    if (!catalog) return;
    catalog.innerHTML = '';
    state.sections.forEach(function (section) {
      const block = el('div', 'quiz-section');
      const head = el('div', 'quiz-section-head');
      head.appendChild(el('h2', 'quiz-section-title', section.title));
      head.appendChild(el('p', 'muted small', section.description));
      block.appendChild(head);

      // тесты группируются по занятиям из таблиц преподавателя:
      // 2 — ОДН/комы, 3 — ОКС/шоки, 4 — зачёт по всем темам
      const groups = {};
      (section.tests || []).forEach(function (test) {
        const lesson = test.lesson || 4;
        (groups[lesson] = groups[lesson] || []).push(test);
      });
      Object.keys(groups).map(Number).sort(function (a, b) { return a - b; })
        .forEach(function (lesson) {
          const group = el('div', 'quiz-lesson');
          group.appendChild(el('div', 'quiz-lesson-title muted small',
            lesson === 4 ? t('Занятие 4 · Зачёт: все темы') : t('Занятие ') + lesson +
              (lesson === 2 ? t(' · ОДН и комы') : t(' · ОКС и шоки'))));
          const grid = el('div', 'quiz-tests');
          groups[lesson].forEach(function (test) {
            const isAll = test.key.endsWith('_all');
            const isLesson = /_lesson\d$/.test(test.key);
            const tile = el('button', 'quiz-test' + (isAll ? ' quiz-test-all' : '') +
              (isLesson ? ' quiz-test-lesson' : ''));
            tile.type = 'button';
            tile.dataset.test = test.key;
            // в заголовке уже есть «Занятие N · …» — оставляем только сценарий
            let title = String(test.title).replace(/^Занятие \d+ · [^:]+: /, '');
            if (/^Занятие \d+/.test(title)) title = t('Все вопросы раздела');
            tile.appendChild(el('span', 'quiz-test-title', title));
            tile.appendChild(el('span', 'quiz-test-meta muted small',
              (isAll ? t('Зачёт') + ' · ' : (isLesson ? t('Всё занятие') + ' · ' : '')) +
              test.count + ' ' + questionsWord(test.count)));
            tile.classList.toggle('is-active', state.testKey === test.key);
            tile.addEventListener('click', function () {
              state.testKey = test.key;
              renderCatalog();
              startRun(test.key);
            });
            grid.appendChild(tile);
          });
          group.appendChild(grid);
          block.appendChild(group);
        });
      catalog.appendChild(block);
    });
  }

  async function loadCatalog() {
    const data = await api('/api/video-quiz/sections?lang=' + lang());
    state.sections = data.sections || [];
    renderCatalog();
  }

  /* ---------- заход ---------- */

  async function startRun(testKey) {
    try {
      const data = await post('/api/video-quiz/start',
        { test: testKey, mode: state.mode, lang: lang() });
      state.run = data;
      state.answers = {};
      state.finished = false;
      state.voices.forEach(function (v) { if (v && v.destroy) v.destroy(); });
      state.voices = [];
      document.getElementById('catalog').hidden = true;
      document.getElementById('runArea').hidden = false;
      document.getElementById('resultPanel').hidden = true;
      document.getElementById('runTitle').textContent = data.test_title;
      document.getElementById('modeBadge').textContent =
        data.mode === 'training' ? t('Обучение') : t('Зачёт');
      document.getElementById('modeBadge').className =
        'run-mode-badge ' + (data.mode === 'training' ? 'is-training' : 'is-testing');
      document.getElementById('totalCount').textContent = data.total;
      document.getElementById('finishBtn').disabled = false;
      document.getElementById('finishBtn').textContent = t('Завершить и увидеть разбор');
      renderQuestions();
      updateProgress();
      scrollToRun();
    } catch (error) {
      alert(error.message);
    }
  }

  /* прокрутка к началу захода: шапка сайта закреплена, поэтому отступ задан в CSS */
  function scrollToRun() {
    const runArea = document.getElementById('runArea');
    if (!runArea) return;
    const top = runArea.getBoundingClientRect().top + window.scrollY - 76;
    window.scrollTo({ top: Math.max(top, 0), behavior: 'smooth' });
  }

  function backToCatalog() {
    document.getElementById('runArea').hidden = true;
    document.getElementById('catalog').hidden = false;
    document.getElementById('resultPanel').hidden = true;
    renderCatalog();
    const panel = document.getElementById('modePanel');
    if (panel) window.scrollTo({ top: panel.getBoundingClientRect().top + window.scrollY - 76, behavior: 'smooth' });
  }

  function updateProgress() {
    const answered = Object.keys(state.answers).length;
    const total = state.run ? state.run.total : 0;
    document.getElementById('answeredCount').textContent = answered;
    document.getElementById('totalCount').textContent = total;
    const fill = document.getElementById('progressFill');
    if (fill) fill.style.width = (total ? Math.round(answered * 100 / total) : 0) + '%';
    document.getElementById('finishBtn').disabled = answered === 0 || state.finished;
  }

  function renderQuestions() {
    const list = document.getElementById('quizList');
    list.innerHTML = '';
    state.run.items.forEach(function (item, index) {
      list.appendChild(renderQuestion(item, index));
    });
  }

  function renderQuestion(item, index) {
    const card = el('div', 'panel quiz-card');
    card.dataset.id = item.id;

    const head = el('div', 'quiz-head');
    head.appendChild(el('span', 'quiz-num', t('Вопрос ') + (index + 1) + t(' из ') + state.run.total));
    head.appendChild(el('span', 'quiz-title', item.test_title || ''));
    card.appendChild(head);

    /* Видео пока нет: пустое окно на месте будущего фрагмента */
    const frame = el('div', 'quiz-video quiz-video-empty');
    frame.appendChild(el('div', 'quiz-video-placeholder',
      t('Видео к этому вопросу появится позже')));
    card.appendChild(frame);

    card.appendChild(el('p', 'quiz-question', item.text));

    const box = el('div', 'quiz-free');
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'quiz-free-input';
    input.placeholder = t('Ваш ответ словами — можно коротко, по смыслу');
    input.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      sendAnswer(item, card, input.value.trim(), input);
    });
    box.appendChild(input);
    const send = el('button', 'btn small', t('Ответить'));
    send.type = 'button';
    send.addEventListener('click', function () { sendAnswer(item, card, input.value.trim(), input); });
    box.appendChild(send);
    card.appendChild(box);

    if (window.VideoVoice) card.appendChild(renderVoice(item, card));

    const feedback = el('div', 'quiz-feedback');
    feedback.hidden = true;
    card.appendChild(feedback);
    return card;
  }

  /* ---------- голос ---------- */

  function renderVoice(item, card) {
    const box = el('div', 'quiz-voice');
    const voice = window.VideoVoice.create(box, {
      t: t,
      lang: lang(),
      label: function () { return t('Ответить голосом'); },
      onText: function (text) {
        const input = card.querySelector('.quiz-free-input');
        if (input && !input.value) input.value = text;
        sendAnswer(item, card, text, input);
      },
    }, 'browser');
    state.voices.push(voice);
    return box;
  }

  /* ---------- ответ ---------- */

  async function sendAnswer(item, card, text, input) {
    if (!state.run || state.finished) return;
    const feedback = card.querySelector('.quiz-feedback');
    if (!text) {
      feedback.hidden = false;
      feedback.className = 'quiz-feedback is-bad';
      feedback.textContent = t('Введите ответ словами или запишите голосом.');
      return;
    }
    if (state.answers[item.id]) return;

    try {
      const result = await post('/api/video-quiz/answer',
        { run_id: state.run.run_id, question_id: item.id, text: text });

      if (result.retry) {
        feedback.hidden = false;
        feedback.className = 'quiz-feedback is-neutral';
        feedback.textContent = result.hint || t('Не разобрал ответ — сформулируйте иначе.');
        return;
      }

      state.answers[item.id] = true;
      if (input) input.disabled = true;
      const send = card.querySelector('.quiz-free .btn');
      if (send) send.disabled = true;
      card.classList.add('is-done');
      updateProgress();

      if (state.run.mode === 'testing') {
        feedback.hidden = false;
        feedback.className = 'quiz-feedback is-neutral';
        feedback.textContent = t('Ответ принят. Вердикт и эталон — в конце.');
        return;
      }

      const good = result.verdict === 'correct';
      const partial = result.verdict === 'partial';
      feedback.hidden = false;
      feedback.className = 'quiz-feedback ' + (good ? 'is-good' : (partial ? 'is-partial' : 'is-bad'));
      const head = el('div', 'quiz-verdict',
        good ? t('Верно') : (partial ? t('Принято, но сказано не всё') : t('Неверно')));
      feedback.appendChild(head);
      if (result.reference) {
        feedback.appendChild(el('div', 'quiz-reference', t('Эталон: ') + result.reference));
      }
      if (result.explain && result.explain !== result.reference) {
        feedback.appendChild(el('div', 'muted small', result.explain));
      }
    } catch (error) {
      feedback.hidden = false;
      feedback.className = 'quiz-feedback is-bad';
      feedback.textContent = error.message;
    }
  }

  /* ---------- итог ---------- */

  async function finishQuiz() {
    if (!state.run || state.finished) return;
    const btn = document.getElementById('finishBtn');
    btn.disabled = true;
    btn.textContent = t('Считаем…');
    try {
      const result = await post('/api/video-quiz/finish', { run_id: state.run.run_id });
      state.finished = true;
      state.voices.forEach(function (v) { if (v && v.destroy) v.destroy(); });
      state.voices = [];
      showResult(result);
      loadHistory();
      btn.textContent = t('Результат сохранён');
      btn.disabled = true;
    } catch (error) {
      alert(error.message);
      btn.textContent = t('Завершить и увидеть разбор');
      btn.disabled = false;
    }
  }

  function showResult(result) {
    const panel = document.getElementById('resultPanel');
    panel.hidden = false;
    document.getElementById('scorePercent').textContent = Math.round(result.percent);
    document.getElementById('scoreVerdict').textContent = result.verdict_text || '';
    document.getElementById('scoreDetail').textContent =
      t('Верных ответов: ') + result.score + t(' из ') + result.total;

    const list = document.getElementById('quizList');
    list.innerHTML = '';
    const head = el('div', 'panel quiz-review-head');
    head.appendChild(el('h3', '', t('Разбор ответов')));
    head.appendChild(el('p', 'muted small', result.test_title + ' · ' + result.mode));
    list.appendChild(head);

    (result.details || []).forEach(function (detail, index) {
      const card = el('div', 'panel quiz-card quiz-card-review ' +
        (detail.correct ? 'is-good' : 'is-bad'));
      const top = el('div', 'quiz-head');
      top.appendChild(el('span', 'quiz-num', t('Вопрос ') + (index + 1)));
      top.appendChild(el('span', 'quiz-title', detail.correct ? t('верно') : t('неверно')));
      card.appendChild(top);
      card.appendChild(el('p', 'quiz-question', detail.text));
      card.appendChild(el('div', 'quiz-answer-line',
        t('Ваш ответ: ') + (detail.answer || t('нет ответа'))));
      card.appendChild(el('div', 'quiz-reference', t('Эталон: ') + detail.reference));
      if (detail.explain && detail.explain !== detail.reference) {
        card.appendChild(el('div', 'muted small', detail.explain));
      }
      list.appendChild(card);
    });
    window.scrollTo({ top: list.getBoundingClientRect().top + window.scrollY - 76, behavior: 'smooth' });
  }

  async function loadHistory() {
    try {
      const data = await api('/api/video-quiz/results');
      const items = data.items || [];
      const panel = document.getElementById('historyPanel');
      const list = document.getElementById('historyList');
      if (!items.length) { panel.hidden = true; return; }
      panel.hidden = false;
      list.innerHTML = '';
      items.slice(0, 10).forEach(function (row) {
        const line = el('div', 'quiz-history-row');
        line.appendChild(el('span', '', row.test_title));
        line.appendChild(el('b', '', ' ' + Math.round(row.percent) + ' %'));
        list.appendChild(line);
      });
    } catch (error) { /* история не критична */ }
  }

  /* ---------- запуск ---------- */

  document.addEventListener('DOMContentLoaded', function () {
    state.lang = lang();
    setupModes();
    loadCatalog().catch(function (error) {
      const catalog = document.getElementById('catalog');
      if (catalog) catalog.innerHTML = '<div class="alert error">' + t('Не удалось загрузить тесты: ') + error.message + '</div>';
    });
    loadHistory();

    const finish = document.getElementById('finishBtn');
    if (finish) finish.addEventListener('click', finishQuiz);
    const back = document.getElementById('backBtn');
    if (back) back.addEventListener('click', backToCatalog);
    const restart = document.getElementById('restartBtn');
    if (restart) restart.addEventListener('click', function () {
      if (state.testKey) startRun(state.testKey);
    });
  });
})();
