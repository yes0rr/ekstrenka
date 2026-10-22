// Проверка логики preview.html без браузера: минимальные заглушки DOM.
// Запуск из корня проекта:  node tools/check_preview.js
const fs = require('fs');
const vm = require('vm');

const store = {};
const els = {};
function el(id) {
  if (!els[id]) {
    els[id] = {
      id, value: '', textContent: '', innerHTML: '', outerHTML: '',
      style: {}, dataset: {}, checked: false,
      classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
      querySelector(){ return null; }, querySelectorAll(){ return []; },
      getContext(){ return null; }, appendChild(){},
    };
  }
  return els[id];
}

global.window = {
  location: { hash: '#/login' },
  addEventListener(){}, scrollTo(){},
  AudioContext: function(){ return { createMediaStreamSource(){return {connect(){}};},
    createAnalyser(){ return { fftSize:0, frequencyBinCount:0, getByteFrequencyData(){}, connect(){} }; },
    close(){} }; },
};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = v; },
  removeItem: (k) => { delete store[k]; },
};
global.document = {
  getElementById: el,
  querySelector(){ return null; },
  querySelectorAll(){ return []; },
  addEventListener(){},
};
global.confirm = () => true;
let lastAlert = '';
global.alert = (m) => { lastAlert = String(m); };
global.navigator = { mediaDevices: {} };
global.setInterval = () => 0; global.clearInterval = () => {}; global.setTimeout = (f) => { try { f(); } catch(e){} return 0; };
global.cancelAnimationFrame = () => {}; global.requestAnimationFrame = () => 0;
global.fetch = () => { throw new Error('fetch не должен вызываться в демо'); };

let code = fs.readFileSync('frontend/js/preview_app.js', 'utf8');
// лексические let/const не видны снаружи — выставляем геттеры
code += `
globalThis.__api = {
  get DB() { return DB; },
  loadDB, currentUser, userById, testById, attemptById, checkAnswer, storeAnswer,
  finishAttempt, saveManual, patchUser, viewHome, viewRun, viewAttempt, viewResults,
  viewUsers, viewLogs, createTest, addQuestion, togglePublish, feedbackHtml, doLogin, doRegister, go,
};`;
const sandbox = { window: global.window, localStorage: global.localStorage, document: global.document,
  confirm: global.confirm, alert: global.alert, navigator: global.navigator, setInterval: global.setInterval,
  clearInterval: global.clearInterval, setTimeout: global.setTimeout, cancelAnimationFrame, requestAnimationFrame,
  fetch: global.fetch, console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: 'preview_app.js' });

const api = null; // заполним после запуска
function call(name, ...args) {
  const fn = (sandbox.__api && sandbox.__api[name]) || sandbox[name];
  if (typeof fn !== 'function') throw new Error('нет функции ' + name);
  return fn(...args);
}

const out = [];
function check(label, cond, extra) {
  out.push((cond ? 'PASS  ' : 'FAIL  ') + label + (extra ? ' → ' + extra : ''));
  if (!cond) process.exitCode = 1;
}

// --- инициализация ---
const A = sandbox.__api;
call('loadDB');
check('демо-данные созданы', A.DB.users.length === 2 && A.DB.tests.length === 1);

// --- вход ---
sandbox.document.getElementById('email').value = 'student@example.com';
sandbox.document.getElementById('password').value = 'wrong';
const errBefore = A.DB.session;
call('doLogin');
check('неверный пароль не пускает', A.DB.session === errBefore);

sandbox.document.getElementById('password').value = 'student123';
call('doLogin');
check('вход учащимся', A.DB.session === 2);

// --- регистрация ---
sandbox.document.getElementById('fullName').value = 'Новый Студент';
sandbox.document.getElementById('regEmail').value = 'new@test.ru';
sandbox.document.getElementById('regPassword').value = 'secret123';
sandbox.document.getElementById('regRole').value = 'student';
sandbox.document.getElementById('regGroup').value = 'РИ-22';
call('doRegister');
check('регистрация создаёт пользователя', A.DB.users.some(u => u.email === 'new@test.ru'));
const newId = A.DB.session;

// --- студент видит опубликованное испытание ---
const home = call('viewHome', call('currentUser'));
check('главная учащегося содержит испытание', home.includes('Базовое собеседование'));

// --- прохождение ---
const run = call('viewRun', call('currentUser'), '1');
check('страница прохождения рендерится', run.includes('Вопрос 1 из 3'));
const attempt = A.DB.attempts.find(a => a.studentId === newId);
check('попытка создана', !!attempt);

