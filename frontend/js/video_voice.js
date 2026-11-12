/* Голосовой ввод ответа: два пути и честный выбор между ними.
 *
 *  1) Сервер (надёжный): браузер пишет короткую запись через MediaRecorder,
 *     отправляет её на /api/video-quiz/transcribe, сервер распознаёт (Whisper) и
 *     возвращает текст. Работает в любом браузере, где есть микрофон. Аудио не сохраняется.
 *  2) Браузер (Web Speech API): если серверное распознавание выключено. В Chrome,
 *     который не может достучаться до сервисов Google, часто сразу отдаёт ошибку «network».
 *  3) Если нет ни того, ни другого — остаётся текстовое поле.
 *
 * Модуль сам решает, что показать, и отдаёт наружу простой интерфейс:
 *     VideoVoice.create(host, { onText(text), lang() })  → { setEnabled(bool), destroy() }
 */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function supported() {
    return Boolean(window.MediaRecorder) && Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  function webSpeech() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function secure() {
    return window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  }

  function blobToBase64(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result)); };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /* ----------------------------- серверная запись ----------------------------- */

  function createRecorder(host, options) {
    var state = { recording: false, busy: false, stopFn: null };
    var button = el('button', 'btn ghost small quiz-mic');
    button.type = 'button';
    button.innerHTML = '<span class="mic-dot" aria-hidden="true"></span>';
    button.appendChild(el('span', '', options.label()));
    var status = el('div', 'quiz-voice-status muted small');

    function setButton(text, listening) {
      button.classList.toggle('is-listening', Boolean(listening));
      button.querySelector('span:last-child').textContent = text;
    }

    async function start() {
      if (state.busy || state.recording) return;
      state.busy = true;
      setButton(options.t('Готовлю микрофон…'), true);
      status.textContent = '';
      var stream = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        state.busy = false;
        setButton(options.label(), false);
        status.textContent = (error && error.name === 'NotAllowedError')
          ? options.t('Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.')
          : options.t('Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.');
        return;
      }

      var chunks = [];
      var mime = '';
      ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
        .some(function (type) {
          if (window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(type)) {
            mime = type;
            return true;
          }
          return false;
        });
      var recorder;
      try {
        recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      } catch (error) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        state.busy = false;
        setButton(options.label(), false);
        status.textContent = options.t('Запись с микрофона не поддерживается этим браузером.');
        return;
      }

      recorder.ondataavailable = function (event) {
        if (event.data && event.data.size) chunks.push(event.data);
      };
      recorder.onstop = async function () {
        stream.getTracks().forEach(function (track) { track.stop(); });
        state.recording = false;
        state.busy = false;
        setButton(options.label(), false);
        var blob = new Blob(chunks, { type: chunks.length ? (chunks[0].type || mime || 'audio/webm') : 'audio/webm' });
        if (blob.size < 600) {
          status.textContent = options.t('Запись пустая — говорите ближе к микрофону.');
          return;
        }
        status.textContent = options.t('Распознаю…');
        try {
          var dataUrl = await blobToBase64(blob);
          var response = await fetch('/api/video-quiz/transcribe', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio: dataUrl, lang: options.lang() }),
          });
          if (!response.ok) {
            var detail = 'Ошибка ' + response.status;
            try { detail = (await response.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
          }
          var data = await response.json();
          var text = (data.text || '').trim();
          if (!text) {
            status.textContent = options.t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
            return;
          }
          status.textContent = options.t('Услышано:') + ' ' + text;
          options.onText(text, status);
        } catch (error) {
          status.textContent = error.message;
        }
      };

      recorder.start();
      state.recording = true;
      state.busy = false;
      state.stopFn = function () { try { recorder.stop(); } catch (e) {} };
      setButton(options.t('Слушаю… (Стоп)'), true);
      status.textContent = options.t('Слушаю… говорите ответ');
      // страховка: очень длинную запись не держим (20 секунд — с запасом)
      state.timer = setTimeout(function () { if (state.recording) state.stopFn(); }, 20000);
    }

    function stop() {
      clearTimeout(state.timer);
      if (state.stopFn) state.stopFn();
    }

    button.addEventListener('click', function () {
      if (state.recording) stop();
      else start();
    });

    host.appendChild(button);
    host.appendChild(status);

    return {
      destroy: function () {
        clearTimeout(state.timer);
        if (state.recording) stop();
        button.remove();
        status.remove();
      },
      stop: stop,
    };
  }

  /* ----------------------------- браузерное распознавание ----------------------------- */

  function createWebSpeech(host, options) {
    var SR = webSpeech();
    var state = { busy: false, recognition: null };
    var button = el('button', 'btn ghost small quiz-mic');
    button.type = 'button';
    button.innerHTML = '<span class="mic-dot" aria-hidden="true"></span>';
    button.appendChild(el('span', '', options.label()));
    var status = el('div', 'quiz-voice-status muted small');

    function setButton(text, listening) {
      button.classList.toggle('is-listening', Boolean(listening));
      button.querySelector('span:last-child').textContent = text;
    }

    function listen(attempt) {
      attempt = attempt || 1;
      var recognition = new SR();
      state.recognition = recognition;
      recognition.lang = options.lang() === 'en' ? 'en-US' : 'ru-RU';
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;

      state.busy = true;
      setButton(options.t('Слушаю… (Стоп)'), true);
      status.textContent = options.t('Слушаю… говорите ответ');

      var finalText = '';
      var done = false;

      function finish() {
        if (done) return;
        done = true;
        state.busy = false;
        state.recognition = null;
        setButton(options.label(), false);
        var text = finalText.trim();
        if (text) {
          status.textContent = options.t('Услышано:') + ' ' + text;
          options.onText(text, status);
          return;
        }
        if (attempt < 2) {
          setTimeout(function () { listen(attempt + 1); }, 250);
          return;
        }
        status.textContent = options.t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
      }

      recognition.onresult = function (event) {
        var interim = '';
        for (var i = event.resultIndex; i < event.results.length; i++) {
          var piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += ' ' + piece;
          else interim += ' ' + piece;
        }
        status.textContent = options.t('Услышано:') + ' ' + (finalText || interim).trim();
      };

      recognition.onerror = function (event) {
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          done = true;
          state.busy = false;
          setButton(options.label(), false);
          status.textContent = options.t('Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.');
          return;
        }
        if (event.error === 'network') {
          done = true;
          state.busy = false;
          setButton(options.label(), false);
          status.textContent = options.t('Браузер не может распознать речь — включите распознавание на сервере (VOICE_ENABLED=1) или введите ответ текстом.');
          return;
        }
        finish();
      };

      recognition.onend = finish;

      try {
        recognition.start();
      } catch (error) {
        state.busy = false;
        setButton(options.label(), false);
        status.textContent = options.t('Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.');
      }
    }

    button.addEventListener('click', function () {
      if (state.busy && state.recognition) {
        try { state.recognition.stop(); } catch (e) {}
        return;
      }
      listen(1);
    });

    host.appendChild(button);
    host.appendChild(status);

    return {
      destroy: function () {
        if (state.recognition) { try { state.recognition.stop(); } catch (e) {} }
        button.remove();
        status.remove();
      },
    };
  }

  window.VideoVoice = {
    secure: secure,
    /* какой способ использовать: server / browser / none */
    pick: function (serverAvailable) {
      if (!secure()) return 'none';
      if (serverAvailable && supported()) return 'server';
      if (webSpeech()) return 'browser';
      return 'none';
    },
    create: function (host, options, mode) {
      if (mode === 'server') return createRecorder(host, options);
      if (mode === 'browser') return createWebSpeech(host, options);
      return { destroy: function () {} };
    },
  };
})();
