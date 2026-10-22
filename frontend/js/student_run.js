/* Прохождение испытания: ответы, таймер, камера/микрофон, завершение.
   Конфигурация приходит из <script id="run-config" type="application/json">:
   { "testId": 1, "mode": "training" | "testing", "total": 3 } */

const RUN = JSON.parse(document.getElementById('run-config').textContent);
const TEST_ID = RUN.testId;
const TEST_MODE = RUN.mode;
const TOTAL = RUN.total;

let attemptId = null;
let startedAt = Date.now();
let mediaSeconds = 0;
let cameraOn = false;
let micOn = false;
let camStream = null;
let micStream = null;
let audioCtx = null;
let rafId = null;

const answered = new Set();
const dirty = new Set();

/* ---------------- попытка ---------------- */

async function startAttempt() {
  try {
    const attempt = await apiFetch('/api/attempts', {
      method: 'POST',
      body: JSON.stringify({
        test_id: TEST_ID,
        subject_type: document.getElementById('subjectSelect').value,
      }),
    });
    attemptId = attempt.id;
    if (attempt.started_at) startedAt = new Date(attempt.started_at).getTime();
    renderTimeline();
  } catch (error) {
    alert(error.message);
  }
}

function tick() {
  const seconds = Math.floor((Date.now() - startedAt) / 1000);
  const minutes = String(Math.floor(seconds / 60)).padStart(2, '0');
  const rest = String(seconds % 60).padStart(2, '0');
  document.getElementById('timerTag').textContent = minutes + ':' + rest;
  if (cameraOn || micOn) {
    mediaSeconds = seconds;
    updateMediaMeta();
  }
}
setInterval(tick, 1000);

function updateMediaMeta() {
  document.getElementById('mediaMeta').textContent =
    `камера ${cameraOn ? 'вкл' : 'выкл'} · микрофон ${micOn ? 'вкл' : 'выкл'} · ${mediaSeconds} с`;
}

/* ---------------- ответы ---------------- */

function setStatus(questionId, text, cssClass) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  if (!box) return;
  const tag = box.querySelector('[data-status]');
  tag.textContent = text;
  tag.className = 'tag ' + (cssClass || '');
}

function updateProgress() {
  document.getElementById('answeredCount').textContent = answered.size;
  renderTimeline();
}

function renderTimeline() {
  const wrap = document.getElementById('timeline');
  if (!wrap.dataset.init) {
    let html = '';
    for (let i = 0; i < TOTAL; i++) {
      html += `<div class="row" data-i="${i}"><span class="n">${i + 1}</span><span>Вопрос ${i + 1}</span></div>`;
    }
    wrap.innerHTML = html;
    wrap.dataset.init = '1';
  }
  const ids = [...document.querySelectorAll('.question')].map((el) => el.dataset.qid);
  ids.forEach((questionId, index) => {
    const row = wrap.querySelector(`.row[data-i="${index}"]`);
    if (!row) return;
    row.classList.toggle('done', answered.has(questionId));
  });
}

function showFeedback(questionId, res) {
  if (TEST_MODE !== 'training') return;

  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const feedback = box.querySelector('[data-feedback]');
  let cssClass = 'neutral';
  let text = res.comment || 'Ответ сохранён';

  if (res.is_correct === true) {
    cssClass = 'ok';
    text = `Верно (+${res.awarded_points})`;
  } else if (res.is_correct === false) {
    cssClass = 'bad';
    text = `Неверно (${res.awarded_points} б.)`;
  }

  if (res.hint) text += ` · Подсказка: ${res.hint}`;
  if (res.correct !== null && res.correct !== undefined && res.is_correct === false) {
    const correct = Array.isArray(res.correct) ? res.correct.join(', ') : res.correct;
    text += ` · Правильный ответ: ${correct}`;
  }

  feedback.className = 'feedback ' + cssClass;
  feedback.textContent = text;
}

async function saveAnswer(questionId, value) {
  if (!attemptId) {
    alert('Попытка ещё не создана');
    return null;
  }
  try {
    const res = await apiFetch(`/api/attempts/${attemptId}/answers`, {
      method: 'POST',
      body: JSON.stringify({ question_id: Number(questionId), value }),
    });
    answered.add(String(questionId));
    setStatus(questionId, 'сохранён', 'info');
    updateProgress();
    showFeedback(questionId, res);
    return res;
  } catch (error) {
    alert(error.message);
    return null;
  }
}

