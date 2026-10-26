/* Отправка кадров с камеры на сервер для анализа техники (СЛР).
 *
 * Что делает:
 *   1. встаёт в очередь (/vision/join) — пока станция занята, показывает «вы N-й»;
 *   2. когда слот освободился — 15 раз в секунду снимает кадр 480×360 в JPEG
 *      и отправляет на /api/attempts/{id}/frames;
 *   3. показывает живые показатели (темп, глубина, руки) в плашке поверх видео;
 *   4. по завершении — /vision/leave (итог сохраняется в попытку).
 *
 * Видео никуда не сохраняется: на сервер уходит одиночный JPEG, который
 * декодируется, обрабатывается и сразу выбрасывается.
 *
 * Подключение:
 *   <script src="/static/js/cpr_stream.js"></script>
 *   CprStream.start(attemptId, videoElement);   // при включении камеры
 *   CprStream.stop();                           // при выключении / завершении
 */
(function () {
  'use strict';

  const CONFIG = {
    width: 480,
    height: 360,
    quality: 0.65,
    fps: 15,
    statusPollMs: 2000,
  };

  const state = {
    running: false,
    attemptId: null,
    video: null,
    canvas: null,
    ctx: null,
    timer: null,
    pollTimer: null,
    sending: false,
    pill: null,
  };

  function pill() {
    if (state.pill) return state.pill;
    const box = document.createElement('div');
    box.id = 'cprLive';
    box.style.cssText = [
      'margin-top:8px', 'padding:8px 12px', 'border-radius:10px',
      'background:#3C388D', 'color:#fff', 'font-size:12.5px', 'line-height:1.5',
      'font-family:Verdana,Arial,sans-serif', 'box-shadow:0 2px 10px rgba(0,0,0,.25)',
    ].join(';');
    box.textContent = 'Анализ техники: подключение…';

    // ВАЖНО: не внутрь .media-box (там overflow:hidden и плашка обрезается),
    // а сразу после него — в родительскую колонку.
    const mediaBox = document.getElementById('mediaBox');
    if (mediaBox && mediaBox.parentElement) {
      mediaBox.parentElement.insertBefore(box, mediaBox.nextSibling);
    } else if (state.video && state.video.parentElement) {
      state.video.parentElement.appendChild(box);
    }
    state.pill = box;
    return box;
  }

  function say(text) {
    const box = pill();
    if (box) box.textContent = text;
  }

  function hide() {
    if (state.pill) {
      state.pill.remove();
      state.pill = null;
    }
  }

  async function api(url, options) {
    const response = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    if (!response.ok) {
      const message = (data && data.detail) || ('HTTP ' + response.status);
      throw new Error(message);
    }
    return data;
  }

  /* ---------------- очередь ---------------- */

  async function join() {
    const info = await api(`/api/attempts/${state.attemptId}/vision/join`, { method: 'POST' });
    if (info.status === 'active') {
      await startCapture();
      return;
    }
    const position = info.position || 1;
    const eta = info.eta_sec ? Math.max(1, Math.round(info.eta_sec / 60)) : null;
    say(`Станция занята. Вы ${position}-й в очереди${eta ? ', ждать ~' + eta + ' мин' : ''}.`);
    state.pollTimer = setTimeout(poll, CONFIG.statusPollMs);
  }

  async function poll() {
    if (!state.running) return;
    try {
      const info = await api(`/api/attempts/${state.attemptId}/vision/status`);
      if (info.status === 'active') {
        say('Слот свободен — начинаем анализ техники.');
        await startCapture();
        return;
      }
      if (info.status === 'off' || info.status === 'expired') {
        say('Анализ техники недоступен — прохождение продолжается без него.');
        return;
      }
      const position = info.position || 1;
      const eta = info.eta_sec ? Math.max(1, Math.round(info.eta_sec / 60)) : null;
      say(`Станция занята. Вы ${position}-й в очереди${eta ? ', ждать ~' + eta + ' мин' : ''}.`);
      state.pollTimer = setTimeout(poll, CONFIG.statusPollMs);
    } catch (error) {
      say('Анализ техники недоступен: ' + error.message);
    }
  }

  /* ---------------- отправка кадров ---------------- */

  async function startCapture() {
    if (!state.video || !state.canvas) return;
    state.sending = true;
    say('Анализ техники: идёт запись кадров…');
    loop();
  }

  async function loop() {
    if (!state.running || !state.sending) return;
    const started = Date.now();
    try {
      if (state.video.readyState >= 2) {
        state.ctx.drawImage(state.video, 0, 0, CONFIG.width, CONFIG.height);
        const image = state.canvas.toDataURL('image/jpeg', CONFIG.quality);
        const answer = await api(`/api/attempts/${state.attemptId}/frames`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: image, ts_ms: Date.now() }),
        });
        render(answer);
      }
    } catch (error) {
      // одна неудачная отправка не должна ломать прохождение
      say('Анализ техники: связь прервалась, пробуем снова…');
    }
    const spent = Date.now() - started;
    const wait = Math.max(0, Math.round(1000 / CONFIG.fps) - spent);
    state.timer = setTimeout(loop, wait);
  }

  function render(answer) {
    const live = answer && answer.result;
    if (!live) return;
    const parts = [];
    if (live.tempo_bpm) parts.push(`темп ${Math.round(live.tempo_bpm)}/мин`);
    if (live.depth_cm) parts.push(`глубина ${live.depth_cm} см`);
    if (live.arms_straight_pct !== null && live.arms_straight_pct !== undefined) {
      parts.push(`руки прямые ${Math.round(live.arms_straight_pct)}%`);
    }
    if (!live.frames_with_pose) {
      say(`Анализ техники: кадр ${live.frames_total || answer.seq}, человек не распознан — встаньте в кадр целиком, камера сбоку`);
      return;
    }
    const tail = ` · кадров ${live.frames_with_pose}`;
    say('Анализ техники: ' + (parts.length ? parts.join(' · ') + tail : 'накапливаем данные…' + tail));
  }

  /* ---------------- публичный API ---------------- */

  const CprStream = {
    start(attemptId, videoElement) {
      if (!attemptId || !videoElement) return;
      if (!window.isSecureContext) return;   // камера недоступна по http — молча выходим
      this.stop();
      state.running = true;
      state.attemptId = attemptId;
      state.video = videoElement;
      state.canvas = document.createElement('canvas');
      state.canvas.width = CONFIG.width;
      state.canvas.height = CONFIG.height;
      state.ctx = state.canvas.getContext('2d');
      state.sending = false;
      join().catch((error) => say('Анализ техники недоступен: ' + error.message));
    },

    async stop() {
      const wasRunning = state.running;
      state.running = false;
      state.sending = false;
      clearTimeout(state.timer);
      clearTimeout(state.pollTimer);
      state.timer = state.pollTimer = null;
      const attemptId = state.attemptId;
      state.attemptId = null;
      if (wasRunning && attemptId) {
        try {
          await api(`/api/attempts/${attemptId}/vision/leave`, { method: 'POST' });
        } catch (error) {
          /* попытка могла уже завершиться — это нормально */
        }
      }
      hide();
    },

    isRunning() {
      return state.running;
    },
  };

  window.CprStream = CprStream;
})();
