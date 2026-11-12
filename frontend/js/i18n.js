/* Перевод интерфейса RU -> EN без перезагрузки страницы.
 *
 * Как работает: словарь фраз + обход текстовых узлов DOM.
 * Серверные данные (названия испытаний, вопросы, ФИО, комментарии) не переводятся —
 * переводим только оболочку интерфейса.
 */
(function () {
  "use strict";

  // фразы интерфейса: русский -> английский
  var DICT = {
    // меню и оболочка
    "Экстренка": "Ekstrenka",
    "Меню": "Menu",
    "Доступные испытания": "Available tests",
    "Обучение": "Training",
    "Мои попытки": "My attempts",
    "Инструкция по ЭМП": "Emergency care guide",
    "Главная": "Home",
    "Испытания": "Tests",
    "Результаты": "Results",
    "Пользователи": "Users",
    "Логи": "Logs",
    "преподаватель": "teacher",
    "учащийся": "student",
    "Аккаунт": "Account",
    "Выйти": "Log out",
    "Войти": "Log in",
    "Вход": "Log in",
    "Вход в систему": "Sign in",
    "Регистрация": "Sign up",
    "Зарегистрироваться": "Sign up",
    "Создать аккаунт": "Create account",
    "Нет аккаунта?": "No account yet?",
    "Уже есть аккаунт?": "Already have an account?",
    "Почта": "Email",
    "Пароль": "Password",
    "Пароль (минимум 6 символов)": "Password (6 characters minimum)",
    "ФИО": "Full name",
    "Группа": "Group",
    "Группа (необязательно)": "Group (optional)",
    "Кем вы будете в системе?": "Who are you?",
    "Учащийся": "Student",
    "Проводящий испытание (преподаватель)": "Examiner (teacher)",
    "Демонстрационные аккаунты. После первого входа смените пароль в разделе «Аккаунт».":
      "Demo accounts. Change the password in the Account section after your first sign-in.",
    "Уже созданы для демонстрации — можно войти, не регистрируясь.":
      "Already created for the demo — you can sign in without registering.",
    "демо-доступы": "demo logins",
    "пароль teacher123 · проводящий испытание": "password teacher123 · examiner",
    "пароль student123 · учащийся": "password student123 · student",
    "Или создайте свой аккаунт формой выше.": "Or create your own account with the form above.",

    // главная учащегося
    "Выберите испытание — откроется рабочее место с вопросами, камерой и разбором ответов.":
      "Pick a test — the workspace with questions, camera and answer review will open.",
    "Пока нет опубликованных испытаний. Загляните позже.": "No published tests yet. Check back later.",
    "Попыток ещё не было.": "No attempts yet.",
    "Пока нет испытаний. Создайте первое — это займёт минуту.":
      "No tests yet. Create your first one — it takes a minute.",
    "доступно испытаний": "tests available",
    "моих попыток": "my attempts",
    "завершённых попыток": "completed attempts",
    "баллов": "points",
    "балл": "point",
    "вопр.": "q.",
    "лимит": "limit",
    "мин": "min",
    "Начать": "Start",
    "Продолжить": "Continue",
    "Пройти": "Take",
    "Открыть": "Open",
    "Подробнее": "Details",
    "все →": "all →",
    "войти →": "open →",
    "подставить →": "open →",

    // кабинет преподавателя
    "Кабинет преподавателя": "Teacher dashboard",
    "Вы — проводящий испытание: создаёте задания, задаёте критерии, проверяете результаты.":
      "You are the examiner: create tests, set criteria, review results.",
    "Новое испытание": "New test",
    "Последние испытания": "Latest tests",
    "Последние попытки": "Latest attempts",
    "Пока никто не проходил ваши испытания.": "Nobody has taken your tests yet.",
    "учащихся в системе": "students in the system",
    "опубликовано": "published",
    "черновик": "draft",
    "Испытания: обучение и тестирование": "Tests: training and examination",
    "Создать испытание": "Create test",
    "Создать и добавить вопросы": "Create and add questions",
    "Название": "Title",
    "Описание": "Description",
    "Режим": "Mode",
    "Обучение (с разбором)": "Training (with review)",
    "Тестирование (без подсказок)": "Examination (no hints)",
    "Субъект испытания": "Test subject",
    "Человек": "Person",
    "Имитация предметами": "Simulation with objects",
    "Время, мин": "Time, min",
    "Критерии оценки (по ним будет работать нейропроверка)":
      "Assessment criteria (used by the automatic check)",
    "Вопросы": "Questions",
    "Добавить вопрос": "Add question",
    "Текст вопроса": "Question text",
    "Тип": "Type",
    "Один вариант": "Single choice",
    "Несколько вариантов": "Multiple choice",
    "Текстовый ответ (сверка с эталоном)": "Text answer (checked against reference)",
    "Текстовый ответ (ручная проверка)": "Text answer (manual check)",
    "Варианты (по одному в строке)": "Options (one per line)",
    "Правильный ответ (по одному в строке / для текста — эталон)":
      "Correct answer (one per line / reference text)",
    "Подсказка (только режим обучения)": "Hint (training mode only)",
    "Баллы": "Points",
    "Сохранить": "Save",
    "Сохранить выбор": "Save choice",
    "Удалить": "Delete",
    "Добавить": "Add",
    "Вопросов пока нет — добавьте первый справа.": "No questions yet — add the first one on the right.",
    "Пусто. Создайте первое испытание.": "Empty. Create your first test.",
    "Опубликовать": "Publish",
    "Снять с публикации": "Unpublish",
    "Заблокировать": "Block",
    "Разблокировать": "Unblock",
    "Сделать учащимся": "Make student",
    "Сделать преподавателем": "Make teacher",
    "Результаты испытаний": "Test results",
    "Пользователь": "User",
    "Роль": "Role",
    "Статус": "Status",
    "Группа": "Group",
    "Начало": "Started",
    "Итог": "Result",
    "Действия": "Actions",
    "Действие": "Action",
    "Данные": "Data",
    "Журнал действий": "Activity log",
    "Логов пока нет.": "No log entries yet.",
    "последние": "latest",
    "записей": "entries",
    "Ручной ввод": "Manual grade",
    "Оценка = алгоритм (авто) + ручной ввод; нейропроверка — заглушка":
      "Score = algorithm (auto) + manual grade; automatic check is a stub",
    "комментарий": "comment",
    "активен": "active",
    "заблокирован": "blocked",
    "в процессе": "in progress",
    "завершено": "completed",
    "завершённых": "completed",
    "прервано": "aborted",
    "ожидает": "pending",
    "роли и статусы": "roles and statuses",

    // страница результата
    "Все попытки": "All attempts",
    "тестирование": "examination",
    "обучение": "training",
    "на человеке": "on a person",
    "имитация предметами": "simulation with objects",
    "начато": "started",
    "итоговый балл": "final score",
    "по ответам (авто)": "from answers (auto)",
    "отвечено вопросов": "questions answered",
    "медиа (камера/микрофон)": "media (camera/microphone)",
    "выставил преподаватель": "set by the teacher",
    "автоматически": "automatically",
    "перекрыт оценкой преподавателя": "overridden by the teacher's grade",
    "итог считается по этому баллу": "the final score uses this value",
    "не отвечен ни один": "none answered",
    "ответы сохранены": "answers saved",
    "камера и микрофон не включались": "camera and microphone were not used",
    "длительность работы медиа": "media session length",
    "Балл выставлен вручную.": "The score was set manually.",
    "Автоматическая проверка не начислила ни одного балла, потому что ответов нет, — итог взят из оценки преподавателя.":
      "The automatic check awarded nothing because there are no answers, so the teacher's grade is used.",
    "Оценка преподавателя:": "Teacher's grade:",
    "Нейропроверка:": "Automatic check:",
    "выполнена": "completed",
    "модуль отключён — балл выставлен по алгоритму критериев":
      "module disabled — the score comes from the criteria algorithm",
    "ожидает проверки": "pending",
    "Разбор ответов": "Answer review",
    "Вопрос": "Question",
    "Ваш ответ:": "Your answer:",
    "Начислено:": "Awarded:",
    "Правильный ответ:": "Correct answer:",
    "Подсказка:": "Hint:",
    "верно": "correct",
    "неверно": "wrong",
    "на проверке": "pending",
    "нет ответа": "no answer",
    "не отвечен": "not answered",
    "Вернуться на главную": "Back to home",
    "На главную": "Home",
    "К испытаниям": "To tests",
    "Назад": "Back",
    "Время:": "Time:",
    "Прогресс": "Progress",
    "Отвечено:": "Answered:",
    "Завершить": "Finish",
    "Прервать": "Abort",
    "Сохранить ответ": "Save answer",

    // рабочее место / камера
    "Камера": "Camera",
    "Микрофон": "Microphone",
    "Включить камеру": "Turn camera on",
    "Выключить камеру": "Turn camera off",
    "Включить микрофон": "Turn microphone on",
    "Камера выключена": "Camera is off",
    "Нажмите «Включить камеру» и разрешите доступ в браузере.":
      "Press “Turn camera on” and allow access in the browser.",
    "Микрофон пока только фиксирует факт включения.":
      "For now the microphone only records that it was switched on.",
    "Кадры с камеры уходят на сервер, где считается техника (темп, глубина, положение рук).":
      "Camera frames go to the server, which evaluates technique (rate, depth, hand position).",
    "Видео не записывается и не хранится — в результате остаются только числа.":
      "Video is not recorded or stored — only numbers remain in the result.",
    "Под видео появится плашка «Анализ техники»: темп, глубина, положение рук.":
      "A “Technique analysis” panel appears under the video: rate, depth, hand position.",
    "Медиа:": "Media:",
    "Камера доступна только по защищённому адресу (https://). ":
      "The camera is only available over a secure address (https://). ",
    "Сейчас страница открыта по http:// — откройте сайт через https, и камера включится.":
      "The page is open over http:// — open the site over https and the camera will work.",
    "Камера занята другой программой (Zoom, Teams, Skype). Закройте её и повторите.":
      "The camera is busy in another app (Zoom, Teams, Skype). Close it and retry.",
    "Камера не найдена. Подключите её и повторите попытку.":
      "Camera not found. Connect it and try again.",
    "Ответ сохранён": "Answer saved",
    "Отвечайте на вопросы — в режиме обучения сразу виден разбор.":
      "Answer the questions — in training mode the review shows up immediately.",
    "В режиме обучения вердикт показывается сразу после ответа.":
      "In training mode the verdict appears right after answering.",
    "Нажмите «Завершить» — получите результат и разбор ошибок.":
      "Press “Finish” to get the result and a breakdown of mistakes.",
    "Выберите испытание. Режим обучения показывает разбор, тестирование — нет.":
      "Pick a test. Training mode shows the review, examination mode does not.",
    "Откройте испытание — начнётся попытка, включится таймер.":
      "Open a test — the attempt starts and the timer begins.",

    // обучение / тренировка
    "Как проходит обучение": "How training works",
    "Задача станции:": "Station task:",
    "Ознакомление с брифингом": "Read the briefing",
    "Алгоритм действий (ABCDE)": "Action algorithm (ABCDE)",
    "Подготовка": "Preparation",
    "Обеспечение:": "Support:",
    "Условия:": "Conditions:",
    "Критерии оценки:": "Assessment criteria:",
    "Взаимодействие с помощником (медбрат/медсестра)": "Working with an assistant (nurse)",
    "Переход по маршруту": "Route handover",
    "Тайминг": "Timing",
    "Голосовая команда": "Voice prompt",
    "Прогресс": "Progress",

    // прочее
    "Профиль": "Profile",
    "Смена пароля": "Change password",
    "Сменить пароль": "Change password",
    "Текущий пароль": "Current password",
    "Новый пароль": "New password",
    "Новый пароль ещё раз": "New password again",
    "Почта и роль меняются только администратором.": "Email and role can only be changed by an administrator.",
    "Минимум 8 символов. После смены пароля все текущие сессии останутся активными.":
      "At least 8 characters. All current sessions stay active after the change.",
    "Ошибка": "Error",
    "СЛР:": "CPR:",
    "Компрессии:": "Compressions:",
    "Динамика:": "Trend:",
    "Подтверждение:": "Confirmation:",
    "АНД:": "AED:",
    "камера": "camera",
    "микрофон": "microphone",
    "звук": "sound",
    "видео": "video",
    "выкл": "off",
    "Не": "No",
    "Авто": "Auto",
    "Нейро": "Auto",
    "Медиа": "Media",
    "Баллы": "Points",
    "Сценарии станции (на выбор АПК)": "Station scenarios (chosen by the equipment)",
    "Открыть полный паспорт станции (PDF)": "Open the full station passport (PDF)",
    "Паспорт станции на fmza.ru": "Station passport on fmza.ru",
    "Инструкция по выполнению экстренной помощи": "Emergency care instructions",
    "Инструкция по выполнению действий при оказании экстренной медицинской помощи":
      "Instructions for emergency medical care",
    "Общие положения": "General provisions",
    "При остановке кровообращения": "In cardiac arrest",
    "Продолжение работы": "Continuing work",
    "Начало работы": "Starting work",
    // добавлено в v16: недостающие подписи интерфейса
    "Палитра": "Palette",
    "Язык": "Language",
    "Выбор запоминается в этом браузере": "Your choice is saved in this browser",
    "Оформление и язык": "Appearance and language",
    "Русский": "Russian",
    "Тёмная синяя": "Dark blue",
    "Тёмная изумрудная": "Dark emerald",
    "Тёмная фиолетовая": "Dark violet",
    "Тёмная графитовая": "Dark graphite",
    "Светлая синяя": "Light blue",
    "Светлая изумрудная": "Light emerald",
    "Светлая тёплая": "Light warm",
    "Светлая фиолетовая": "Light violet",
    "Мои испытания": "My tests",
    "моих испытаний": "my tests",
    "+ Новое испытание": "+ New test",
    "Объект": "Subject",
    "Испытание": "Test",
    "На ком проводится": "Who takes part",
    "человек": "person",
    "Рабочее место": "Workspace",
    "Можно уточнить перед началом.": "You can change it before you start.",
    "Время": "Time",
    "Продолжительность:": "Duration:",
    "Критерии оценивания (кратко)": "Assessment criteria (briefly)",
    "Ручной ввод: можно печатать сюда или отвечать голосом — текст вводится вручную":
      "Manual entry: type here; voice answers are typed in by hand",
    "Вопросы (": "Questions (",
    "ожидает проверки.": "pending.",
    "Необязательно": "Optional",
    "заглушка": "stub",
    "имитация": "imitation",
    "имитация предметами": "imitation with props",
    "модуль отключён — балл выставлен по алгоритму критериев.":
      "module is off — the score is calculated by the criteria algorithm.",
    "Оценка = алгоритм (авто) + ручной ввод; нейропроверка — заглушка":
      "Score = algorithm (auto) + manual entry; neural check is a stub",
    "Видеотест": "Video test",
    "Видеотест: алгоритм станции ЭМП": "Video test: emergency care station algorithm",
    "Отвечено": "Answered",
    "Проверка ответа сразу": "Answer checked immediately",
    "Зачёт: разбор в конце": "Exam mode: review at the end",
    "Завершить и увидеть разбор": "Finish and see the review",
    "Верно": "Correct",
    "Неверно — правильный вариант:": "Incorrect — correct option:",
    "Ответа нет — правильный вариант:": "No answer — correct option:",
    "Ответ принят — вердикт будет в конце": "Answer accepted — verdict at the end",
    "Паспорт станции:": "Station passport:",
    "Результат": "Result",
    "Прошлые прохождения": "Previous attempts",
    "Пройти заново": "Start over",
    "Обучение": "Training",
    "Зачёт": "Exam",
    "Правильный вариант": "Correct option",
    "Нажмите на картинку — откроется крупно.": "Click a picture to open it full size.",
    "Открыть крупно": "Open full size",
    "группа": "group",
    "критерии": "criteria",
    "Вопрос": "Question",
    "Пункт": "Item",
    "Вариант 1": "Option 1",
    "Вариант 2": "Option 2",
    "Вариант 3": "Option 3",
    "Введите ответ...": "Type your answer...",
    "Например: Собеседование по теме «Датчики»": "Example: Interview on the topic “Sensors”",
    "Что проверяем и в каком порядке": "What we check and in which order",
    "Например: полнота ответа, корректность терминов, связность изложения":
      "Example: completeness, correct terminology, coherent reasoning",
    "Что нужно ответить?": "What should the answer contain?",
    "Тип": "Type",
    "варианты": "options",
    "ответ": "answer",
    "максимум": "maximum",
    "🎙 микрофон": "🎙 mic",
    "🎥 камера": "🎥 camera",

    // рабочее место: памятка по съёмке
    "Как поставить камеру и встать в кадре": "How to place the camera and stay in frame",
    "Камера строго сбоку и с другой стороны манекена, чем тот, кто делает компрессии: иначе спина закрывает руки. Расстояние 2–3 метра, высота — на уровне груди.":
      "Camera strictly to the side and on the opposite side of the mannequin from the rescuer: otherwise the back blocks the arms. Distance 2–3 metres, height at chest level.",
    "В кадре должны быть голова, плечи и руки целиком. Кисти не должны уходить за край кадра — иначе глубина и положение рук не считаются.":
      "The frame must show the head, shoulders and both arms completely. The hands must not leave the frame, otherwise depth and hand position cannot be measured.",
    "Проверка за 10 секунд: запишите короткое видео и посмотрите, видно ли кисти в самой нижней точке нажатия. Если кисти срезаны — отодвиньте камеру или поднимите её чуть выше.":
      "Ten-second check: record a short clip and see whether the hands are visible at the lowest point of compressions. If they are cut off, move the camera back or raise it slightly.",
    "Уже созданы для демонстрации — можно войти, не регистрируясь. Или создайте свой аккаунт формой выше.":
      "They already exist for the demo — sign in without registering. Or create your own account with the form above.",
    "Выберите испытание — откроется рабочее место с вопросами, камерой и разбором ответов. В режиме обучения вердикт показывается сразу после ответа.":
      "Pick a test — the workspace with questions, camera and answer review opens. In training mode the verdict appears right after answering.",
    "«Войдите на станцию и озвучьте свой логин»": "“Enter the station and say your login out loud”",
    "«Ознакомьтесь с заданием станции»": "“Read the station task”",
    "«Перейдите на следующую станцию»": "“Move on to the next station”",
    "«У Вас осталась одна минута»": "“You have one minute left”",
    "Кадры с камеры уходят на сервер, где считается техника (темп, глубина, положение рук). Видео не записывается и не хранится — в результате остаются только числа. Микрофон пока только фиксирует факт включения.":
      "Camera frames go to the server, which evaluates technique (rate, depth, hand position). Video is not recorded or stored — only numbers remain in the result. The microphone only records that it was switched on.",
    "Если станция занята другой попыткой, вы встанете в очередь — плашка покажет вашу позицию и примерное время ожидания. Прохождение при этом не блокируется.":
      "If the station is busy with another attempt, you join the queue — the banner shows your position and the approximate wait. You can still take the test."

  };

  // шаблоны с числами/переменными
  var PATTERNS = [
    [/^Вопрос (\d+) · (.+)$/, "Question $1 · $2"],
    [/^Вопрос (\d+) из (\d+) · (.+)$/, "Question $1 of $2 · $3"],
    [/^Вопрос (\d+)$/, "Question $1"],
    [/^из (\S+)$/, "of $1"],
    [/^(\d+) б\.$/, "$1 pts"],
    [/^1 балл$/, "1 point"],
    [/^(\d+) баллов$/, "$1 points"],
    [/^1 вопр\.$/, "1 question"],
    [/^(\d+) вопр\.$/, "$1 questions"],
    [/^(\d+) мин$/, "$1 min"],
    [/^лимит (\d+) мин$/, "limit $1 min"],
    [/^начато (.+)$/, "started $1"],
    [/^последние (\d+) записей$/, "latest $1 entries"],
    [/^камера выкл · микрофон выкл · (\d+) с$/, "camera off · mic off · $1 s"],
    [/^итоговый балл · (.+)$/, "final score · $1"],
    [/^(\d+) с$/, "$1 s"],
    [/^(\d+) мин (\d+) с$/, "$1 min $2 s"],
    [/^(\d+) б\. из (\d+) б\.$/, "$1 of $2 pts"],
    [/^из (\S+) · (\d+)$/, "of $1 · $2"],
    [/^(.+) · (\d+)%$/, "$1 · $2%"],
    [/^Начислено: (\d+) б\. из (\d+) б\.$/, "Awarded: $1 of $2 pts"],
    [/(\d+) вопр\./, "$1 questions"],
    [/(\d+) баллов/, "$1 points"],
    [/максимум (\d+) баллов/, "maximum $1 points"],
    [/^(обучение|тестирование) · (на человеке|имитация предметами) · начато (.+)$/,
     "training · on a person · started $3"],
    [/^Режим обучения — с разбором ответов · (на человеке|имитация предметами) · (\d+) вопр\. · (\d+) баллов$/,
     "Training mode — with answer review · $1 · $2 questions · $3 points"],
    [/^Режим тестирования — без подсказок · (на человеке|имитация предметами) · (\d+) вопр\. · (\d+) баллов$/,
     "Examination mode — no hints · $1 · $2 questions · $3 points"],
    [/^Тип: (\S+) · варианты: (.+) · ответ: (.+)$/, "Type: $1 · options: $2 · answer: $3"],
    [/^Тип: (\S+)$/, "Type: $1"],
    [/^максимум (\d+) баллов$/, "maximum $1 points"],
    [/^Вопросы \((\d+)\)$/, "Questions ($1)"],
    [/^Вопрос (\d+) из (\d+) · (.+)$/, "Question $1 of $2 · $3"],
    [/^Вопрос (\d+) · (.+)$/, "Question $1 · $2"]
  ];

  // расширенный словарь (страницы-справки, демо-данные, видеотест) подключается файлом i18n_extra.js
  var EXTRA_PATTERNS = [];
  if (window.I18N_EXTRA) {
    Object.keys(window.I18N_EXTRA).forEach(function (key) {
      if (key === "__patterns") return;
      if (!Object.prototype.hasOwnProperty.call(DICT, key)) DICT[key] = window.I18N_EXTRA[key];
    });
    (window.I18N_EXTRA.__patterns || []).forEach(function (pair) {
      EXTRA_PATTERNS.push([new RegExp(pair[0]), pair[1]]);
    });
  }

  var TEXT_ATTRS = ["placeholder", "title", "aria-label"];

  // единицы и обрывки, которые надо чинить и после основного перевода
  function polishUnits(text) {
    return text
      .replace(/(\d+(?:[.,]\d+)?)\s*б\./g, "$1 pts")
      .replace(/(\d+)\s*баллов/g, "$1 points")
      .replace(/(\d+)\s*балл\b/g, "$1 point")
      .replace(/(\d+)\s*мин\b/g, "$1 min")
      .replace(/(\d+) pts из (\d+) pts/g, "$1 of $2 pts")
      .replace(/(\d+) (?:балл\w*|pts) из (\d+) (?:балл\w*|pts)/g, "$1 of $2 pts")
      .replace(/(\d+)\s*вопр\./g, "$1 questions")
      .replace(/\bначато\b/g, "started")
      .replace(/\bна человеке\b/g, "on a person")
      .replace(/\bимитация предметами\b/g, "simulation with objects")
      .replace(/\bобучение\b/g, "training")
      .replace(/\bтестирование\b/g, "examination");
  }

  /* шаблон, который должен совпасть со всей строкой (^…$) — он точнее частичного */
  function isAnchored(pattern) {
    var source = pattern.source;
    return source.charAt(0) === "^" && source.charAt(source.length - 1) === "$";
  }

  function translateLine(key) {
    if (Object.prototype.hasOwnProperty.call(DICT, key)) return DICT[key];
    var all = PATTERNS.concat(EXTRA_PATTERNS);
    // сначала точные шаблоны на всю строку, потом частичные: иначе /(\d+) баллов/
    // съест «максимум 10 баллов» раньше, чем сработает /^максимум (\d+) баллов$/
    var ordered = all.filter(function (pair) { return isAnchored(pair[0]); })
      .concat(all.filter(function (pair) { return !isAnchored(pair[0]); }));
    for (var i = 0; i < ordered.length; i++) {
      if (ordered[i][0].test(key)) return key.replace(ordered[i][0], ordered[i][1]);
    }
    return null;
  }

  /* сколько в строке русских букв — по нему выбираем лучший вариант перевода */
  function cyrillicCount(text) {
    var found = String(text).match(/[А-Яа-яЁё]/g);
    return found ? found.length : 0;
  }

  /* перевод по частям, разделённым «·»: «Режим обучения · имитация · 2 баллов» */
  function translateParts(text) {
    var pieces = text.split("·");
    if (pieces.length < 2) return null;
    var changed = false;
    var out = pieces.map(function (piece) {
      var part = piece.trim();
      if (!part) return "";
      var line = translateLine(part);
      if (line !== null) { changed = true; return line; }
      return part;
    });
    return changed ? out.filter(Boolean).join(" · ") : null;
  }

  function translateString(text) {
    var raw = String(text).trim();
    if (!raw) return null;

    var candidates = [];

    // 1) точное совпадение со словарём или шаблоном
    var direct = translateLine(raw);
    if (direct !== null) candidates.push(direct);

    // 2) многострочный текст (placeholder из нескольких вариантов) — по строкам
    if (raw.indexOf("\n") >= 0) {
      var changed = false;
      var lines = raw.split("\n").map(function (line) {
        var t = line.trim();
        if (!t) return "";
        var r = translateLine(t);
        if (r !== null) { changed = true; return r; }
        return t;
      });
      if (changed) candidates.push(lines.filter(Boolean).join("\n"));
    }

    // 3) переносы строк и отступы внутри абзаца — как обычные пробелы
    var flat = raw.replace(/\s+/g, " ");
    if (flat !== raw) {
      var found = translateLine(flat);
      if (found !== null) candidates.push(found);
    }

    // 4) фраза склеена из кусков через «·» — переводим каждый кусок
    var parts = translateParts(flat);
    if (parts !== null) candidates.push(parts);

    if (!candidates.length) {
      var polishedOnly = polishUnits(flat);
      return polishedOnly !== flat ? polishedOnly : null;
    }

    // выбираем вариант с наименьшим числом русских букв
    var best = null;
    var bestScore = cyrillicCount(raw);
    candidates.forEach(function (candidate) {
      var polished = polishUnits(candidate);
      var score = cyrillicCount(polished);
      if (score < bestScore || (best === null && score <= bestScore)) {
        best = polished;
        bestScore = score;
      }
    });
    return best;
  }

  var SKIP = { SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, TEXTAREA: 1 };
  // текст внутри textarea не трогаем, но placeholder/title/aria-label переводим
  var SKIP_ATTR = { SCRIPT: 1, STYLE: 1, CODE: 1 };

  // оригинальные русские значения: чтобы можно было вернуть язык назад
  var originalText = new WeakMap();
  var originalAttrs = new WeakMap(); // элемент -> { attr: исходное значение }

  function rememberAttr(el, attr, value) {
    var map = originalAttrs.get(el);
    if (!map) { map = {}; originalAttrs.set(el, map); }
    if (!Object.prototype.hasOwnProperty.call(map, attr)) map[attr] = value;
  }

  function rememberText(node, value) {
    if (!originalText.has(node)) originalText.set(node, value);
  }

  function restore(node) {
    if (!node) return;
    var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
    var queue = [node];
    while (walker.nextNode()) queue.push(walker.currentNode);
    queue.forEach(function (n) {
      if (n.nodeType === 3 && originalText.has(n)) n.nodeValue = originalText.get(n);
      if (n.nodeType === 1) {
        var map = originalAttrs.get(n);
        if (map) Object.keys(map).forEach(function (attr) { n.setAttribute(attr, map[attr]); });
      }
    });
  }

  function walkText(node) {
    if (!node || SKIP[node.parentNode && node.parentNode.nodeName]) return;
    if (node.nodeType === 3) {
      var out = translateString(node.nodeValue);
      if (out !== null) node.nodeValue = node.nodeValue.replace(node.nodeValue.trim(), out);
      return;
    }
    if (node.nodeType !== 1) return;
  }

  function translateTree(root) {
    if (!root) return;
    if (root.nodeType === 1 && SKIP[root.nodeName]) return;
    // атрибуты
    if (root.nodeType === 1) {
      TEXT_ATTRS.forEach(function (attr) {
        var val = root.getAttribute && root.getAttribute(attr);
        if (val) {
          var out = translateString(val);
          if (out !== null) root.setAttribute(attr, out);
        }
      });
    }
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode;
        while (p) {
          if (p.nodeName && SKIP[p.nodeName]) return NodeFilter.FILTER_REJECT;
          p = p.parentNode;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (n) {
      var out = translateString(n.nodeValue);
      if (out !== null) {
        rememberText(n, n.nodeValue);
        n.nodeValue = n.nodeValue.replace(n.nodeValue.trim(), out);
      }
    });
    if (root.nodeType === 1) {
      var els = root.querySelectorAll ? root.querySelectorAll("*") : [];
      Array.prototype.forEach.call(els, function (el) {
        if (SKIP_ATTR[el.nodeName]) return;
        TEXT_ATTRS.forEach(function (attr) {
          var val = el.getAttribute(attr);
          if (!val) return;
          var out = translateString(val);
          if (out !== null) {
            rememberAttr(el, attr, val);
            el.setAttribute(attr, out);
          }
        });
      });
    }
  }

  var observer = null;

  function startObserver() {
    if (observer || !window.MutationObserver) return;
    observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        Array.prototype.forEach.call(m.addedNodes, function (n) {
          if (n.nodeType === 1 || n.nodeType === 3) translateTree(n.nodeType === 3 ? n.parentNode : n);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  /* заголовок вкладки: «Обучение · Экстренка» → «Training · Ekstrenka» */
  function translateTitle() {
    var parts = String(document.title).split("·");
    var out = parts.map(function (part) {
      var text = part.trim();
      if (!text) return "";
      var result = translateLine(text);
      return result !== null ? result : text;
    }).filter(Boolean);
    if (out.length) document.title = out.join(" · ");
  }

  window.I18N = {
    dict: DICT,
    translate: translateString,
    apply: function (lang) {
      document.documentElement.lang = lang;
      if (lang === "en") {
        translateTree(document.body);
        translateTitle();
        startObserver();
      } else {
        if (observer) { observer.disconnect(); observer = null; }
        restore(document.body);
      }
    }
  };
})();