function answerSingle(questionId, input) {
  document.querySelectorAll(`.question[data-qid="${questionId}"] .option`)
    .forEach((element) => element.classList.toggle('selected', element.contains(input)));
  saveAnswer(questionId, input.value);
}

function answerMultiple(questionId, forced) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const values = [...box.querySelectorAll('input[type=checkbox]:checked')].map((input) => input.value);
  box.querySelectorAll('.option').forEach((element) => {
    element.classList.toggle('selected', !!element.querySelector('input:checked'));
  });
  if (!forced && values.length === 0) return;
  saveAnswer(questionId, values);
}

function markDirty(questionId) {
  dirty.add(String(questionId));
  setStatus(questionId, 'не сохранён', 'warn');
}

function answerText(questionId) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const value = box.querySelector('textarea').value;
  dirty.delete(String(questionId));
  saveAnswer(questionId, value);
}

/* ---------------- камера и микрофон ---------------- */

async function toggleCamera() {
  const button = document.getElementById('camBtn');

  if (cameraOn) {
    if (camStream) camStream.getTracks().forEach((track) => track.stop());
    camStream = null;
    cameraOn = false;
    document.getElementById('cam').classList.add('hidden');
    const placeholder = document.getElementById('mediaPlaceholder');
    placeholder.classList.remove('hidden');
    placeholder.textContent = 'Камера выключена';
    if (button) button.textContent = 'Включить камеру';
    updateMediaMeta();
    return;
  }

  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const video = document.getElementById('cam');
    video.srcObject = camStream;
    video.classList.remove('hidden');
    document.getElementById('mediaPlaceholder').classList.add('hidden');
    cameraOn = true;
    if (button) button.textContent = 'Выключить камеру';
    updateMediaMeta();
  } catch (error) {
    document.getElementById('mediaPlaceholder').textContent =
      'Нет доступа к камере: ' + error.message;
  }
}

async function toggleMic() {
  const button = document.getElementById('micBtn');

  if (micOn) {
    if (micStream) micStream.getTracks().forEach((track) => track.stop());
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    cancelAnimationFrame(rafId);
    micStream = null;
    micOn = false;
    document.getElementById('micState').textContent = 'выкл';
    document.getElementById('micLevel').style.width = '0%';
    if (button) button.textContent = 'Включить микрофон';
    updateMediaMeta();
    return;
  }

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(micStream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);

    const buffer = new Uint8Array(analyser.frequencyBinCount);
    const loop = () => {
      analyser.getByteFrequencyData(buffer);
      let sum = 0;
      for (let i = 0; i < buffer.length; i++) sum += buffer[i];
      const level = Math.min(100, (sum / buffer.length) * 1.8);
      document.getElementById('micLevel').style.width = level + '%';
      rafId = requestAnimationFrame(loop);
    };
    loop();

    micOn = true;
    document.getElementById('micState').textContent = 'вкл';
    if (button) button.textContent = 'Выключить микрофон';
    updateMediaMeta();
  } catch (error) {
    document.getElementById('micState').textContent = 'нет доступа';
  }
}

function subjectChanged() {
  if (!attemptId) return;
  sessionStorage.setItem('subject_type', document.getElementById('subjectSelect').value);
}

async function sendMedia() {
  if (!attemptId) return;
  try {
    await apiFetch(`/api/attempts/${attemptId}/media`, {
      method: 'POST',
      body: JSON.stringify({
        camera: cameraOn,
        mic: micOn,
        seconds: mediaSeconds,
        note: 'заглушка: файлы не сохраняются',
      }),
    });
  } catch (error) {
    /* не мешаем завершению */
  }
}

/* ---------------- завершение ---------------- */

async function finishAttempt() {
  if (!attemptId) return;

  if (dirty.size > 0 && !confirm('Есть несохранённые ответы. Всё равно завершить?')) return;
  if (!confirm('Завершить испытание и получить результат?')) return;

  await sendMedia();
  try {
    const attempt = await apiFetch(`/api/attempts/${attemptId}/finish`, { method: 'POST' });
    window.location.href = '/student/attempts/' + attempt.id;
  } catch (error) {
    alert(error.message);
  }
}

async function abortAttempt() {
  if (!attemptId) {
    window.location.href = '/';
    return;
  }
  if (!confirm('Прервать испытание? Ответы сохранятся, попытка будет помечена как прерванная.')) return;

  await sendMedia();
  try {
    await apiFetch(`/api/attempts/${attemptId}/abort`, { method: 'POST' });
  } catch (error) {
    /* игнорируем: всё равно уходим со страницы */
  }
  window.location.href = '/student/attempts';
}

startAttempt();
