/* Демо-версия «Экстренка» — работает без сервера, данные в localStorage.
   Это витрина для показа: та же логика и интерфейс, но без Python, БД и нейросети. */

const STORE_KEY = 'ispytaniya_preview_v1';
const MODE_LABEL = { training: 'обучение', testing: 'тестирование' };
const SUBJECT_LABEL = { human: 'на человеке', imitation: 'имитация предметами' };

let DB = null;
let timerHandle = null;
let mediaTimerHandle = null;
let camStream = null;
let micStream = null;
let audioCtx = null;
let rafId = null;

/* ============================ хранилище ============================ */

function seed() {
  const now = Date.now();
  return {
    users: [
      { id: 1, email: 'teacher@example.com', fullName: 'Преподаватель Демо', password: 'teacher123', role: 'teacher', group: '', status: 'active', createdAt: now },
      { id: 2, email: 'student@example.com', fullName: 'Студент Демо', password: 'student123', role: 'student', group: 'РИ-21', status: 'active', createdAt: now },
    ],
    tests: [{
      id: 1, authorId: 1, title: 'Базовое собеседование по предмету',
      description: 'Демонстрационное испытание: три вопроса, камера и микрофон включены.',
      mode: 'testing', subject: 'human', duration: 10, criteria: 'Полнота ответа, корректность терминологии, логика изложения.',
      camera: true, mic: true, published: true, createdAt: now,
      questions: [
        { id: 1, text: 'Что такое испытуемый объект?', kind: 'single', options: ['Человек', 'Прибор', 'Предмет'], correct: 'Человек', points: 1, hint: 'Речь о том, кого испытывают.' },
        { id: 2, text: 'Какие признаки относятся к имитации предметами?', kind: 'multiple', options: ['Макет', 'Стенд', 'Живой человек'], correct: ['Макет', 'Стенд'], points: 2, hint: 'Живой человек — это уже испытание на человеке.' },
        { id: 3, text: 'Опишите порядок проведения испытания.', kind: 'text_manual', options: [], correct: null, points: 3, hint: 'Ответ проверит преподаватель.' },
      ],
    }],
    attempts: [],
    logs: [],
    session: null,
    seq: { user: 3, test: 2, question: 4, attempt: 1, log: 1 },
  };
}

function loadDB() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    DB = raw ? JSON.parse(raw) : seed();
  } catch (e) {
    DB = seed();
  }
  if (!DB.seq) DB.seq = seed().seq;
  saveDB();
}

function saveDB() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(DB));
  } catch (e) {
    console.warn('Не удалось сохранить данные', e);
  }
}

function resetDemo() {
  if (!confirm('Сбросить демо-данные к исходным? Все созданные испытания и попытки удалятся.')) return;
  try { localStorage.removeItem(STORE_KEY); } catch (e) { /* режим без storage */ }
  DB = seed();
  saveDB();
  go('#/login');
}

function logAction(action, detail) {
  DB.logs.unshift({ id: DB.seq.log++, at: Date.now(), action, userId: DB.session, detail: detail || '' });
  DB.logs = DB.logs.slice(0, 300);
  saveDB();
}

/* ============================ помощники ============================ */

const esc = (value) => String(value == null ? '' : value)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const fmtDate = (ts) => new Date(ts).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
const currentUser = () => DB.users.find((u) => u.id === DB.session) || null;
const userById = (id) => DB.users.find((u) => u.id === id) || null;
const testById = (id) => DB.tests.find((t) => t.id === Number(id)) || null;
const attemptById = (id) => DB.attempts.find((a) => a.id === Number(id)) || null;

function go(hash) {
  window.location.hash = hash;
  window.scrollTo(0, 0);
}

function maxScore(test) {
  return test.questions.reduce((sum, q) => sum + Number(q.points || 0), 0);
}

function normalize(value) {
  return String(value == null ? '' : value).trim().toLowerCase().replace(/ё/g, 'е');
}

function checkAnswer(question, value) {
  if (question.kind === 'single') {
    if (question.correct == null) return [null, 0];
    const ok = normalize(value) === normalize(question.correct);
    return [ok, ok ? Number(question.points) : 0];
  }
  if (question.kind === 'multiple') {
    const expect = (question.correct || []).map(normalize);
    if (!expect.length) return [null, 0];
    const given = (value || []).map(normalize);
    const hits = given.filter((v) => expect.includes(v));
    const ok = hits.length === expect.length && given.length === expect.length;
    if (ok) return [true, Number(question.points)];
    return [false, Math.round((hits.length / expect.length) * Number(question.points) * 0.5 * 100) / 100];
  }
  if (!question.correct) return [null, 0];
  const variants = Array.isArray(question.correct) ? question.correct : [question.correct];
  const ok = variants.map(normalize).includes(normalize(value));
  return [ok, ok ? Number(question.points) : 0];
}

/* ============================ каркас страницы ============================ */

function navBar(user) {
  const isTeacher = user.role === 'teacher';
  const links = isTeacher
    ? [['#/', 'Главная'], ['#/tests', 'Испытания'], ['#/results', 'Результаты'], ['#/users', 'Пользователи'], ['#/logs', 'Логи'], ['#/instruction', 'Инструкция по ЭМП']]
    : [['#/', 'Доступные испытания'], ['#/training', 'Обучение'], ['#/attempts', 'Мои попытки'], ['#/instruction', 'Инструкция по ЭМП']];
  const current = window.location.hash || '#/';
  const isActive = (href) => (href === '#/'
    ? (current === '#/' || current.startsWith('#/run/'))
    : current.startsWith(href.replace('#/', '#/')));
  return `
    <header class="topbar">
      <a class="brand" href="#/">Экстренка<span class="dot">.</span></a>
      <button class="nav-toggle" id="navToggle" type="button" aria-expanded="false" aria-controls="mainNav" onclick="toggleNav()">
        <span class="nav-toggle-bars" aria-hidden="true"><i></i><i></i><i></i></span>
        Меню
      </button>
      <nav class="nav" id="mainNav">
        ${links.map(([href, label]) => `<a href="${href}" class="${isActive(href) ? 'active' : ''}">${label}</a>`).join('')}
      </nav>
      <div class="userbox">
        <span class="role-badge ${user.role}">${user.role === 'teacher' ? 'преподаватель' : 'учащийся'}</span>
        <a class="username ${current === '#/account' ? 'active-user' : ''}" href="#/account" title="Аккаунт">${esc(user.fullName)}</a>
        <button class="btn ghost small" onclick="logout()">Выйти</button>
      </div>
    </header>`;
}

