/* Видеотест: разделы → заход → ответы → итог.
 *
 * Правила, которые здесь важны:
 *  1) один заход = одна запись в истории. Итог сохраняет сервер по run_id,
 *     повторное нажатие «завершить» возвращает уже сохранённый результат;
 *  2) «обучение» — варианты ответа и вердикт сразу; «зачёт» — вариантов нет,
 *     ответ вводится текстом или голосом, вердикт только в конце;
 *  3) голос распознаёт браузер (Chrome/Edge), на сервер уходит только текст.
 */

(function () {
  var state = { sections: [], run: null, answers: {}, mode: 'training', finished: false, voiceBusy: false };

  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var voiceSupported = Boolean(SR);
  var secure = window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1';

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
    catalog.innerHTML = '';
    state.sections.forEach(function (section) {
      const card = el('button', 'quiz-tile');
      card.type = 'button';

      const cover = el('div', 'quiz-tile-cover');
      const img = document.createElement('img');
      img.src = '/static/media/quiz/' + section.cover + '.jpg';
      img.alt = '';
      img.loading = 'lazy';
      cover.appendChild(img);
      const badge = el('span', 'quiz-tile-badge',
        t(section.run_size === section.total
          ? section.total + ' вопросов'
          : section.run_size + ' из ' + section.total));
      cover.appendChild(badge);
      card.appendChild(cover);

      const body = el('div', 'quiz-tile-body');
      body.appendChild(el('div', 'quiz-tile-title', section.title));
      body.appendChild(el('div', 'quiz-tile-desc muted small', section.description));
      const start = el('span', 'quiz-tile-start', state.mode === 'training' ? t('Начать обучение') : t('Начать зачёт'));
      body.appendChild(start);
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
      document.getElementById('catalog').hidden = true;
      document.getElementById('runArea').hidden = false;
      document.getElementById('resultPanel').hidden = true;
      const section = state.sections.find(function (s) { return s.key === sectionKey; });
      document.getElementById('runTitle').textContent =
        (section ? section.title : '') + ' · ' +
        (data.mode === 'training' ? t('обучение') : t('зачёт'));
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
      const box = el('div', 'quiz-free');
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'quiz-free-input';
      input.placeholder = t('Ваш ответ словами, например «тридцать на два»');
      input.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        sendAnswer(q, card, { text: input.value.trim() });
      });
      box.appendChild(input);
      const send = el('button', 'btn small', t('Ответить'));
      send.type = 'button';
      send.addEventListener('click', function () { sendAnswer(q, card, { text: input.value.trim() }); });
      box.appendChild(send);
      card.appendChild(box);
    }

    if (voiceSupported && secure) card.appendChild(renderVoice(q, card));

    const feedback = el('div', 'quiz-feedback');
    feedback.hidden = true;
    card.appendChild(feedback);
    return card;
  }

  /* ---------------------------- голос ---------------------------- */

  function renderVoice(q, card) {
    const box = el('div', 'quiz-voice');
    const button = el('button', 'btn ghost small quiz-mic');
    button.type = 'button';
    button.innerHTML = '<span class="mic-dot" aria-hidden="true"></span>';
    button.appendChild(el('span', '', t('Ответить голосом')));
    const status = el('div', 'quiz-voice-status muted small');

    button.addEventListener('click', function () {
      if (state.voiceBusy) {
        // второй клик по кнопке — «Стоп»: отправляем то, что успели услышать
        if (state.recognition) {
          try { state.recognition.stop(); } catch (e) {}
        }
        return;
      }
      listen(q, card, button, status);
    });

    box.appendChild(button);
    box.appendChild(status);
    return box;
  }

  function setListening(button, on) {
    button.classList.toggle('is-listening', on);
    button.querySelector('span:last-child').textContent = on ? t('Слушаю… (Стоп)') : t('Ответить голосом');
  }

  /* Слушаем до результата. Если браузер закрыл распознавание без текста —
     пробуем ещё раз (не больше двух), и только потом просим повторить.
     Раньше сообщение «не разобрал» появлялось мгновенно, до первой фразы. */
  function listen(q, card, button, status, attempt) {
    attempt = attempt || 1;
    const recognition = new SR();
    recognition.lang = lang() === 'en' ? 'en-US' : 'ru-RU';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    state.voiceBusy = true;
    state.recognition = recognition;
    setListening(button, true);
    status.textContent = t('Слушаю… скажите ответ');

    var finalText = '';
    var finished = false;

    function finish(showError) {
      if (finished) return;
      finished = true;
      state.voiceBusy = false;
      state.recognition = null;
      setListening(button, false);
      const text = finalText.trim();
      if (text) {
        sendAnswer(q, card, { text: text }, status);
        return;
      }
      if (attempt < 2) {
        status.textContent = t('Слушаю… скажите ответ');
        setTimeout(function () { listen(q, card, button, status, attempt + 1); }, 250);
        return;
      }
      if (showError) {
        status.textContent = t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
      }
    }

    recognition.onresult = function (event) {
      var interim = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += ' ' + piece;
        else interim += ' ' + piece;
      }
      status.textContent = t('Услышано:') + ' ' + (finalText || interim).trim();
    };

    recognition.onerror = function (event) {
      var code = event.error;
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        finished = true;
        state.voiceBusy = false;
        setListening(button, false);
        status.textContent = t('Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.');
        return;
      }
      if (code === 'no-speech' || code === 'aborted') {
        finish(true);
        return;
      }
      finish(true);
    };

    // распознавание закрылось: если текст есть — отправляем, если нет — одна повторная попытка
    recognition.onend = function () { finish(true); };

    try {
      recognition.start();
    } catch (e) {
      state.voiceBusy = false;
      setListening(button, false);
      status.textContent = t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
    }
  }

  /* ---------------------------- ответы ---------------------------- */

  async function sendAnswer(q, card, payload, status) {
    if (!state.run || state.finished) return;
    try {
      const data = await post('/api/video-quiz/answer',
        Object.assign({ run_id: state.run.run_id, question_id: q.id }, payload));
      state.answers[q.id] = true;
      updateProgress();
      if (status) {
        if (data.accepted) {
          status.textContent = t('Ответ принят — вердикт будет в конце');
        } else if (data.recognised === false) {
          status.textContent = t('Услышано:') + ' ' + (payload.text || '') + ' · ' +
            t('не похоже ни на один из вариантов ответа');
        } else {
          status.textContent = t('Услышано:') + ' ' + (payload.text || '') + ' · ' +
            (data.correct ? t('Верно') : t('Неверно'));
        }
      }
      if (data.accepted) showPending(card);
      else showVerdict(card, data);
    } catch (error) {
      const feedback = card.querySelector('.quiz-feedback');
      feedback.hidden = false;
      feedback.textContent = error.message;
    }
  }

  function showPending(card) {
    const feedback = card.querySelector('.quiz-feedback');
    feedback.hidden = false;
    feedback.innerHTML = '';
    feedback.appendChild(el('div', 'quiz-verdict pending', t('Ответ принят — вердикт будет в конце')));
  }

  function showVerdict(card, data) {
    const feedback = card.querySelector('.quiz-feedback');
    feedback.hidden = false;
    feedback.innerHTML = '';
    if (data.recognised === false) {
      /* фраза или текст не сопоставились ни с одним вариантом — честно говорим об этом */
      feedback.appendChild(el('div', 'quiz-verdict pending',
        t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.')));
      return;
    }
    card.classList.toggle('is-correct', data.correct);
    card.classList.toggle('is-wrong', !data.correct);
    feedback.appendChild(el('div', 'quiz-verdict ' + (data.correct ? 'ok' : 'bad'),
      data.correct ? t('Верно') : t('Неверно — правильный вариант:') + ' ' + (data.correct_index + 1)));
    feedback.appendChild(el('div', 'quiz-explain', data.explain));
    feedback.appendChild(el('div', 'quiz-source', t('Паспорт станции:') + ' ' + data.checklist));
    card.querySelectorAll('.quiz-option').forEach(function (label, i) {
      label.classList.toggle('is-answer', i === data.correct_index);
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
      const verdictText = item.chosen < 0
        ? t('Ответа нет — правильный вариант:') + ' ' + (item.correct_index + 1)
        : (item.correct ? t('Верно')
          : t('Неверно — правильный вариант:') + ' ' + (item.correct_index + 1));
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

  /* вердикт: слова «инструкция по ЭМП» превращаем в ссылку на саму инструкцию */
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
        left.appendChild(el('span', 'quiz-history-mode', (row.mode === 'testing' ? t('зачёт') : t('обучение'))));
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

  function applyMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.seg').forEach(function (button) {
      const on = button.dataset.mode === mode;
      button.classList.toggle('is-on', on);
      button.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    if (!state.run) renderCatalog();
  }

  /* ---------------------------- клавиатура ---------------------------- */

  function bindKeys() {
    document.addEventListener('keydown', function (event) {
      if (!state.run || state.finished) return;
      if (event.target.matches('input, textarea, select, button')) return;
      if (event.key === 'Enter' && !document.getElementById('finishBtn').disabled) {
        finishQuiz();
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
    if (!voiceSupported || !secure) {
      const hint = document.getElementById('voiceHint');
      if (hint) {
        hint.textContent = !secure
          ? t('Голосовой ответ работает только по https — на этом адресе он недоступен. Введите ответ текстом.')
          : t('В этом браузере голосовой ответ недоступен — работает в Chrome и Edge. Введите ответ текстом.');
      }
    }
    document.addEventListener('ekstrenka:lang', function () { backToCatalog(); loadSections(); });
    bindKeys();
    loadSections();
  });
})();
