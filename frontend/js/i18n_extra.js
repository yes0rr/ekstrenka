/* Расширенный словарь RU → EN.
 *
 * Основной словарь интерфейса лежит в i18n.js; здесь — то, что переводится редко,
 * но без него английская версия выглядела недопереведённой:
 *   • страница-справка по экстренной помощи (алгоритм и сценарии станции);
 *   • демонстрационные данные (названия испытаний, ФИО демо-аккаунтов);
 *   • страница видеотеста;
 *   • «мелочи»: статусы, подписи полей, буквы ролей.
 *
 * Формат: объект «русская фраза»: «english phrase» и необязательный ключ __patterns —
 * список [регулярное выражение строкой, замена] для фраз с числами.
 */
(function () {
  "use strict";

  window.I18N_EXTRA = {
    // ---------- видеотест ----------
    "Видеотест": "Video test",
    "Видеотест: алгоритм станции": "Video test: station algorithm",
    "Видеотест: алгоритм станции ЭМП": "Video test: emergency care station algorithm",
    "Девять коротких фрагментов реального прохождения станции «Экстренная медицинская помощь». В каждом — один вопрос о том, что делает врач и что должно быть дальше.":
      "Nine short clips from a real run of the Emergency Medical Care station. Each clip has one question about what the doctor is doing and what comes next.",
    "Девять коротких фрагментов реального прохождения станции «Экстренная медицинская помощь».":
      "Nine short clips from a real run of the Emergency Medical Care station.",
    "вердикт сразу после ответа": "verdict right after the answer",
    "вердикт и разбор — в конце": "verdict and review at the end",
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
    "Зачем это": "Why this exists",
    "Обучение": "Training",
    "Зачёт": "Exam",
    "Видео без звука — это нарезка из записи станции; нижняя плашка с пунктами оценочного листа срезана, чтобы не подсказывать.":
      "The video has no sound: it is cut from a recording of the station, and the checklist banner is cropped out so it cannot give hints.",
    "Клавиши 1–4 выбирают вариант, Enter отправляет итог.":
      "Keys 1–4 pick an option, Enter finishes.",
    "В каждом — один вопрос о том, что делает врач и что должно быть дальше.":
      "Each clip has one question about what the doctor is doing and what comes next.",
    "То, что камера увидеть не может, закрывается вопросами — а не выдуманными критериями.":
      "What a camera cannot see is covered by questions — not by invented criteria.",
    "Видеотест проверяет знание последовательности действий по паспорту станции: оценка сознания и дыхания, вызов СМП, АНД, разряд, вентиляция 30:2.":
      "The video test checks knowledge of the action sequence in the station passport: checking consciousness and breathing, calling the ambulance, AED, shock, 30:2 ventilation.",
    "Основание: паспорт экзаменационной станции «Экстренная медицинская помощь», алгоритм и оценочный лист (50 пунктов).":
      "Source: the passport of the examination station “Emergency Medical Care”, the algorithm and the 50-item checklist.",
    "Ответить голосом": "Answer by voice",
    "Слушаю…": "Listening…",
    "Слушаю… (Стоп)": "Listening… (Stop)",
    "не похоже ни на один из вариантов ответа": "not close to any of the answer options",
    "Стоп": "Stop",
    "Сказать ещё раз": "Say it again",
    "Не разобрал ответ — попробуйте ещё раз или выберите вариант вручную.":
      "Could not make out the answer — try again or pick an option manually.",
    "Голосовой ответ: скажите, что делает врач, например «пульсоксиметрия» или «тридцать на два».":
      "Voice answer: say what the doctor does, for example “pulse oximetry” or “thirty to two”.",
    "Голос распознаётся браузером и никуда не записывается — на сервер уходит только текст.":
      "Speech is recognised by your browser and is not recorded — only the text goes to the server.",
    "Голос распознаётся браузером и никуда не записывается — на сервер уходит только текст.":
      "Speech is recognised by your browser and is not recorded — only the text goes to the server.",
    "В этом браузере голосовой ответ недоступен — работает в Chrome и Edge. Выберите вариант вручную.":
      "Voice answers are not available in this browser — they work in Chrome and Edge. Please pick an option manually.",
    "Микрофон недоступен. Разрешите доступ к микрофону в настройках браузера.":
      "Microphone is unavailable. Allow microphone access in your browser settings.",
    "Услышано:": "Heard:",
    "Понял как вариант": "Understood as option",
    "уверенность": "confidence",

    // ---------- демо-данные ----------
    "Студент Демо": "Student Demo",
    "Преподаватель Демо": "Teacher Demo",
    "РИ-21": "RI-21",
    "Тренировка: базовая СЛР": "Training: basic CPR",
    "Станция ОСКЭ: Экстренная медицинская помощь": "OSCE station: emergency medical care",
    "Тренировочный режим — с подсказками и разбором после каждого ответа.":
      "Training mode — with hints and review after each answer.",
    "Базовая станция первичной аккредитации: обследование пациента в экстренной ситуации.":
      "Basic primary accreditation station: examining a patient in an emergency.",

    // ---------- мелкие подписи ----------
    "П": "T",
    "У": "S",
    "Иванов Иван": "Ivan Ivanov",
    "попытка открыта": "attempt open",
    "в процессе": "in progress",
    "завершено": "finished",
    "прервано": "aborted",

    "Вы ещё не проходили испытания.": "You have not taken any tests yet.",
    "Пока нет опубликованных испытаний. Преподаватель должен создать испытание и нажать «Опубликовать».":
      "No published tests yet. The examiner needs to create a test and press “Publish”.",
    "Режим прохождения": "Test mode",
    "Пока нет записей.": "No entries yet.",

    // ---------- страница-справка по экстренной помощи ----------
    "Основано на «Паспорте экзаменационной станции «Экстренная медицинская помощь»» (первичная аккредитация / первичная специализированная аккредитация, ОСКЭ).":
      "Based on the passport of the examination station “Emergency Medical Care” (primary accreditation / primary specialised accreditation, OSCE).",
    "демонстрация навыков обследования пациента с резким ухудшением состояния в условиях амбулаторно-поликлинической МО, умение использовать укладку экстренной медицинской помощи и распознавать остановку кровообращения с применением при необходимости автоматического наружного дефибриллятора (АНД).":
      "demonstration of skills in examining a patient whose condition deteriorates sharply in an outpatient setting, ability to use the emergency care kit and to recognise circulatory arrest, applying an automated external defibrillator (AED) when indicated.",
    "общее время выполнения навыка — 10 минут. Время на станции — не менее 8,5 минут (при досрочном выполнении аккредитуемый остаётся до команды «Перейдите на следующую станцию»).":
      "total skill time is 10 minutes. Time at the station is at least 8.5 minutes (if you finish early, stay until told “Move to the next station”).",
    "пациент 45 лет (ориентировочно ~60 кг, рост 165 см), имеется периферический венозный катетер. Рядом — укладка ЭМП и АНД. Медбрат/медсестра — помощник, не знает причин ухудшения состояния.":
      "patient aged 45 (~60 kg, height 165 cm) with a peripheral venous catheter. The emergency kit and AED are nearby. The nurse is an assistant and does not know the cause of the deterioration.",
    "Острый коронарный синдром (ОКС1), кардиогенный шок": "Acute coronary syndrome (ACS1), cardiogenic shock",
    "Острый коронарный синдром (ОКС2), отёк лёгких": "Acute coronary syndrome (ACS2), pulmonary oedema",
    "Анафилактический шок (АШ)": "Anaphylactic shock",
    "Желудочно-кишечное кровотечение (ЖКК)": "Gastrointestinal bleeding",
    "Бронхообструктивный синдром на фоне бронхиальной астмы (БОС)": "Broncho-obstructive syndrome in asthma",
    "Тромбоэмболия лёгочной артерии (ТЭЛА)": "Pulmonary embolism",
    "Спонтанный пневмоторакс (обструктивный шок)": "Spontaneous pneumothorax (obstructive shock)",
    "Гипогликемия": "Hypoglycaemia",
    "Гипергликемия": "Hyperglycaemia",
    "Оценить сознание: осторожно встряхнуть за плечи, громко спросить: «Вам нужна помощь?»":
      "Check consciousness: gently shake the shoulders and ask loudly “Do you need help?”",
    "Надеть перчатки и предложить надеть их помощнику": "Put on gloves and ask the assistant to put them on",
    "Комментировать действия вслух, давать точные полные указания помощнику (работа в команде)":
      "Comment on actions aloud and give the assistant precise, complete instructions (teamwork)",
    "A — проходимость дыхательных путей": "A — airway patency",
    "Осмотреть полость рта на наличие инородных тел, жидкостей":
      "Inspect the oral cavity for foreign bodies and fluids",
    "B — дыхание": "B — breathing",
    "Обеспечить пульсоксиметрию": "Apply pulse oximetry",
    "Обеспечить кислородотерапию при показаниях (сценарии 1–3, 5–7).":
      "Provide oxygen therapy when indicated (scenarios 1–3, 5–7).",
    "проводить при отсутствии показаний (4, 8, 9)": "do not give it without indications (4, 8, 9)",
    "Оценить ЧДД в течение не менее 10 секунд": "Assess respiratory rate for at least 10 seconds",
    "Сравнительная перкуссия и аускультация лёгких": "Comparative percussion and auscultation of the lungs",
    "Осмотр трахеи, вен шеи": "Inspect the trachea and neck veins",
    "C — кровообращение": "C — circulation",
    "Пальпация пульса на лучевых/сонных артериях (оценка симметричности, дефицита пульса), не менее 10 секунд":
      "Palpate the radial/carotid pulse (check symmetry and pulse deficit) for at least 10 seconds",
    "Измерить АД": "Measure blood pressure",
    "Аускультация сердца": "Auscultate the heart",
    "Оценка симптома «белого пятна» (>5 секунд), цвет кожных покровов":
      "Check the “white spot” sign (>5 seconds) and skin colour",
    "Регистрация ЭКГ в 12 отведениях, интерпретация": "Record a 12-lead ECG and interpret it",
    "Убедиться в наличии венозного доступа, обеспечить забор анализов":
      "Confirm venous access and take blood samples",
    "D — неврологический статус": "D — neurological status",
    "Оценка фотореакции зрачков": "Check pupil light reaction",
    "Оценка мышечного тонуса верхних/нижних конечностей": "Assess muscle tone of the arms and legs",
    "Определение уровня глюкозы крови глюкометром с интерпретацией":
      "Measure blood glucose with a glucometer and interpret the result",
    "E — осмотр и дополнительные меры": "E — examination and additional measures",
    "Полная оценка состояния: пальпация живота, ректальное исследование по показаниям":
      "Full assessment: abdominal palpation, rectal examination when indicated",
    "Установить диагноз, сообщить о нём при вызове СМП/бригады ОРИТ":
      "Make the diagnosis and report it when calling the ambulance / ICU team",
    "Назначить/обеспечить лечение по показаниям (препарат, доза, путь введения)":
      "Prescribe/provide treatment when indicated (drug, dose, route)",
    "Соблюдать последовательность ABCDE, при необходимости повторный ABCDE-осмотр":
      "Follow the ABCDE sequence, repeat the ABCDE assessment if needed",
    "незамедлительно подтвердить ОК по отсутствию сознания и дыхания (в течение не менее 10 секунд)":
      "confirm circulatory arrest immediately by the absence of consciousness and breathing (for at least 10 seconds)",
    "дать команду или самостоятельно начать компрессии грудной клетки. Начать в течение 20 секунд после сообщения о прекращении экскурсий грудной клетки":
      "give the order or start chest compressions yourself. Start within 20 seconds of the report that chest excursions have stopped",
    "незамедлительно включить АНД, правильно наклеить электроды, не прерывая КГК. Не прикасаться к пациенту при анализе ритма и при разряде. Нажать «Разряд» по команде АНД":
      "switch the AED on immediately, apply the pads correctly without interrupting compressions. Do not touch the patient during rhythm analysis or the shock. Press “Shock” when the AED prompts",
    "по команде АНД продолжить/возобновить КГК и ИВЛ соотношением 30:2 (или дать команду помощнику). Не оценивать жизнедеятельность сразу после дефибрилляции":
      "on the AED prompt continue/resume compressions and ventilation 30:2 (or order the assistant to). Do not check vital signs right after defibrillation",
    "подключить кислород к дыхательному мешку при необходимости": "connect oxygen to the bag if needed",
    "при повторной команде АНД прекратить СЛР для анализа ритма, не прикасаться к пациенту во время анализа, возобновить СЛР по команде при показаниях":
      "at the repeated AED prompt stop CPR for rhythm analysis, do not touch the patient during analysis, and resume CPR on prompt when indicated",
    "проводить реанимационные мероприятия до приезда СМП/бригады ОРИТ (озвучить)":
      "continue resuscitation until the ambulance / ICU team arrives (say it aloud)",
    "Давать чёткие, полные указания по каждому действию": "Give clear, complete instructions for each action",
    "Контролировать выполнение, при необходимости корректировать":
      "Check that tasks are done and correct them if needed",
    "Помощник надевает перчатки только по просьбе": "The assistant puts on gloves only when asked",
    "Помощник выполняет поручения, при недостатке объяснений уточняет: «Как это надо делать?»":
      "The assistant follows instructions and asks “How should this be done?” if the explanation is unclear",
    "После выполненного действия помощник должен вслух сообщить о его выполнении или о результате измерения":
      "After completing a task the assistant must report it aloud, including measurement results",
    "При наложении электродов ЭКГ/АНД до или во время ОК — использовать бумажную версию ЭКГ соответствующего этапа/сценария":
      "If ECG/AED pads are applied before or during circulatory arrest, use the paper ECG of the relevant stage/scenario",
    "Оценка в чек-листе — «Да/Нет». Ключевые позиции: оценка сознания и дыхания, работа по ABCDE, кислородотерапия по показаниям/противопоказаниям, ЭКГ/интерпретация, венозный доступ/забор анализов, при ОК — своевременное начало КГК, работа с АНД, правильное соотношение КГК:ИВЛ 30:2, непрерывность СЛР, работа в команде.":
      "The checklist is scored Yes/No. Key items: checking consciousness and breathing, working through ABCDE, oxygen therapy by indication/contraindication, ECG and interpretation, venous access and blood sampling, and in cardiac arrest — timely start of compressions, AED use, the correct 30:2 ratio, continuity of CPR and teamwork.",

    "Режим обучения — с разбором ответов": "Training mode — with answer review",
    "Режим тестирования — без подсказок": "Examination mode — no hints",
    "максимум": "maximum",
    "итоговый балл": "final score",
    "Вопросы": "Questions",
    "Начислено:": "Awarded:",

    "Начать обучение": "Start training",
    "Начать зачёт": "Start the exam",
    "К разделам": "Back to sections",
    "Все разделы": "All sections",
    "Ваш ответ словами, например «тридцать на два»": "Type your answer, e.g. “thirty to two”",
    "Ответить": "Answer",
    "Ваш ответ:": "Your answer:",
    "Результат сохранён": "Result saved",
    "Пройти ещё раз": "Try again",
    "Слушаю… скажите ответ": "Listening… say your answer",
    "Голосовой ответ работает только по https — на этом адресе он недоступен. Введите ответ текстом.":
      "Voice answers require https and are unavailable at this address. Type your answer instead.",
    "В этом браузере голосовой ответ недоступен — работает в Chrome и Edge. Введите ответ текстом.":
      "Voice answers are not available in this browser (Chrome and Edge only). Type your answer instead.",
    "варианты и вердикт сразу после ответа": "options and a verdict right after the answer",
    "вариантов нет — ответ вводите или проговариваете сами": "no options — type or say the answer yourself",
    "обучение": "training",
    "зачёт": "exam",
    "Вопрос ": "Question ",

    "Короткие фрагменты реального прохождения станции «Экстренная медицинская помощь». Выберите раздел — вопросы каждый раз новые и идут в случайном порядке.":
      "Short clips from a real run of the Emergency Medical Care station. Pick a section — questions are new and shuffled every time.",
    "Заход": "Run",

    "по теме: ": "on topic: ",
    "по теме:": "on topic:",
    "из": "of",
    "в заходе": "per run",
    "Открыть снова": "Open again",
    "Голосовой ответ: нажмите кнопку и говорите — распознаёт браузер. Если не сработает, введите ответ текстом.":
      "Voice answer: press the button and speak — recognised by the browser. If it fails, type your answer.",
    "Голосовой ответ сейчас недоступен — введите ответ текстом.":
      "Voice answer is not available right now — please type your answer.",
    "Голосовой ответ недоступен в этом браузере — введите ответ текстом.":
      "Voice answer is not available in this browser — please type your answer.",

    "вариантов нет — отвечаете текстом или голосом": "no options — answer by typing or speaking",
    "вопрос": "question",
    "вопроса": "questions",
    "вопросов": "questions",
    "Готовлю микрофон…": "Preparing the microphone…",
    "Слушаю… говорите ответ": "Listening… say your answer",
    "Распознаю…": "Recognising…",
    "Запись пустая — говорите ближе к микрофону.": "The recording is empty — speak closer to the microphone.",
    "Запись с микрофона не поддерживается этим браузером.": "Recording is not supported by this browser.",
    "Не понял ответ — сформулируйте иначе или скажите короче. Ответ не засчитан.":
      "Did not understand — phrase it differently or say it more briefly. The answer was not counted.",
    "Не понял ответ — попробуйте ещё раз.": "Did not understand — try again.",
    "Сказанное не совпало с ответом — попробуйте иначе.": "What you said did not match an answer — try another wording.",
    "Введите ответ или скажите его голосом.": "Type the answer or say it aloud.",
    "Неверно — правильный ответ:": "Incorrect — correct answer:",
    "Режим «Обучение»: варианты ответа и вердикт сразу.":
      "Training mode: answer options and an immediate verdict.",
    "Режим «Зачёт»: вариантов не будет — отвечайте текстом или голосом.":
      "Exam mode: no options — answer by typing or speaking.",
    "Голосовой ответ: нажмите кнопку и говорите — запись распознаётся на нашем сервере и никуда не сохраняется.":
      "Voice answer: press the button and speak — the recording is recognised on our server and is not stored.",
    "Голосовой ответ: распознаёт браузер (Chrome, Edge). Если не работает — включите распознавание на сервере.":
      "Voice answer is recognised by the browser (Chrome, Edge). If it fails, enable server recognition.",
    "Браузер не может распознать речь — включите распознавание на сервере (VOICE_ENABLED=1) или введите ответ текстом.":
      "The browser cannot recognise speech — enable server recognition (VOICE_ENABLED=1) or type your answer.",
    "Голосовой ответ в этом браузере недоступен. Введите ответ текстом.":
      "Voice answers are not available in this browser. Type your answer.",

    // фразы с числами
    __patterns: [
      ["^Фрагмент (\\d+) из (\\d+)$", "Clip $1 of $2"],
      ["^Фрагмент (\\d+)$", "Clip $1"],
      ["^Верных ответов: (\\d+) из (\\d+)$", "Correct answers: $1 of $2"],
      ["^Режим (обучения — с разбором ответов|тестирования — без подсказок) · (.+)$", "Mode: $1 · $2"],
      ["^Вопрос (\\d+) из (\\d+)$", "Question $1 of $2"],
      ["^(\\d+) из (\\d+)$", "$1 of $2"],
      ["^(\\d+) вопросов$", "$1 questions"],
      ["^максимум (\\d+) баллов$", "maximum $1 points"]
    ]
  };
})();