function toggleNav() {
  const nav = document.getElementById('mainNav');
  const toggle = document.getElementById('navToggle');
  if (!nav || !toggle) return;
  const isOpen = nav.classList.toggle('open');
  toggle.classList.toggle('is-open', isOpen);
  toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}

function shell(user, content) {
  return `${navBar(user)}<main class="container">${content}</main>
    <footer class="footer">
      <a href="#" onclick="resetDemo();return false">сбросить демо-данные</a>
    </footer>`;
}

function plainShell(content) {
  return `<div class="auth-wrap">${content}</div>`;
}

/* ============================ маршрутизация ============================ */

const ROUTES = [
  [/^#\/$/, viewHome],
  [/^#\/instruction$/, viewInstruction],
  [/^#\/training$/, viewTraining],
  [/^#\/login$/, viewLogin],
  [/^#\/register$/, viewRegister],
  [/^#\/account$/, viewAccount],
  [/^#\/tests$/, viewTests],
  [/^#\/tests\/new$/, viewTestNew],
  [/^#\/tests\/(\d+)$/, viewTestEdit],
  [/^#\/run\/(\d+)$/, viewRun],
  [/^#\/attempts$/, viewAttempts],
  [/^#\/attempt\/(\d+)$/, viewAttempt],
  [/^#\/results$/, viewResults],
  [/^#\/users$/, viewUsers],
  [/^#\/logs$/, viewLogs],
];

function router() {
  stopTimers();
  const hash = window.location.hash || '#/';
  const user = currentUser();
  const app = document.getElementById('app');

  if (!user && hash !== '#/login' && hash !== '#/register') {
    go('#/login');
    return;
  }

  for (const [pattern, handler] of ROUTES) {
    const match = hash.match(pattern);
    if (match) {
      app.innerHTML = handler(user, ...match.slice(1));
      return;
    }
  }
  app.innerHTML = plainShell(`<div class="auth-card"><h1>404</h1><p class="muted">Страница не найдена.</p><a class="btn" href="#/">На главную</a></div>`);
}

function stopTimers() {
  clearInterval(timerHandle);
  clearInterval(mediaTimerHandle);
  timerHandle = null;
  mediaTimerHandle = null;
}

/* ============================ вход и регистрация ============================ */

function viewLogin() {
  return plainShell(`
    <div class="auth-card">
      <h1>Вход в систему</h1>
      <p class="sub">Экстренка: обучение и тестирование</p>
      <div id="loginError" class="alert error hidden"></div>
      <div class="field">
        <label for="email">Почта</label>
        <input id="email" type="email" value="teacher@example.com">
      </div>
      <div class="field">
        <label for="password">Пароль</label>
        <input id="password" type="password" value="teacher123">
      </div>
      <button class="btn" style="width:100%" onclick="doLogin()">Войти</button>
      <div class="auth-foot">Нет аккаунта? <a href="#/register">Зарегистрироваться</a></div>
      <div class="demo-box">
        <div class="demo-title">демо-доступы</div>
        <button type="button" class="demo-row" onclick="fillDemo('teacher')">
          <span class="demo-badge teacher">П</span>
          <span class="demo-text"><b>teacher@example.com</b><small>пароль teacher123 · проводящий испытание</small></span>
          <span class="demo-go">подставить →</span>
        </button>
        <button type="button" class="demo-row" onclick="fillDemo('student')">
          <span class="demo-badge student">У</span>
          <span class="demo-text"><b>student@example.com</b><small>пароль student123 · учащийся</small></span>
          <span class="demo-go">подставить →</span>
        </button>
      </div>
    </div>`);
}

function fillDemo(role) {
  const accounts = {
    teacher: { email: 'teacher@example.com', password: 'teacher123' },
    student: { email: 'student@example.com', password: 'student123' },
  };
  const account = accounts[role];
  if (!account) return;
  document.getElementById('email').value = account.email;
  document.getElementById('password').value = account.password;
}

function doLogin() {
  const email = document.getElementById('email').value.trim().toLowerCase();
  const password = document.getElementById('password').value;
  const user = DB.users.find((u) => u.email === email && u.password === password);
  const box = document.getElementById('loginError');
  if (!user) {
    box.textContent = 'Неверная почта или пароль';
    box.classList.remove('hidden');
    logAction('login_failed', email);
    return;
  }
  if (user.status !== 'active') {
    box.textContent = 'Аккаунт заблокирован';
    box.classList.remove('hidden');
    return;
  }
  DB.session = user.id;
  saveDB();
  logAction('login', user.email);
  go('#/');
}

function viewRegister() {
  return plainShell(`
    <div class="auth-card">
      <h1>Регистрация</h1>
      <p class="sub">Кем вы будете в системе?</p>
      <div id="regError" class="alert error hidden"></div>
      <div class="field"><label for="fullName">ФИО</label><input id="fullName" type="text" placeholder="Иванов Иван"></div>
      <div class="field"><label for="regEmail">Почта</label><input id="regEmail" type="email"></div>
      <div class="field"><label for="regPassword">Пароль (минимум 6 символов)</label><input id="regPassword" type="password"></div>
      <div class="field-row">
        <div class="field">
          <label for="regRole">Роль</label>
          <select id="regRole">
            <option value="student">Учащийся</option>
            <option value="teacher">Проводящий испытание (преподаватель)</option>
          </select>
        </div>
        <div class="field"><label for="regGroup">Группа</label><input id="regGroup" type="text" placeholder="РИ-21"></div>
      </div>
      <button class="btn" style="width:100%" onclick="doRegister()">Создать аккаунт</button>
      <div class="auth-foot">Уже есть аккаунт? <a href="#/login">Войти</a></div>
    </div>`);
}

function doRegister() {
  const fullName = document.getElementById('fullName').value.trim();
  const email = document.getElementById('regEmail').value.trim().toLowerCase();
  const password = document.getElementById('regPassword').value;
  const role = document.getElementById('regRole').value;
  const group = document.getElementById('regGroup').value.trim();
  const box = document.getElementById('regError');

  const fail = (message) => { box.textContent = message; box.classList.remove('hidden'); };
  if (!fullName || !email) return fail('Заполните ФИО и почту');
  if (password.length < 6) return fail('Пароль должен быть не короче 6 символов');
  if (DB.users.some((u) => u.email === email)) return fail('Пользователь с такой почтой уже есть');

  const user = { id: DB.seq.user++, email, fullName, password, role, group, status: 'active', createdAt: Date.now() };
  DB.users.push(user);
  DB.session = user.id;
  saveDB();
  logAction('register', email);
  go('#/');
}

function logout() {
  logAction('logout', '');
  DB.session = null;
  saveDB();
  go('#/login');
}

/* ============================ главная ============================ */

function viewHome(user) {
  return user.role === 'teacher' ? homeTeacher(user) : homeStudent(user);
}

function homeTeacher(user) {
  const tests = DB.tests.filter((t) => t.authorId === user.id);
  const finished = DB.attempts.filter((a) => a.status === 'finished' && testById(a.testId));
  return shell(user, `
    <div class="panel-head">
      <div>
        <h1>Кабинет преподавателя</h1>
        <p class="muted">Вы — проводящий испытание: создаёте задания, задаёте критерии, проверяете результаты.</p>
      </div>
      <a class="btn" href="#/tests/new">+ Новое испытание</a>
    </div>
    <div class="grid stats" style="margin-bottom:18px">
      <div class="stat"><div class="value">${tests.length}</div><div class="label">моих испытаний</div></div>
      <div class="stat"><div class="value">${tests.filter((t) => t.published).length}</div><div class="label">опубликовано</div></div>
      <div class="stat"><div class="value">${finished.length}</div><div class="label">завершённых попыток</div></div>
      <div class="stat"><div class="value">${DB.users.filter((u) => u.role === 'student').length}</div><div class="label">учащихся</div></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2 style="margin:0">Последние испытания</h2><a class="small" href="#/tests">все →</a></div>
      ${tests.length ? tests.slice(0, 4).map((t) => `
        <a class="card" href="#/tests/${t.id}" style="color:inherit;margin-bottom:10px">
          <div class="title">${esc(t.title)}</div>
          <div class="meta">
            <span>${t.questions.length} вопр.</span>
            <span>${MODE_LABEL[t.mode]}</span>
            <span>${SUBJECT_LABEL[t.subject]}</span>
            ${t.published ? '<span class="tag ok">опубликовано</span>' : '<span class="tag">черновик</span>'}
          </div>
        </a>`).join('') : '<p class="muted">Пока нет испытаний. Создайте первое.</p>'}
    </div>`);
}

function homeStudent(user) {
  const tests = DB.tests.filter((t) => t.published);
  const myAttempts = DB.attempts.filter((a) => a.studentId === user.id);
  return shell(user, `
    <div class="panel-head">
      <div>
        <h1>Доступные испытания</h1>
        <p class="muted">Режим обучения показывает разбор, тестирование — нет.</p>
      </div>
      <a class="btn ghost" href="#/attempts">Мои попытки</a>
    </div>
    <div class="grid stats" style="margin-bottom:18px">
      <div class="stat"><div class="value">${tests.length}</div><div class="label">доступно</div></div>
      <div class="stat"><div class="value">${myAttempts.length}</div><div class="label">моих попыток</div></div>
      <div class="stat"><div class="value">${myAttempts.filter((a) => a.status === 'finished').length}</div><div class="label">завершено</div></div>
      <div class="stat"><div class="value">${esc(user.group || '—')}</div><div class="label">группа</div></div>
    </div>
    <div class="grid cards">
      ${tests.length ? tests.map((t) => `
        <div class="card">
          <div class="title">${esc(t.title)}</div>
          <div class="meta">
            <span class="tag ${t.mode === 'training' ? 'info' : ''}">${MODE_LABEL[t.mode]}</span>
            <span class="tag">${SUBJECT_LABEL[t.subject]}</span>
          </div>
          <p class="small muted">${esc(t.description || 'Без описания')}</p>
          <div class="meta small">
            <span>${t.questions.length} вопр.</span><span>${t.duration} мин</span><span>${maxScore(t)} баллов</span>
            ${t.camera ? '<span>🎥 камера</span>' : ''}${t.mic ? '<span>🎙 микрофон</span>' : ''}
          </div>
          <div class="btn-row" style="margin-top:auto"><a class="btn" href="#/run/${t.id}">Пройти</a></div>
        </div>`).join('') : '<div class="panel"><p class="muted" style="margin:0">Пока нет опубликованных испытаний.</p></div>'}
    </div>`);
}

/* ============================ испытания (преподаватель) ============================ */

function viewTests(user) {
  if (user.role !== 'teacher') return shell(user, '<div class="panel">Доступно только преподавателю.</div>');
  const tests = DB.tests.filter((t) => t.authorId === user.id);
  return shell(user, `
    <div class="panel-head"><h1>Мои испытания</h1><a class="btn" href="#/tests/new">+ Новое испытание</a></div>
    <div class="panel">
      ${tests.length ? `<table><thead><tr><th>Название</th><th>Режим</th><th>Объект</th><th>Вопросы</th><th>Баллы</th><th>Статус</th><th></th></tr></thead>
      <tbody>${tests.map((t) => `
        <tr>
          <td><a href="#/tests/${t.id}">${esc(t.title)}</a><div class="muted small">${fmtDate(t.createdAt)}</div></td>
          <td><span class="tag ${t.mode === 'training' ? 'info' : ''}">${MODE_LABEL[t.mode]}</span></td>
          <td class="small">${t.subject === 'human' ? 'человек' : 'имитация'}</td>
          <td class="mono">${t.questions.length}</td>
          <td class="mono">${maxScore(t)}</td>
          <td>${t.published ? '<span class="tag ok">опубликовано</span>' : '<span class="tag">черновик</span>'}</td>
          <td class="right"><a class="btn ghost small" href="#/tests/${t.id}">Открыть</a></td>
        </tr>`).join('')}</tbody></table>` : '<p class="muted">Пусто. Создайте первое испытание.</p>'}
    </div>`);
}

function viewTestNew(user) {
  if (user.role !== 'teacher') return shell(user, '<div class="panel">Доступно только преподавателю.</div>');
  return shell(user, `
    <div class="panel-head"><h1>Новое испытание</h1><a class="btn ghost" href="#/tests">Назад</a></div>
    <div class="panel" style="max-width:720px">
      <div id="newError" class="alert error hidden"></div>
      <div class="field"><label for="title">Название</label><input id="title" type="text" placeholder="Например: Собеседование по теме «Датчики»"></div>
      <div class="field"><label for="description">Описание</label><textarea id="description" placeholder="Что проверяем и в каком порядке"></textarea></div>
      <div class="field-row">
        <div class="field"><label for="mode">Режим</label><select id="mode">
          <option value="testing">Тестирование (без подсказок)</option>
          <option value="training">Обучение (с разбором)</option>
        </select></div>
        <div class="field"><label for="subject">На ком проводится</label><select id="subject">
          <option value="human">Человек</option><option value="imitation">Имитация предметами</option>
        </select></div>
        <div class="field"><label for="duration">Время, мин</label><input id="duration" type="number" min="1" max="600" value="15"></div>
      </div>
      <div class="field"><label for="criteria">Критерии оценки (по ним будет работать нейропроверка)</label>
        <textarea id="criteria" placeholder="Полнота ответа, корректность терминов, связность изложения"></textarea></div>
      <div class="field-row">
        <label class="checkbox"><input type="checkbox" id="camera" checked> Камера</label>
        <label class="checkbox"><input type="checkbox" id="mic" checked> Микрофон</label>
      </div>
      <button class="btn" onclick="createTest()">Создать и добавить вопросы</button>
    </div>`);
}

function createTest() {
  const user = currentUser();
  const title = document.getElementById('title').value.trim();
  if (title.length < 3) {
    const box = document.getElementById('newError');
    box.textContent = 'Название — минимум 3 символа';
    box.classList.remove('hidden');
    return;
  }
  const test = {
    id: DB.seq.test++,
    authorId: user.id,
    title,
    description: document.getElementById('description').value.trim(),
    mode: document.getElementById('mode').value,
    subject: document.getElementById('subject').value,
    duration: Number(document.getElementById('duration').value || 15),
    criteria: document.getElementById('criteria').value.trim(),
    camera: document.getElementById('camera').checked,
    mic: document.getElementById('mic').checked,
    published: false,
    createdAt: Date.now(),
    questions: [],
  };
  DB.tests.push(test);
  saveDB();
  logAction('test_created', title);
  go('#/tests/' + test.id);
}

function viewTestEdit(user, id) {
  const test = testById(id);
  if (!test) return shell(user, '<div class="panel">Испытание не найдено.</div>');
  if (user.role !== 'teacher' || test.authorId !== user.id) return shell(user, '<div class="panel">Это не ваше испытание.</div>');

  return shell(user, `
    <div class="panel-head">
      <div>
        <h1>${esc(test.title)}</h1>
        <p class="muted">${esc(test.description || 'Без описания')} · ${test.duration} мин · максимум ${maxScore(test)} баллов</p>
      </div>
      <div class="btn-row">
        <a class="btn ghost" href="#/results">Результаты</a>
        <button class="btn" onclick="togglePublish(${test.id})">${test.published ? 'Снять с публикации' : 'Опубликовать'}</button>
      </div>
    </div>
    <div class="grid split-edit">
      <section class="panel">
        <div class="panel-head"><h2 style="margin:0">Вопросы (${test.questions.length})</h2></div>
        ${test.questions.length ? test.questions.map((q, index) => `
          <div class="question">
            <div class="q-head">
              <div>
                <div class="q-index">Вопрос ${index + 1} · ${q.points} б.</div>
                <div>${esc(q.text)}</div>
              </div>
              <button class="btn danger small" onclick="deleteQuestion(${test.id},${q.id})">Удалить</button>
            </div>
            <div class="small muted">Тип: ${q.kind}
              ${q.options.length ? ' · варианты: ' + esc(q.options.join(', ')) : ''}
              ${q.correct ? ' · ответ: ' + esc(Array.isArray(q.correct) ? q.correct.join(', ') : q.correct) : ''}
            </div>
          </div>`).join('') : '<p class="muted">Вопросов пока нет — добавьте первый справа.</p>'}
      </section>
      <section class="panel">
        <h2 style="margin-top:0">Добавить вопрос</h2>
        <div id="qError" class="alert error hidden"></div>
        <div class="field"><label for="qtext">Текст вопроса</label><textarea id="qtext"></textarea></div>
        <div class="field"><label for="qkind">Тип</label><select id="qkind" onchange="toggleQuestionFields()">
          <option value="single">Один вариант</option>
          <option value="multiple">Несколько вариантов</option>
          <option value="text">Текстовый ответ (сверка с эталоном)</option>
          <option value="text_manual">Текстовый ответ (ручная проверка)</option>
        </select></div>
        <div class="field" id="optionsField"><label for="qoptions">Варианты (по одному в строке)</label><textarea id="qoptions"></textarea></div>
        <div class="field" id="correctField"><label for="qcorrect">Правильный ответ (по одному в строке)</label><textarea id="qcorrect"></textarea></div>
        <div class="field"><label for="qpoints">Баллы</label><input id="qpoints" type="number" min="0" max="100" step="0.5" value="1"></div>
        <div class="field"><label for="qhint">Подсказка (только режим обучения)</label><input id="qhint" type="text"></div>
        <button class="btn" style="width:100%" onclick="addQuestion(${test.id})">Добавить</button>
      </section>
    </div>`);
}

function toggleQuestionFields() {
  const kind = document.getElementById('qkind').value;
  document.getElementById('optionsField').classList.toggle('hidden', !(kind === 'single' || kind === 'multiple'));
  document.getElementById('correctField').classList.toggle('hidden', kind === 'text_manual');
}

function addQuestion(testId) {
  const test = testById(testId);
  const text = document.getElementById('qtext').value.trim();
  const box = document.getElementById('qError');
  if (!text) {
    box.textContent = 'Введите текст вопроса';
    box.classList.remove('hidden');
    return;
  }
  const kind = document.getElementById('qkind').value;
  const lines = (id) => document.getElementById(id).value.split('\n').map((s) => s.trim()).filter(Boolean);
  const options = (kind === 'single' || kind === 'multiple') ? lines('qoptions') : [];
  const correctLines = lines('qcorrect');
  let correct = null;
  if (kind === 'single') correct = correctLines[0] || null;
  else if (kind === 'multiple' || kind === 'text') correct = correctLines.length ? correctLines : null;

  test.questions.push({
    id: DB.seq.question++,
    text, kind, options, correct,
    points: Number(document.getElementById('qpoints').value || 1),
    hint: document.getElementById('qhint').value.trim(),
  });
  saveDB();
  logAction('question_added', text.slice(0, 60));
  router();
}

function deleteQuestion(testId, questionId) {
  const test = testById(testId);
  test.questions = test.questions.filter((q) => q.id !== questionId);
  saveDB();
  logAction('question_deleted', String(questionId));
  router();
}

function togglePublish(testId) {
  const test = testById(testId);
  test.published = !test.published;
  saveDB();
  logAction('test_published', String(test.published));
  router();
}

/* ============================ прохождение ============================ */

function viewRun(user, testId) {
  const test = testById(testId);
  if (!test || !test.published) return shell(user, '<div class="panel">Испытание недоступно.</div>');

  let attempt = DB.attempts.find((a) => a.testId === test.id && a.studentId === user.id && a.status === 'in_progress');
  if (!attempt) {
    attempt = {
      id: DB.seq.attempt++,
      testId: test.id,
      studentId: user.id,
      status: 'in_progress',
      mode: test.mode,
      subject: test.subject,
      startedAt: Date.now(),
      finishedAt: null,
      answers: {},
      score: 0,
      maxScore: maxScore(test),
      manualScore: null,
      comment: '',
      neural: 'pending',
      media: { camera: false, mic: false, seconds: 0 },
    };
    DB.attempts.push(attempt);
    saveDB();
    logAction('attempt_started', test.title);
  }

  const html = shell(user, `
    <div class="panel-head">
      <div>
        <h1>${esc(test.title)}</h1>
        <p class="muted">${test.mode === 'training' ? 'Режим обучения — с разбором ответов' : 'Режим тестирования — без подсказок'}
          · ${SUBJECT_LABEL[test.subject]} · ${test.questions.length} вопр. · ${maxScore(test)} баллов</p>
      </div>
      <div class="btn-row">
        <span class="tag info" id="timerTag">00:00</span>
        <button class="btn ghost" onclick="abortAttempt(${attempt.id})">Прервать</button>
        <button class="btn" onclick="finishAttempt(${attempt.id})">Завершить</button>
      </div>
    </div>
    ${test.criteria ? `<div class="alert info"><strong>Критерии оценки:</strong> ${esc(test.criteria)}</div>` : ''}
    <div class="run-shell">
      <div>
        ${test.questions.map((q, index) => questionBlock(q, index, test, attempt)).join('')}
      </div>
      <aside>
        <div class="panel" style="margin-bottom:14px">
          <h3 style="margin-top:0">Рабочее место</h3>
          <div class="media-box" id="mediaBox">
            <div class="media-placeholder" id="mediaPlaceholder">Камера выключена</div>
            <video id="cam" autoplay playsinline muted class="hidden"></video>
          </div>
          <div class="btn-row" style="margin-top:10px">
            ${test.camera ? '<button class="btn ghost small" id="camBtn" onclick="toggleCamera()">Включить камеру</button>' : ''}
            ${test.mic ? '<button class="btn ghost small" id="micBtn" onclick="toggleMic()">Включить микрофон</button>' : ''}
          </div>
          <div style="margin-top:12px">
            <div class="muted small" style="display:flex;justify-content:space-between"><span>Микрофон</span><span id="micState">выкл</span></div>
            <div class="meter"><div id="micLevel"></div></div>
          </div>
          <div class="muted small" style="margin-top:10px">Медиа: <span id="mediaMeta">камера выкл · микрофон выкл · 0 с</span></div>
        </div>
        <div class="panel">
          <h3 style="margin-top:0">Прогресс</h3>
          <div class="timeline" id="timeline"></div>
          <div style="margin-top:12px" class="muted small">Отвечено: <span id="answeredCount">${Object.keys(attempt.answers).length}</span> / ${test.questions.length}</div>
        </div>
      </aside>
    </div>`);

  setTimeout(() => {
    renderTimeline(test, attempt);
    const seconds = Math.floor((Date.now() - attempt.startedAt) / 1000);
    const tag = document.getElementById('timerTag');
    if (tag) tag.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    timerHandle = setInterval(() => {
      const elapsed = Math.floor((Date.now() - attempt.startedAt) / 1000);
      const timerTag = document.getElementById('timerTag');
      if (timerTag) timerTag.textContent = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
    }, 1000);
  }, 0);

  return html;
}

function questionBlock(question, index, test, attempt) {
  const saved = attempt.answers[question.id];
  const value = saved ? saved.value : null;
  let body = '';

  if (question.kind === 'single') {
    body = question.options.map((option) => `
      <label class="option ${value === option ? 'selected' : ''}">
        <input type="radio" name="q${question.id}" value="${esc(option)}"
          ${value === option ? 'checked' : ''}
          onchange="answerSingle(${attempt.id},${question.id},this)">
        <span>${esc(option)}</span>
      </label>`).join('');
  } else if (question.kind === 'multiple') {
    const current = Array.isArray(value) ? value : [];
    body = question.options.map((option) => `
      <label class="option ${current.includes(option) ? 'selected' : ''}">
        <input type="checkbox" value="${esc(option)}" ${current.includes(option) ? 'checked' : ''}
          onchange="answerMultiple(${attempt.id},${question.id})">
        <span>${esc(option)}</span>
      </label>`).join('');
  } else {
    body = `<textarea oninput="markDirty(${question.id})">${esc(value || '')}</textarea>
      <div class="btn-row" style="margin-top:8px">
        <button class="btn ghost small" onclick="answerText(${attempt.id},${question.id})">Сохранить ответ</button>
        <span class="muted small">Ручной ввод текста</span>
      </div>`;
  }

  const feedback = saved && test.mode === 'training'
    ? feedbackHtml(saved, question)
    : '<div class="feedback hidden" data-feedback></div>';

  return `
    <div class="question" data-qid="${question.id}">
      <div class="q-head">
        <div class="q-main">
          <div class="q-meta">
            <span class="q-index">Вопрос ${index + 1} из ${test.questions.length} · ${question.points} б.</span>
            <span class="tag ${saved ? 'info' : ''}" data-status>${saved ? 'сохранён' : 'не отвечен'}</span>
          </div>
          <div class="q-text">${esc(question.text)}</div>
        </div>
      </div>
      ${body}
      ${feedback}
    </div>`;
}

function feedbackHtml(saved, question) {
  if (saved.correct === true) {
    return `<div class="feedback ok">Верно (+${saved.points})</div>`;
  }
  if (saved.correct === false) {
    const correct = question.correct ? (Array.isArray(question.correct) ? question.correct.join(', ') : question.correct) : '';
    return `<div class="feedback bad">Неверно (${saved.points} б.)${correct ? ' · Правильный ответ: ' + esc(correct) : ''}${question.hint ? ' · Подсказка: ' + esc(question.hint) : ''}</div>`;
  }
  return `<div class="feedback neutral">Ответ сохранён · проверит преподаватель${question.hint ? ' · ' + esc(question.hint) : ''}</div>`;
}

function renderTimeline(test, attempt) {
  const wrap = document.getElementById('timeline');
  if (!wrap) return;
  wrap.innerHTML = test.questions.map((q, index) => `
    <div class="row ${attempt.answers[q.id] ? 'done' : ''}">
      <span class="n">${index + 1}</span><span>Вопрос ${index + 1}</span>
    </div>`).join('');
  const counter = document.getElementById('answeredCount');
  if (counter) counter.textContent = Object.keys(attempt.answers).length;
}

function storeAnswer(attemptId, questionId, value) {
  const attempt = attemptById(attemptId);
  const test = testById(attempt.testId);
  const question = test.questions.find((q) => q.id === Number(questionId));
  const [correct, points] = checkAnswer(question, value);
  attempt.answers[question.id] = { value, correct, points };
  attempt.score = Math.round(Object.values(attempt.answers).reduce((sum, a) => sum + Number(a.points || 0), 0) * 100) / 100;
  saveDB();
  renderTimeline(test, attempt);
  return { test, attempt, question, correct, points };
}

function answerSingle(attemptId, questionId, input) {
  document.querySelectorAll(`.question[data-qid="${questionId}"] .option`)
    .forEach((el) => el.classList.toggle('selected', el.contains(input)));
  afterAnswer(storeAnswer(attemptId, questionId, input.value), questionId, attemptId);
}

function answerMultiple(attemptId, questionId) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const values = [...box.querySelectorAll('input[type=checkbox]:checked')].map((input) => input.value);
  box.querySelectorAll('.option').forEach((el) => el.classList.toggle('selected', !!el.querySelector('input:checked')));
  if (!values.length) return;
  afterAnswer(storeAnswer(attemptId, questionId, values), questionId, attemptId);
}

function answerText(attemptId, questionId) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  afterAnswer(storeAnswer(attemptId, questionId, box.querySelector('textarea').value), questionId, attemptId);
}

function markDirty(questionId) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const tag = box.querySelector('[data-status]');
  tag.textContent = 'не сохранён';
  tag.className = 'tag warn';
}

function afterAnswer({ test, attempt, question }, questionId, attemptId) {
  const box = document.querySelector(`.question[data-qid="${questionId}"]`);
  const tag = box.querySelector('[data-status]');
  tag.textContent = 'сохранён';
  tag.className = 'tag info';
  if (test.mode !== 'training') return;
  const saved = attempt.answers[question.id];
  const holder = box.querySelector('[data-feedback]');
  if (holder) holder.outerHTML = feedbackHtml(saved, question);
}

/* ---------------- камера/микрофон ---------------- */

function updateMediaMeta() {
  const el = document.getElementById('mediaMeta');
  if (!el) return;
  el.textContent = `камера ${camStream ? 'вкл' : 'выкл'} · микрофон ${micStream ? 'вкл' : 'выкл'} · ${window.__mediaSeconds || 0} с`;
}

async function toggleCamera() {
  const button = document.getElementById('camBtn');
  if (camStream) {
    camStream.getTracks().forEach((track) => track.stop());
    camStream = null;
    document.getElementById('cam').classList.add('hidden');
    const placeholder = document.getElementById('mediaPlaceholder');
    placeholder.classList.remove('hidden');
    placeholder.textContent = 'Камера выключена';
    if (button) button.textContent = 'Включить камеру';
    updateMediaMeta();
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true });
    const video = document.getElementById('cam');
    video.srcObject = camStream;
    video.classList.remove('hidden');
    document.getElementById('mediaPlaceholder').classList.add('hidden');
    if (button) button.textContent = 'Выключить камеру';
    updateMediaMeta();
  } catch (error) {
    document.getElementById('mediaPlaceholder').textContent = 'Нет доступа к камере: ' + error.message;
  }
}

async function toggleMic() {
  const button = document.getElementById('micBtn');
  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    if (audioCtx) { audioCtx.close(); audioCtx = null; }
    cancelAnimationFrame(rafId);
    micStream = null;
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
      document.getElementById('micLevel').style.width = Math.min(100, (sum / buffer.length) * 1.8) + '%';
      rafId = requestAnimationFrame(loop);
    };
    loop();
    document.getElementById('micState').textContent = 'вкл';
    if (button) button.textContent = 'Выключить микрофон';
    updateMediaMeta();
  } catch (error) {
    document.getElementById('micState').textContent = 'нет доступа';
  }
}

function finishAttempt(attemptId) {
  const attempt = attemptById(attemptId);
  attempt.status = 'finished';
  attempt.finishedAt = Date.now();
  attempt.media = { camera: !!camStream, mic: !!micStream, seconds: Math.floor((Date.now() - attempt.startedAt) / 1000) };
  saveDB();
  logAction('attempt_finished', `балл ${attempt.score}`);
  stopCameras();
  go('#/attempt/' + attempt.id);
}

function abortAttempt(attemptId) {
  const attempt = attemptById(attemptId);
  if (!confirm('Прервать испытание? Ответы сохранятся, попытка будет помечена как прерванная.')) return;
  attempt.status = 'aborted';
  attempt.finishedAt = Date.now();
  saveDB();
  logAction('attempt_aborted', '');
  stopCameras();
  go('#/attempts');
}

function stopCameras() {
  if (camStream) { camStream.getTracks().forEach((track) => track.stop()); camStream = null; }
  if (micStream) { micStream.getTracks().forEach((track) => track.stop()); micStream = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
  cancelAnimationFrame(rafId);
}

/* ============================ попытки и результаты ============================ */

function viewAttempts(user) {
  const attempts = DB.attempts.filter((a) => a.studentId === user.id).sort((a, b) => b.startedAt - a.startedAt);
  const statusTag = (status) => status === 'finished'
    ? '<span class="tag ok">завершено</span>'
    : (status === 'in_progress' ? '<span class="tag info">в процессе</span>' : '<span class="tag bad">прервано</span>');

  return shell(user, `
    <div class="panel-head"><h1>Мои попытки</h1><a class="btn ghost" href="#/">К испытаниям</a></div>
    <div class="panel">
      ${attempts.length ? `<table><thead><tr><th>Испытание</th><th>Режим</th><th>Начало</th><th>Статус</th><th>Баллы</th><th>Нейро</th><th></th></tr></thead>
      <tbody>${attempts.map((a) => {
        const test = testById(a.testId) || { title: '—' };
        return `<tr>
          <td>${esc(test.title)}</td>
          <td><span class="tag ${a.mode === 'training' ? 'info' : ''}">${MODE_LABEL[a.mode]}</span></td>
          <td class="small mono">${fmtDate(a.startedAt)}</td>
          <td>${statusTag(a.status)}</td>
          <td class="mono">${a.manualScore != null ? a.manualScore : a.score} / ${a.maxScore}</td>
          <td><span class="tag warn">${a.neural}</span></td>
          <td class="right"><a class="btn ghost small" href="#/attempt/${a.id}">Подробнее</a></td>
        </tr>`;
      }).join('')}</tbody></table>` : '<p class="muted">Вы ещё не проходили испытания.</p>'}
    </div>`);
}

function viewAttempt(user, attemptId) {
  const attempt = attemptById(attemptId);
  if (!attempt) return shell(user, '<div class="panel">Попытка не найдена.</div>');
  if (user.role === 'student' && attempt.studentId !== user.id) return shell(user, '<div class="panel">Это не ваша попытка.</div>');
  if (attempt.status === 'in_progress') return viewRun(user, attempt.testId);

  const test = testById(attempt.testId);
  const rows = test.questions.map((q, index) => {
    const saved = attempt.answers[q.id];
    const value = saved ? (Array.isArray(saved.value) ? saved.value.join(', ') : saved.value) : '';
    const verdict = !saved ? '<span class="tag">нет ответа</span>'
      : (saved.correct === true ? '<span class="tag ok">верно</span>'
        : (saved.correct === false ? '<span class="tag bad">неверно</span>' : '<span class="tag warn">на проверке</span>'));
    const correct = q.correct ? (Array.isArray(q.correct) ? q.correct.join(', ') : q.correct) : '';
    return `<div class="question">
      <div class="q-head">
        <div><div class="q-index">Вопрос ${index + 1} · ${q.points} б.</div><div>${esc(q.text)}</div></div>
        ${verdict}
      </div>
      <div class="small"><span class="muted">Ваш ответ:</span> ${esc(value || '—')}</div>
      <div class="small muted" style="margin-top:4px">Начислено: ${saved ? saved.points : 0} б.</div>
      ${attempt.mode === 'training' && correct ? `<div class="feedback neutral" style="margin-top:8px">Правильный ответ: ${esc(correct)}${q.hint ? '<br>Подсказка: ' + esc(q.hint) : ''}</div>` : ''}
    </div>`;
  }).join('');

  return shell(user, `
    <div class="panel-head">
      <div>
        <h1>${esc(test.title)}</h1>
        <p class="muted">${MODE_LABEL[attempt.mode]} · ${SUBJECT_LABEL[attempt.subject]} · начато ${fmtDate(attempt.startedAt)}</p>
      </div>
      <a class="btn ghost" href="${user.role === 'teacher' ? '#/results' : '#/attempts'}">Назад</a>
    </div>
    <div class="grid stats" style="margin-bottom:18px">
      <div class="stat"><div class="value">${attempt.manualScore != null ? attempt.manualScore : attempt.score}</div><div class="label">итоговый балл из ${attempt.maxScore}</div></div>
      <div class="stat"><div class="value">${attempt.score}</div><div class="label">по алгоритму</div></div>
      <div class="stat"><div class="value">${Object.keys(attempt.answers).length}</div><div class="label">ответов</div></div>
      <div class="stat"><div class="value">${attempt.media.camera ? '🎥' : '—'} ${attempt.media.mic ? '🎙' : ''}</div><div class="label">медиа (заглушка)</div></div>
    </div>
    ${attempt.manualScore != null ? `<div class="alert ok"><strong>Оценка преподавателя:</strong> ${attempt.manualScore} б.${attempt.comment ? ' — ' + esc(attempt.comment) : ''}</div>` : ''}
    <div class="alert info"><strong>Нейропроверка:</strong> ${attempt.neural} — в демо-версии модель не подключена.</div>
    <div class="panel"><h2 style="margin-top:0">Разбор ответов</h2>${rows}</div>`);
}

function viewResults(user) {
  if (user.role !== 'teacher') return shell(user, '<div class="panel">Доступно только преподавателю.</div>');
  const mine = DB.attempts.filter((a) => { const t = testById(a.testId); return t && t.authorId === user.id; })
    .sort((a, b) => b.startedAt - a.startedAt);

  return shell(user, `
    <div class="panel-head">
      <h1>Результаты испытаний</h1>
      <span class="muted small">Оценка = алгоритм + ручной ввод; нейропроверка — заглушка</span>
    </div>
    <div class="panel">
      ${mine.length ? `<table><thead><tr><th>Учащийся</th><th>Испытание</th><th>Режим</th><th>Медиа</th><th>Авто</th><th>Итог</th><th>Ручной ввод</th></tr></thead>
      <tbody>${mine.map((a) => {
        const student = userById(a.studentId) || { fullName: '—', email: '' };
        const test = testById(a.testId) || { title: '—' };
        return `<tr>
          <td>${esc(student.fullName)}<div class="muted small">${esc(student.email)}</div></td>
          <td>${esc(test.title)}<div class="muted small">${fmtDate(a.startedAt)}</div></td>
          <td><span class="tag ${a.mode === 'training' ? 'info' : ''}">${MODE_LABEL[a.mode]}</span></td>
          <td class="small">${a.media.camera ? '<span class="tag ok">🎥</span>' : ''} ${a.media.mic ? '<span class="tag ok">🎙</span>' : ''}<div class="muted mono">${a.media.seconds}с</div></td>
          <td class="mono">${a.score} / ${a.maxScore}</td>
          <td class="mono"><strong>${a.manualScore != null ? a.manualScore : a.score}</strong></td>
          <td>
            <div class="btn-row">
              <input type="number" step="0.5" min="0" max="${a.maxScore}" id="score-${a.id}" value="${a.manualScore != null ? a.manualScore : ''}" style="width:80px" placeholder="балл">
              <input type="text" id="comment-${a.id}" value="${esc(a.comment || '')}" placeholder="комментарий" style="width:150px">
              <button class="btn ghost small" onclick="saveManual(${a.id})">Сохранить</button>
              <a class="btn ghost small" href="#/attempt/${a.id}">Открыть</a>
            </div>
          </td>
        </tr>`;
      }).join('')}</tbody></table>` : '<p class="muted">Пока никто не проходил ваши испытания.</p>'}
    </div>`);
}

function saveManual(attemptId) {
  const attempt = attemptById(attemptId);
  const score = parseFloat(document.getElementById('score-' + attemptId).value);
  if (Number.isNaN(score)) { alert('Введите балл'); return; }
  if (score > attempt.maxScore) { alert('Балл не может быть больше максимума (' + attempt.maxScore + ')'); return; }
  attempt.manualScore = score;
  attempt.comment = document.getElementById('comment-' + attemptId).value.trim();
  saveDB();
  logAction('manual_result', `${score} б.`);
  router();
}

/* ============================ пользователи и логи ============================ */

function viewUsers(user) {
  if (user.role !== 'teacher') return shell(user, '<div class="panel">Доступно только преподавателю.</div>');
  return shell(user, `
    <div class="panel-head"><h1>Пользователи</h1><span class="muted small">роли и статусы</span></div>
    <div class="panel">
      <table><thead><tr><th>ФИО</th><th>Почта</th><th>Роль</th><th>Статус</th><th>Группа</th><th>Регистрация</th><th>Действия</th></tr></thead>
      <tbody>${DB.users.map((u) => `
        <tr>
          <td>${esc(u.fullName)}</td>
          <td class="small mono">${esc(u.email)}</td>
          <td><span class="tag ${u.role === 'teacher' ? 'ok' : 'info'}">${u.role === 'teacher' ? 'преподаватель' : 'учащийся'}</span></td>
          <td>${u.status === 'active' ? '<span class="tag ok">активен</span>' : '<span class="tag bad">заблокирован</span>'}</td>
          <td class="small">${esc(u.group || '—')}</td>
          <td class="small mono">${new Date(u.createdAt).toLocaleDateString('ru-RU')}</td>
          <td><div class="btn-row">
            <button class="btn ghost small" onclick="patchUser(${u.id},'role')">${u.role === 'teacher' ? 'Сделать учащимся' : 'Сделать преподавателем'}</button>
            <button class="btn ghost small" onclick="patchUser(${u.id},'status')">${u.status === 'active' ? 'Заблокировать' : 'Разблокировать'}</button>
          </div></td>
        </tr>`).join('')}</tbody></table>
    </div>`);
}

function patchUser(userId, field) {
  const target = userById(userId);
  const me = currentUser();
  if (field === 'role') {
    if (target.id === me.id) { alert('Нельзя снять роль с самого себя'); return; }
    target.role = target.role === 'teacher' ? 'student' : 'teacher';
  } else {
    if (target.id === me.id) { alert('Нельзя заблокировать себя'); return; }
    target.status = target.status === 'active' ? 'blocked' : 'active';
  }
  saveDB();
  logAction('user_updated', target.email);
  router();
}

function viewLogs(user) {
  if (user.role !== 'teacher') return shell(user, '<div class="panel">Доступно только преподавателю.</div>');
  return shell(user, `
    <div class="panel-head"><h1>Журнал действий</h1><span class="muted small">последние ${Math.min(DB.logs.length, 200)} записей</span></div>
    <div class="panel">
      ${DB.logs.length ? `<table><thead><tr><th>Время</th><th>Действие</th><th>Пользователь</th><th>Данные</th></tr></thead>
      <tbody>${DB.logs.slice(0, 200).map((l) => {
        const u = userById(l.userId);
        return `<tr>
          <td class="mono small">${new Date(l.at).toLocaleString('ru-RU')}</td>
          <td><span class="tag">${esc(l.action)}</span></td>
          <td class="small">${esc(u ? u.fullName : '—')}</td>
          <td class="small muted">${esc(l.detail)}</td>
        </tr>`;
      }).join('')}</tbody></table>` : '<p class="muted">Логов пока нет.</p>'}
    </div>`);
}

function viewInstruction(user) {
  return shell(user, `
    <div class="panel-head"><h1>Инструкция по ЭМП</h1></div>
    <div class="panel">
      <p class="muted">В рабочей версии здесь открывается полная инструкция по выполнению экстренной помощи
        со схемами и ссылкой на PDF. В демо-прототипе страница оставлена заглушкой.</p>
      <a class="btn ghost" href="#/">На главную</a>
    </div>`);
}

function viewTraining(user) {
  return shell(user, `
    <div class="panel-head"><h1>Обучение · тренировочный режим</h1></div>
    <div class="panel">
      <p class="muted">Тренировочный режим доступен в рабочей версии: запуск камеры, пробное прохождение
        без сохранения результата. В демо-прототипе — заглушка.</p>
      <a class="btn ghost" href="#/">На главную</a>
    </div>`);
}

function viewAccount(user) {
  return shell(user, `
    <div class="panel-head"><h1>Аккаунт</h1></div>
    <div id="accError" class="alert error hidden"></div>
    <div id="accOk" class="alert ok hidden"></div>
    <div class="grid split-two">
      <section class="panel">
        <h2 style="margin-top:0">Профиль</h2>
        <div class="field"><label>Почта</label><input type="text" value="${esc(user.email)}" disabled></div>
        <div class="field"><label>Роль</label><input type="text" value="${user.role === 'teacher' ? 'преподаватель' : 'учащийся'}" disabled></div>
        <div class="field"><label for="accName">ФИО</label><input id="accName" type="text" value="${esc(user.fullName)}"></div>
        <div class="field"><label for="accGroup">Группа</label><input id="accGroup" type="text" value="${esc(user.group || '')}"></div>
        <button class="btn" onclick="saveProfile()">Сохранить</button>
      </section>
      <section class="panel">
        <h2 style="margin-top:0">Смена пароля</h2>
        <div class="field"><label for="curPass">Текущий пароль</label><input id="curPass" type="password"></div>
        <div class="field"><label for="newPass">Новый пароль (минимум 6)</label><input id="newPass" type="password"></div>
        <div class="field"><label for="newPass2">Новый пароль ещё раз</label><input id="newPass2" type="password"></div>
        <button class="btn" onclick="changePassword()">Сменить пароль</button>
      </section>
    </div>`);
}

function saveProfile() {
  const user = currentUser();
  user.fullName = document.getElementById('accName').value.trim() || user.fullName;
  user.group = document.getElementById('accGroup').value.trim();
  saveDB();
  logAction('profile_updated', '');
  router();
}

function changePassword() {
  const user = currentUser();
  const current = document.getElementById('curPass').value;
  const next = document.getElementById('newPass').value;
  const next2 = document.getElementById('newPass2').value;
  const err = document.getElementById('accError');
  const ok = document.getElementById('accOk');
  err.classList.add('hidden');
  ok.classList.add('hidden');

  if (current !== user.password) { err.textContent = 'Текущий пароль неверный'; err.classList.remove('hidden'); return; }
  if (next.length < 6) { err.textContent = 'Новый пароль — минимум 6 символов'; err.classList.remove('hidden'); return; }
  if (next !== next2) { err.textContent = 'Пароли не совпадают'; err.classList.remove('hidden'); return; }
  user.password = next;
  saveDB();
  logAction('password_changed', '');
  ok.textContent = 'Пароль изменён';
  ok.classList.remove('hidden');
}

/* ============================ старт ============================ */

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', () => {
  loadDB();
  if (!window.location.hash) window.location.hash = DB.session ? '#/' : '#/login';
  router();
});
