/* Видеотест: вопросы по фрагментам станции ЭМП + голосовой ответ.
 *
 * Правильные ответы живут только на сервере: браузер присылает номер варианта,
 * вердикт (в режиме обучения) и разбор (в конце) приходят ответом API.
 *
 * Голос: распознаёт браузер (Web Speech API, Chrome и Edge), на сервер уходит только текст;
 * сервер сопоставляет фразу с вариантами и возвращает номер — запись никуда не сохраняется.
 */

(function () {
  var state = { questions: [], answers: {}, checked: {}, mode: 'training', voiceBusy: false };

  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var voiceSupported = Boolean(SR);

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

  /* подпись интерфейса: русский текст, английский — из словаря i18n */
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

  /* ---------------------------- отрисовка ---------------------------- */

  function renderQuestion(q, index) {
    const card = el('div', 'panel quiz-card');
    card.dataset.id = q.id;

    const head = el('div', 'quiz-head');
    head.appendChild(el('span', 'quiz-num', t('Фрагмент ' + (index + 1) + ' из ' + state.questions.length)));
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

    const options = el('div', 'quiz-options');
    q.options.forEach(function (text, i) {
      const label = el('label', 'option quiz-option');
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'q' + q.id;
      radio.value = String(i);
      radio.addEventListener('change', function () { onChoose(q, i, card); });
      label.appendChild(radio);
      label.appendChild(el('span', 'opt-key', String(i + 1)));
      label.appendChild(el('span', '', text));
      options.appendChild(label);
    });
    card.appendChild(options);

    if (voiceSupported) card.appendChild(renderVoice(q, card));

    const feedback = el('div', 'quiz-feedback');
    feedback.hidden = true;
    card.appendChild(feedback);

    return card;
  }

  function renderVoice(q, card) {
    const box = el('div', 'quiz-voice');
    const button = el('button', 'btn ghost small quiz-mic');
    button.type = 'button';
    button.innerHTML = '<span class="mic-dot" aria-hidden="true"></span>';
    button.appendChild(el('span', '', t('Ответить голосом')));
    const status = el('div', 'quiz-voice-status muted small');

    button.addEventListener('click', function () {
      if (state.voiceBusy) return;
      listen(q, card, button, status);
    });

    box.appendChild(button);
    box.appendChild(status);
    return box;
  }

  function setListening(button, on) {
    button.classList.toggle('is-listening', on);
    button.querySelector('span:last-child').textContent = on ? t('Слушаю…') : t('Ответить голосом');
  }

  function listen(q, card, button, status) {
    const recognition = new SR();
    recognition.lang = lang() === 'en' ? 'en-US' : 'ru-RU';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    state.voiceBusy = true;
    setListening(button, true);
    status.textContent = t('Слушаю…');

    var finalText = '';
    var stopped = false;

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
      stopped = true;
      state.voiceBusy = false;
      setListening(button, false);
      status.textContent = event.error === 'not-allowed'
        ? t('Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.')
        : t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
    };

    recognition.onend = function () {
      setListening(button, false);
      state.voiceBusy = false;
      if (stopped) return;
      var text = finalText.trim();
      if (!text) {
        status.textContent = t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
        return;
      }
      sendVoice(q, card, text, status);
    };

    try {
      recognition.start();
    } catch (e) {
      state.voiceBusy = false;
      setListening(button, false);
      status.textContent = t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
    }
  }

  async function sendVoice(q, card, transcript, status) {
    status.textContent = t('Услышано:') + ' ' + transcript;
    try {
      const result = await post('/api/video-quiz/voice',
        { question_id: q.id, transcript: transcript, lang: lang() });
      if (result.chosen === null || result.chosen === undefined) {
        status.textContent = t('Услышано:') + ' ' + transcript + ' · ' +
          t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
        return;
      }
      const label = card.querySelectorAll('.quiz-option')[result.chosen];
      if (label) {
        label.querySelector('input').checked = true;
        label.querySelector('input').dispatchEvent(new Event('change'));
      }
      status.textContent = t('Услышано:') + ' ' + transcript + ' · ' +
        t('Понял как вариант') + ' ' + (result.chosen + 1) +
        (result.confidence ? ' (' + t('уверенность') + ' ' + Math.round(result.confidence * 100) + ' %)' : '');
    } catch (error) {
      status.textContent = 'Не удалось проверить голосовой ответ: ' + error.message;
    }
  }

  function showFeedback(card, data) {
    const feedback = card.querySelector('.quiz-feedback');
    feedback.hidden = false;
    feedback.innerHTML = '';
    if (data.accepted) {
      feedback.appendChild(el('div', 'quiz-verdict pending', t('Ответ принят — вердикт будет в конце')));
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

  /* ---------------------------- действия ---------------------------- */

  async function onChoose(q, index, card) {
    state.answers[q.id] = index;
    updateProgress();
    try {
      const data = await post('/api/video-quiz/answer',
        { question_id: q.id, answer: index, mode: state.mode, lang: lang() });
      state.checked[q.id] = data.accepted ? null : data.correct;
      showFeedback(card, data);
      updateProgress();
    } catch (error) {
      const feedback = card.querySelector('.quiz-feedback');
      feedback.hidden = false;
      feedback.textContent = 'Не удалось проверить ответ: ' + error.message;
    }
  }

  function updateProgress() {
    const answered = Object.keys(state.answers).length;
    const total = state.questions.length || 9;
    document.getElementById('answeredCount').textContent = answered;
    document.getElementById('totalCount').textContent = total;
    document.getElementById('progressFill').style.width = Math.round(answered * 100 / total) + '%';
    document.getElementById('finishBtn').disabled = answered === 0;
  }

  async function finishQuiz() {
    const btn = document.getElementById('finishBtn');
    btn.disabled = true;
    btn.textContent = t('Считаем…');
    try {
      const result = await post('/api/video-quiz/finish',
        { answers: state.answers, mode: state.mode, lang: lang() });
      showResult(result);
      loadHistory();
    } catch (error) {
      alert(error.message);
    } finally {
      btn.textContent = t('Завершить и увидеть разбор');
      btn.disabled = false;
    }
  }

  function showResult(result) {
    document.getElementById('resultPanel').hidden = false;
    document.getElementById('scorePercent').textContent = result.percent;
    document.getElementById('scoreVerdict').textContent = result.verdict_text;
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
      feedback.appendChild(el('div', 'quiz-explain', item.explain));
      feedback.appendChild(el('div', 'quiz-source', t('Паспорт станции:') + ' ' + item.checklist));
      card.querySelectorAll('.quiz-option').forEach(function (label, i) {
        label.classList.toggle('is-answer', i === item.correct_index);
        label.classList.toggle('is-chosen', i === item.chosen);
      });
    });
    document.getElementById('resultPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.seg').forEach(function (button) {
      const on = button.dataset.mode === mode;
      button.classList.toggle('is-on', on);
      button.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.getElementById('modeHint').textContent = mode === 'training'
      ? t('Проверка ответа сразу')
      : t('Зачёт: разбор в конце');
    restart(false);
  }

  function restart(scroll) {
    state.answers = {};
    state.checked = {};
    document.getElementById('resultPanel').hidden = true;
    const list = document.getElementById('quizList');
    list.innerHTML = '';
    state.questions.forEach(function (q, i) { list.appendChild(renderQuestion(q, i)); });
    updateProgress();
    if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function loadHistory() {
    try {
      const data = await api('/api/video-quiz/results');
      const panel = document.getElementById('historyPanel');
      const list = document.getElementById('historyList');
      if (!data.items || !data.items.length) { panel.hidden = true; return; }
      list.innerHTML = '';
      data.items.forEach(function (row) {
        const line = el('div', 'quiz-history-row');
        const when = row.created_at ? new Date(row.created_at).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU') : '';
        line.appendChild(el('span', '', when));
        line.appendChild(el('b', '', row.percent + ' %'));
        list.appendChild(line);
      });
      panel.hidden = false;
    } catch (e) { /* история не критична для прохождения */ }
  }

  async function start() {
    const list = document.getElementById('quizList');
    try {
      const data = await api('/api/video-quiz/questions?lang=' + lang());
      state.questions = data.items;
      restart(false);
      loadHistory();
    } catch (error) {
      list.innerHTML = '<div class="alert error">Не удалось загрузить вопросы: ' + error.message + '</div>';
    }
  }

  /* ---------------------------- клавиатура ---------------------------- */

  function bindKeys() {
    document.addEventListener('keydown', function (event) {
      if (event.target.matches('input, textarea, select, button')) return;
      if (event.key === 'Enter' && !document.getElementById('finishBtn').disabled) {
        finishQuiz();
        return;
      }
      const num = parseInt(event.key, 10);
      if (!(num >= 1 && num <= 4)) return;
      const next = state.questions.find(function (q) { return state.answers[q.id] === undefined; });
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
    document.getElementById('restartBtn').addEventListener('click', function () { restart(true); });
    document.querySelectorAll('.seg').forEach(function (button) {
      button.addEventListener('click', function () { setMode(button.dataset.mode); });
    });
    if (!voiceSupported) {
      const hint = document.getElementById('voiceHint');
      if (hint) hint.textContent = t('В этом браузере голосовой ответ недоступен — работает в Chrome и Edge. Выберите вариант вручную.');
    }
    // смена языка: серверные тексты (вопросы, варианты) перезапрашиваем
    document.addEventListener('ekstrenka:lang', function () { start(); });
    bindKeys();
    start();
  });
})();
