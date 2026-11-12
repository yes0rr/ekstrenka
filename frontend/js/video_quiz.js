/* Видеотест: разделы → заход → ответы → итог.
 *
 * Правила:
 *  1) один заход = одна запись в истории (итог сохраняет сервер по run_id,
 *     повторное «завершить» возвращает уже сохранённое);
 *  2) «обучение» — варианты и вердикт сразу; «зачёт» — вариантов нет: ответ
 *     вводится текстом или голосом, вердикт и разбор — в конце;
 *  3) голос — через сервер (Whisper) или встроенный Web Speech, см. video_voice.js;
 *  4) нераспознанный ответ в зачёте не засчитывается как ошибка — просим повторить.
 */

(function () {
  var state = {
    sections: [], run: null, answers: {}, mode: 'training', finished: false,
    voiceMode: 'none', voices: []
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function lang() {
    var stored = null;
    try { stored = localStorage.getItem('ekstrenka.lang'); } catch (e) {}
    return stored === 'en' ? 'en' : 'ru';
  }

  function t(text) {
    if (lang() === 'en' && window.I18N) return window.I18N.translate(text) || text;
    return text;
  }

  async function api(url, options) {
    const response = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
    if (!response.ok) {
      let message = 'Ошибка ' + response.status;
      try { message = (await response.json()).detail || message; } catch (e) {}
      throw new Error(message);
    }
    return response.json();
  }

  function post(url, body) {
    return api(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  /* ---------------------------- каталог разделов ---------------------------- */

  function renderCatalog() {
    const catalog = document.getElementById('catalog');
    if (!catalog) return;
    catalog.innerHTML = '';
    state.sections.forEach(function (section) {
      const card = el('button', 'quiz-tile');
      card.type = 'button';
      card.dataset.section = section.key;  // по этому атрибуту удобно и тестировать, и стилизовать

      const cover = el('div', 'quiz-tile-cover');
      const img = document.createElement('img');
      img.src = '/static/media/quiz/' + section.cover + '.jpg';
      img.alt = '';
      img.loading = 'lazy';
      cover.appendChild(img);
      const parts = [];
      if (section.own && section.own < section.run_size) parts.push(t('по теме:') + ' ' + section.own);
      cover.appendChild(el('span', 'quiz-tile-badge', section.run_size + ' ' + t('вопросов')));
      card.appendChild(cover);

      const body = el('div', 'quiz-tile-body');
      body.appendChild(el('div', 'quiz-tile-title', section.title));
      body.appendChild(el('div', 'quiz-tile-desc muted small', section.description));
      if (parts.length) body.appendChild(el('div', 'quiz-tile-meta muted small', parts.join(' · ')));
      body.appendChild(el('span', 'quiz-tile-start',
        state.mode === 'training' ? t('Начать обучение') : t('Начать зачёт')));
      card.appendChild(body);

      card.addEventListener('click', function () { startRun(section.key); });
      catalog.appendChild(card);
    });
  }

  /* ---------------------------- заход ---------------------------- */

  async function startRun(sectionKey) {
    try {
      const data = await post('/api/video-quiz/start',
        { section: sectionKey, mode: state.mode, lang: lang() });
      state.run = data;
      state.answers = {};
      state.finished = false;
      state.voices.forEach(function (v) { if (v && v.destroy) v.destroy(); });
      state.voices = [];
      document.getElementById('catalog').hidden = true;
      document.getElementById('runArea').hidden = false;
      document.getElementById('resultPanel').hidden = true;
      const section = state.sections.find(function (s) { return s.key === sectionKey; });
      document.getElementById('runTitle').textContent =
        (section ? section.title : '') + ' · ' +
        (data.mode === 'training' ? t('обучение') : t('зачёт'));
      document.getElementById('modeBadge').textContent =
        data.mode === 'training' ? t('Обучение') : t('Зачёт');
      document.getElementById('modeBadge').className =
        'run-mode-badge ' + (data.mode === 'training' ? 'is-training' : 'is-testing');
      document.getElementById('keyHint').hidden = data.mode === 'testing';
      document.getElementById('finishBtn').disabled = false;
      document.getElementById('finishBtn').textContent = t('Завершить и увидеть разбор');
      renderQuestions();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
      alert(error.message);
    }
  }

  function renderQuestions() {
    const list = document.getElementById('quizList');
    list.innerHTML = '';
    state.voices = [];
    state.run.items.forEach(function (q, index) { list.appendChild(renderQuestion(q, index)); });
    updateProgress();
  }

  function renderQuestion(q, index) {
    const card = el('div', 'panel quiz-card');
    card.dataset.id = q.id;

    const head = el('div', 'quiz-head');
    head.appendChild(el('span', 'quiz-num', t('Вопрос ' + (index + 1) + ' из ' + state.run.total)));
    head.appendChild(el('span', 'quiz-title', q.title));
    card.appendChild(head);

    const video = document.createElement('video');
    video.className = 'quiz-video';
    video.src = '/static/media/quiz/' + q.clip + '.mp4';
    video.poster = '/static/media/quiz/' + q.clip + '.jpg';
    video.controls = true;
    video.playsInline = true;
    video.preload = 'none';
    video.muted = true;
    card.appendChild(video);

    card.appendChild(el('p', 'quiz-question', q.question));

    if (state.run.mode === 'training') {
      const options = el('div', 'quiz-options');
      q.options.forEach(function (text, i) {
        const label = el('label', 'option quiz-option');
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'q' + q.id;
        radio.value = String(i);
        radio.addEventListener('change', function () { sendAnswer(q, card, { answer: i }); });
        label.appendChild(radio);
        label.appendChild(el('span', 'opt-key', String(i + 1)));
        label.appendChild(el('span', '', text));
        options.appendChild(label);
      });
      card.appendChild(options);
    } else {
      /* зачёт: вариантов нет — только поле ввода и голос */
      const box = el('div', 'quiz-free');
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'quiz-free-input';
      input.placeholder = t('Ваш ответ словами, например «тридцать на два»');
      input.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        sendAnswer(q, card, { text: input.value.trim() }, input);
      });
      box.appendChild(input);
      const send = el('button', 'btn small', t('Ответить'));
      send.type = 'button';
      send.addEventListener('click', function () { sendAnswer(q, card, { text: input.value.trim() }, input); });
      box.appendChild(send);
      card.appendChild(box);
    }

    if (state.voiceMode !== 'none') card.appendChild(renderVoice(q, card));

    const feedback = el('div', 'quiz-feedback');
    feedback.hidden = true;
    card.appendChild(feedback);
    return card;
  }

  /* ---------------------------- голос ---------------------------- */

  function renderVoice(q, card) {
    const box = el('div', 'quiz-voice');
    const voice = window.VideoVoice.create(box, {
      t: t,
      lang: lang,
      label: function () { return t('Ответить голосом'); },
      onText: function (text, status) {
        const input = card.querySelector('.quiz-free-input');
        if (input && !input.value) input.value = text;
        sendAnswer(q, card, { text: text }, input, status);
      },
    }, state.voiceMode);
    state.voices.push(voice);
    return box;
  }

  /* ---------------------------- ответы ---------------------------- */

  async function sendAnswer(q, card, payload, input, status) {
    if (!state.run || state.finished) return;
    const feedback = card.querySelector('.quiz-feedback');
    if (payload.text !== undefined && !payload.text) {
      feedback.hidden = false;
      feedback.textContent = t('Введите ответ или скажите его голосом.');
      return;
    }
    try {
      const data = await post('/api/video-quiz/answer',
        Object.assign({ run_id: state.run.run_id, question_id: q.id }, payload));

      if (data.retry) {
        /* текст не сопоставился с вариантами — ответ не засчитываем, просим повторить */
        feedback.hidden = false;
        feedback.innerHTML = '';
        feedback.appendChild(el('div', 'quiz-verdict pending',
          t('Не понял ответ — сформулируйте иначе или скажите короче. Ответ не засчитан.')));
        feedback.appendChild(el('div', 'quiz-source', t('Услышано:') + ' ' + data.text));
        if (status) status.textContent = t('Сказанное не совпало с ответом — попробуйте иначе.');
        return;
      }

      state.answers[q.id] = true;
      updateProgress();
      if (data.accepted) {
        showPending(card);
        if (status) status.textContent = t('Ответ принят — вердикт будет в конце');
        if (input) input.disabled = true;
        if (card.querySelector('.quiz-free')) {
          const send = card.querySelector('.quiz-free button');
          if (send) send.disabled = true;
        }
      } else {
        showVerdict(card, data, typeof payload.answer === 'number' ? payload.answer : -1);
        // ответ уже принят — варианты блокируем, иначе после вердикта можно выбрать правильный
        card.querySelectorAll('.quiz-option input').forEach(function (radio) { radio.disabled = true; });
        if (input) input.disabled = true;
        if (status) status.textContent = t('Услышано:') + ' ' + (payload.text || '') + ' · ' +
          (data.correct ? t('Верно') : t('Неверно'));
      }
    } catch (error) {
      feedback.hidden = false;
      feedback.textContent = error.message;
    }
  }

  function showPending(card) {
    const feedback = card.querySelector('.quiz-feedback');
    feedback.hidden = false;
    feedback.innerHTML = '';
    feedback.appendChild(el('div', 'quiz-verdict pending', t('Ответ принят — вердикт будет в конце')));
    card.classList.add('is-answered');
  }

  /* вердикт в обучении: показываем и номер, и сам текст правильного ответа */
  function showVerdict(card, data, chosen) {
    const feedback = card.querySelector('.quiz-feedback');
    feedback.hidden = false;
    feedback.innerHTML = '';
    card.classList.toggle('is-correct', data.correct);
    card.classList.toggle('is-wrong', !data.correct);
    card.classList.add('is-answered');
    feedback.appendChild(el('div', 'quiz-verdict ' + (data.correct ? 'ok' : 'bad'),
      data.correct ? t('Верно') : t('Неверно — правильный ответ:') + ' ' + data.correct_text));
    feedback.appendChild(el('div', 'quiz-explain', data.explain));
    feedback.appendChild(el('div', 'quiz-source', t('Паспорт станции:') + ' ' + data.checklist));
    card.querySelectorAll('.quiz-option').forEach(function (label, i) {
      label.classList.toggle('is-answer', i === data.correct_index);
      // выбранный, но неверный вариант помечаем красным — видно, где ошибся
      label.classList.toggle('is-choice-wrong', !data.correct && i === chosen);
    });
  }

  function updateProgress() {
    if (!state.run) return;
    const answered = Object.keys(state.answers).length;
    document.getElementById('answeredCount').textContent = answered;
    document.getElementById('totalCount').textContent = state.run.total;
    document.getElementById('progressFill').style.width =
      Math.round(answered * 100 / state.run.total) + '%';
    document.getElementById('finishBtn').disabled = answered === 0 || state.finished;
  }

  /* ---------------------------- итог ---------------------------- */

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
      document.querySelectorAll('.quiz-free-input').forEach(function (i) { i.disabled = true; });
    } catch (error) {
      alert(error.message);
      btn.textContent = t('Завершить и увидеть разбор');
      btn.disabled = false;
    }
  }

  function showResult(result) {
    const panel = document.getElementById('resultPanel');
    panel.hidden = false;
    document.getElementById('scorePercent').textContent = result.percent;
    const verdictBox = document.getElementById('scoreVerdict');
    verdictBox.innerHTML = '';
    appendVerdict(verdictBox, result.verdict_text);
    document.getElementById('scoreDetail').textContent =
      t('Верных ответов: ' + result.score + ' из ' + result.total);

    result.details.forEach(function (item) {
      const card = document.querySelector('.quiz-card[data-id="' + item.id + '"]');
      if (!card) return;
      const feedback = card.querySelector('.quiz-feedback');
      feedback.hidden = false;
      feedback.innerHTML = '';
      const right = item.options[item.correct_index];
      let verdictText;
      if (item.chosen < 0) verdictText = t('Ответа нет — правильный ответ:') + ' ' + right;
      else if (item.correct) verdictText = t('Верно');
      else verdictText = t('Неверно — правильный ответ:') + ' ' + right;
      feedback.appendChild(el('div', 'quiz-verdict ' + (item.correct ? 'ok' : 'bad'), verdictText));
      if (item.text) feedback.appendChild(el('div', 'quiz-source', t('Ваш ответ:') + ' ' + item.text));
      feedback.appendChild(el('div', 'quiz-explain', item.explain));
      feedback.appendChild(el('div', 'quiz-source', t('Паспорт станции:') + ' ' + item.checklist));
      card.querySelectorAll('.quiz-option').forEach(function (label, i) {
        label.classList.toggle('is-answer', i === item.correct_index);
        label.classList.toggle('is-chosen', i === item.chosen);
      });
    });
    panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  /* вердикт: слова про инструкцию превращаем в ссылку */
  function appendVerdict(box, text) {
    const needles = ['инструкции по ЭМП', 'инструкцией по ЭМП', 'инструкция по ЭМП',
      'the emergency care guide', 'emergency care guide'];
    const needle = needles.find(function (n) { return text.indexOf(n) >= 0; });
    if (!needle) { box.textContent = text; return; }
    const parts = text.split(needle);
    box.appendChild(document.createTextNode(parts[0]));
    const link = document.createElement('a');
    link.href = '/instruction/emergency-help';
    link.textContent = needle;
    link.className = 'quiz-verdict-link';
    box.appendChild(link);
    box.appendChild(document.createTextNode(parts.slice(1).join(needle)));
  }

  function backToCatalog() {
    state.voices.forEach(function (v) { if (v && v.destroy) v.destroy(); });
    state.voices = [];
    state.run = null;
    state.finished = false;
    state.answers = {};
    document.getElementById('runArea').hidden = true;
    document.getElementById('catalog').hidden = false;
    renderCatalog();
    loadHistory();
  }

  /* ---------------------------- история ---------------------------- */

  async function loadHistory() {
    try {
      const data = await api('/api/video-quiz/results');
      const panel = document.getElementById('historyPanel');
      const list = document.getElementById('historyList');
      if (!data.items || !data.items.length) { panel.hidden = true; return; }
      list.innerHTML = '';
      data.items.forEach(function (row) {
        const line = el('div', 'quiz-history-row');
        const left = el('div', 'quiz-history-left');
        const when = row.finished_at
          ? new Date(row.finished_at).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU',
            { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
          : '';
        left.appendChild(el('span', '', when));
        left.appendChild(el('span', 'quiz-history-mode', row.mode === 'testing' ? t('зачёт') : t('обучение')));
        line.appendChild(left);
        line.appendChild(el('b', '', row.percent + ' %'));
        list.appendChild(line);
      });
      panel.hidden = false;
    } catch (e) { /* история не критична */ }
  }

  async function loadSections() {
    const catalog = document.getElementById('catalog');
    try {
      const data = await api('/api/video-quiz/sections?lang=' + lang());
      state.sections = data.items;
      catalog.hidden = false;
      renderCatalog();
      loadHistory();
    } catch (error) {
      catalog.innerHTML = '<div class="alert error">Не удалось загрузить разделы: ' + error.message + '</div>';
    }
  }

  async function loadVoiceMode() {
    let serverAvailable = false;
    try {
      const data = await api('/api/video-quiz/voice/status');
      serverAvailable = Boolean(data.server && data.server.available);
    } catch (e) { /* если статус не отдался — считаем, что сервера нет */ }
    state.voiceMode = window.VideoVoice ? window.VideoVoice.pick(serverAvailable) : 'none';
    const hint = document.getElementById('voiceHint');
    if (!hint) return;
    if (!window.VideoVoice || !window.VideoVoice.secure()) {
      hint.textContent = t('Голосовой ответ работает только по https — на этом адресе он недоступен. Введите ответ текстом.');
    } else if (state.voiceMode === 'none') {
      hint.textContent = t('Голосовой ответ в этом браузере недоступен. Введите ответ текстом.');
    } else if (state.voiceMode === 'server') {
      hint.textContent = t('Голосовой ответ: нажмите кнопку и говорите — запись распознаётся на нашем сервере и никуда не сохраняется.');
    } else {
      hint.textContent = t('Голосовой ответ: распознаёт браузер (Chrome, Edge). Если не работает — включите распознавание на сервере.');
    }
  }

  /* ---------------------------- режим ---------------------------- */

  function applyMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.seg').forEach(function (button) {
      const on = button.dataset.mode === mode;
      button.classList.toggle('is-on', on);
      button.setAttribute('aria-selected', on ? 'true' : 'false');
      const mark = button.querySelector('.seg-check');
      if (mark) mark.textContent = on ? '✓' : '';
    });
    const hint = document.getElementById('modeHint');
    if (hint) {
      hint.textContent = mode === 'training'
        ? t('Режим «Обучение»: варианты ответа и вердикт сразу.')
        : t('Режим «Зачёт»: вариантов не будет — отвечайте текстом или голосом.');
    }
    if (state.run) backToCatalog();
    else renderCatalog();
    /* прокручиваем к выбору раздела: там начинается сам тест */
    const catalog = document.getElementById('catalog');
    if (catalog) catalog.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function bindKeys() {
    document.addEventListener('keydown', function (event) {
      if (!state.run || state.finished) return;
      const tag = (event.target.tagName || '').toLowerCase();
      const typing = tag === 'input' || tag === 'textarea' || tag === 'select' || event.target.isContentEditable;
      if (typing) return;  // в поле ответа цифры — это текст ответа, а не выбор варианта
      if (event.key === 'Enter') {
        // на кнопке Enter уже срабатывает сам — второй раз не перехватываем
        if (tag !== 'button' && !document.getElementById('finishBtn').disabled) finishQuiz();
        return;
      }
      if (state.run.mode !== 'training') return;
      const num = parseInt(event.key, 10);
      if (!(num >= 1 && num <= 4)) return;
      const next = state.run.items.find(function (q) { return !state.answers[q.id]; });
      if (!next) return;
      const card = document.querySelector('.quiz-card[data-id="' + next.id + '"]');
      const label = card && card.querySelectorAll('.quiz-option')[num - 1];
      if (!label) return;
      label.querySelector('input').checked = true;
      label.querySelector('input').dispatchEvent(new Event('change'));
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('finishBtn').addEventListener('click', finishQuiz);
    document.getElementById('backBtn').addEventListener('click', backToCatalog);
    document.getElementById('restartBtn').addEventListener('click', backToCatalog);
    document.querySelectorAll('.seg').forEach(function (button) {
      button.addEventListener('click', function () { applyMode(button.dataset.mode); });
    });
    document.addEventListener('ekstrenka:lang', function () { backToCatalog(); loadSections(); });
    bindKeys();
    applyMode('training');
    loadVoiceMode();
    loadSections();
  });
})();