// верный одиночный
let res = call('storeAnswer', attempt.id, 1, 'Человек');
check('одиночный: верно', res.correct === true && res.points === 1);
// множественный частичный
res = call('storeAnswer', attempt.id, 2, ['Макет']);
check('множественный: частичный балл', res.correct === false && res.points === 0.5, String(res.points));
// множественный полный
res = call('storeAnswer', attempt.id, 2, ['Макет', 'Стенд']);
check('множественный: полный', res.correct === true && res.points === 2);
// текстовый с ручной проверкой
res = call('storeAnswer', attempt.id, 3, 'Подготовка, проведение, протокол');
check('text_manual: на проверку', res.correct === null && res.points === 0);

call('finishAttempt', attempt.id);
check('попытка завершена', attempt.status === 'finished' && attempt.score === 3, 'score=' + attempt.score);
const resultPage = call('viewAttempt', call('currentUser'), String(attempt.id));
check('страница результата рендерится', resultPage.includes('Разбор ответов'));

// --- преподаватель: ручная оценка, пользователи, логи ---
A.DB.session = 1;
const results = call('viewResults', call('currentUser'));
check('результаты видят попытку', results.includes('Новый Студент'));
sandbox.document.getElementById('score-' + attempt.id).value = '5';
sandbox.document.getElementById('comment-' + attempt.id).value = 'Хорошо';
call('saveManual', attempt.id);
check('ручная оценка сохранена', attempt.manualScore === 5 && attempt.comment === 'Хорошо');

const usersPage = call('viewUsers', call('currentUser'));
check('страница пользователей рендерится', usersPage.includes('new@test.ru'));
call('patchUser', newId, 'status');
check('блокировка работает', A.userById(newId).status === 'blocked');
lastAlert = '';
call('patchUser', 1, 'role');
check('нельзя снять роль с себя', A.userById(1).role === 'teacher' && lastAlert.includes('самого себя'), lastAlert);

const logsPage = call('viewLogs', call('currentUser'));
check('логи пишутся', logsPage.includes('manual_result') && logsPage.includes('attempt_finished'));

// --- создание испытания и вопроса ---
sandbox.document.getElementById('title').value = 'Новое испытание';
sandbox.document.getElementById('description').value = 'Описание';
sandbox.document.getElementById('mode').value = 'training';
sandbox.document.getElementById('subject').value = 'imitation';
sandbox.document.getElementById('duration').value = '20';
sandbox.document.getElementById('criteria').value = 'Критерии';
sandbox.document.getElementById('camera').checked = true;
sandbox.document.getElementById('mic').checked = true;
call('createTest');
const created = A.DB.tests[A.DB.tests.length - 1];
check('испытание создано', created.title === 'Новое испытание' && created.published === false);

sandbox.document.getElementById('qtext').value = 'Столица Франции?';
sandbox.document.getElementById('qkind').value = 'single';
sandbox.document.getElementById('qoptions').value = 'Париж\nЛион';
sandbox.document.getElementById('qcorrect').value = 'Париж';
sandbox.document.getElementById('qpoints').value = '2';
sandbox.document.getElementById('qhint').value = 'Эйфелева башня';
call('addQuestion', created.id);
check('вопрос добавлен', created.questions.length === 1 && created.questions[0].points === 2);

call('togglePublish', created.id);
check('публикация переключается', created.published === true);

// --- режим обучения: разбор виден ---
A.DB.session = newId;
A.userById(newId).status = 'active';
const trainAttempt = { id: 999, testId: created.id, studentId: newId, status: 'in_progress', mode: 'training',
  subject: 'imitation', startedAt: Date.now(), finishedAt: null, answers: {}, score: 0, maxScore: 2,
  manualScore: null, comment: '', neural: 'pending', media: { camera:false, mic:false, seconds:0 } };
A.DB.attempts.push(trainAttempt);
const r2 = call('storeAnswer', 999, created.questions[0].id, 'Лион');
const fb = call('feedbackHtml', trainAttempt.answers[created.questions[0].id], created.questions[0]);
check('обучение: неверно + разбор', r2.correct === false && fb.includes('Правильный ответ') && fb.includes('Эйфелева'));

console.log(out.join('\n'));
const failed = out.filter(l => l.startsWith('FAIL')).length;
console.log('\n' + (failed ? `${failed} проверок упало` : `все ${out.length} проверок прошли`));
