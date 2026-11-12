"""Банк вопросов видеотеста: проверка знания алгоритма станции ЭМП по фрагментам записи.

Каждый вопрос — короткий фрагмент реального прохождения станции (см. frontend/media/quiz)
и один вопрос с четырьмя вариантами. Правильный ответ, пояснение и пункт паспорта
хранятся только на сервере: в браузер они уходят лишь после проверки ответа.

Тексты двуязычные (RU/EN): язык выбирается параметром lang, по умолчанию русский.
У каждого варианта есть набор слов-подсказок для голосового ответа (см. app/voice.py):
фраза «двадцать на два» или «да, тридцать на два» должна находить нужный вариант.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LANGS = ("ru", "en")


@dataclass(frozen=True)
class VideoQuestion:
    id: int
    clip: str                          # имя файла в frontend/media/quiz без расширения
    title: dict[str, str]              # что видно на фрагменте
    question: dict[str, str]
    options: dict[str, tuple[str, ...]]
    correct: int                       # индекс верного варианта
    explain: dict[str, str]
    checklist: str = field(default="")  # пункт оценочного листа станции
    triggers: dict[str, tuple[tuple[str, ...], ...]] = field(default_factory=dict)

    def public(self, lang: str = "ru") -> dict:
        """Версия для браузера: только то, что можно показать до ответа."""
        lang = lang if lang in LANGS else "ru"
        return {
            "id": self.id,
            "clip": self.clip,
            "title": self.title[lang],
            "question": self.question[lang],
            "options": list(self.options[lang]),
        }

    def voice_options(self, lang: str = "ru") -> tuple[tuple[str, ...], ...]:
        lang = lang if lang in LANGS else "ru"
        return self.triggers.get(lang, ())


QUESTIONS: tuple[VideoQuestion, ...] = (
    VideoQuestion(
        id=1,
        clip="01_pulseox",
        title={
            "ru": "Врач работает с кистью пациента",
            "en": "The doctor works with the patient's hand",
        },
        question={
            "ru": "Что делает врач на этом фрагменте?",
            "en": "What is the doctor doing in this clip?",
        },
        options={
            "ru": (
                "Измеряет артериальное давление",
                "Обеспечивает пульсоксиметрию для оценки сатурации",
                "Регистрирует ЭКГ в 12 отведениях",
                "Оценивает симптом «белого пятна»",
            ),
            "en": (
                "Measures blood pressure",
                "Applies pulse oximetry to assess saturation",
                "Records a 12-lead ECG",
                "Checks the capillary refill (white spot) sign",
            ),
        },
        correct=1,
        explain={
            "ru": "Датчик на палец — это пульсоксиметрия. По паспорту станции она входит "
                  "в оценку дыхания (B): сначала сатурация, затем частота дыхания за 10 секунд.",
            "en": "A finger probe means pulse oximetry. In the station passport it belongs to "
                  "the breathing step (B): saturation first, then respiratory rate for 10 seconds.",
        },
        checklist="п. 5",
        triggers={
            "ru": (
                ("давление", "тонометр", "тонометром", "ад"),
                ("пульсоксиметр", "пульсоксиметрия", "сатурация", "датчик", "палец", "оксигенация"),
                ("экг", "кардиограмм", "электрод", "12 отведен"),
                ("белое пятно", "белого пятна", "симптом белого"),
            ),
            "en": (
                ("blood pressure", "tonometer", "pressure cuff"),
                ("pulse oximetry", "oximeter", "saturation", "finger", "spo2"),
                ("ecg", "electrocardiogram", "electrodes", "12 lead"),
                ("white spot", "capillary refill", "refill"),
            ),
        },
    ),
    VideoQuestion(
        id=2,
        clip="02_ekg",
        title={
            "ru": "Врач с помощницей накладывают электроды, на мониторе ЭКГ",
            "en": "The doctor and the assistant apply electrodes, ECG on the monitor",
        },
        question={
            "ru": "Какое действие сердечно-сосудистого этапа выполняется?",
            "en": "Which step of the circulation stage is being performed?",
        },
        options={
            "ru": (
                "Регистрация ЭКГ в 12 отведениях с последующей интерпретацией",
                "Непрямой массаж сердца",
                "Пункция периферической вены",
                "Дефибрилляция",
            ),
            "en": (
                "Recording a 12-lead ECG followed by interpretation",
                "Chest compressions",
                "Peripheral venous cannulation",
                "Defibrillation",
            ),
        },
        correct=0,
        explain={
            "ru": "Наложение электродов и запись — это ЭКГ в 12 отведениях. Мало снять плёнку: "
                  "по чек-листу нужно ещё и правильно её истолковать (ритм, ишемия, признаки ТЭЛА).",
            "en": "Electrodes and a trace mean a 12-lead ECG. Recording alone is not enough: the "
                  "checklist requires correct interpretation (rhythm, ischaemia, signs of pulmonary embolism).",
        },
        checklist="п. 18–19",
        triggers={
            "ru": (
                ("экг", "кардиограмм", "12 отведен", "электрод", "запись экг", "снять экг"),
                ("массаж", "компресси", "кгк", "непрямой"),
                ("вена", "вены", "пункци", "катетер", "венозный доступ"),
                ("дефибрилл", "разряд", "анд"),
            ),
            "en": (
                ("ecg", "electrocardiogram", "12 lead", "electrodes", "trace"),
                ("compressions", "massage", "cpr"),
                ("venous", "cannulation", "vein", "catheter", "line"),
                ("defibrillation", "shock", "aed"),
            ),
        },
    ),
    VideoQuestion(
        id=3,
        clip="03_call_smp",
        title={
            "ru": "Врач говорит по телефону, помощница продолжает работу",
            "en": "The doctor is on the phone, the assistant keeps working",
        },
        question={
            "ru": "Что обязательно должно прозвучать в вызове скорой помощи?",
            "en": "What must the emergency call include?",
        },
        options={
            "ru": (
                "Только адрес и фамилия пострадавшего",
                "Адрес, число пострадавших, пол и возраст, предполагаемый диагноз, "
                "объём оказанной помощи и подтверждение, что вызов принят",
                "Только предполагаемый диагноз",
                "Фамилия врача и номер бригады",
            ),
            "en": (
                "Only the address and the patient's surname",
                "Address, number of patients, sex and age, provisional diagnosis, care already "
                "provided and confirmation that the call was accepted",
                "Only the provisional diagnosis",
                "The doctor's name and the team number",
            ),
        },
        correct=1,
        explain={
            "ru": "Вызов считается выполненным, когда переданы пять элементов и врач убедился, "
                  "что вызов принят. Молча положить трубку — типичная потеря балла.",
            "en": "The call counts only when all five elements are passed and the doctor has made "
                  "sure the call was accepted. Hanging up silently is a typical lost point.",
        },
        checklist="п. 28",
        triggers={
            "ru": (
                ("только адрес", "адрес и фамили", "фамилия пострадавшего"),
                ("адрес", "диагноз", "возраст", "пол", "объем помощи", "принят", "количество пострадавших"),
                ("только диагноз", "предполагаемый диагноз"),
                ("фамилия врача", "номер бригады", "бригады"),
            ),
            "en": (
                ("only the address", "address and surname"),
                ("address", "diagnosis", "age", "sex", "care provided", "accepted", "number of patients"),
                ("only the diagnosis", "provisional diagnosis"),
                ("doctor's name", "team number"),
            ),
        },
    ),
    VideoQuestion(
        id=4,
        clip="04_arrest",
        title={
            "ru": "Врач наклоняется к пациенту, затем выпрямляется и даёт команду",
            "en": "The doctor leans over the patient, straightens up and gives an order",
        },
        question={
            "ru": "Что достаточно для констатации остановки кровообращения?",
            "en": "What is enough to confirm circulatory arrest?",
        },
        options={
            "ru": (
                "Отсутствие пульса на лучевой артерии",
                "Отсутствие сознания и отсутствие дыхания (оценка не менее 10 секунд)",
                "Бледность кожи и холодные кисти",
                "Показания тонометра",
            ),
            "en": (
                "No pulse on the radial artery",
                "No consciousness and no breathing (checked for at least 10 seconds)",
                "Pale skin and cold hands",
                "Blood pressure reading",
            ),
        },
        correct=1,
        explain={
            "ru": "Проверяют ровно два признака: сознание и дыхание, не меньше 10 секунд. "
                  "Пульс на сонной артерии и давление для этого решения не нужны — время дороже.",
            "en": "Exactly two signs are checked: consciousness and breathing, for at least "
                  "10 seconds. Carotid pulse and blood pressure are not needed — time matters more.",
        },
        checklist="п. 35, 38",
        triggers={
            "ru": (
                ("лучевой", "лучевая", "пульс на руке"),
                ("сознани", "дыхани", "10 секунд", "десять секунд", "нет дыхания", "не дышит"),
                ("бледность", "холодные кисти", "кожа"),
                ("тонометр", "давление"),
            ),
            "en": (
                ("radial", "pulse on the wrist"),
                ("consciousness", "breathing", "10 seconds", "ten seconds", "not breathing"),
                ("pale", "cold hands", "skin"),
                ("tonometer", "blood pressure"),
            ),
        },
    ),
    VideoQuestion(
        id=5,
        clip="05_aed_on",
        title={
            "ru": "Помощница включает аппарат, врач накладывает электроды",
            "en": "The assistant switches the device on, the doctor applies the pads",
        },
        question={
            "ru": "Когда включают автоматический наружный дефибриллятор?",
            "en": "When is the automated external defibrillator switched on?",
        },
        options={
            "ru": (
                "После первого разряда",
                "Сразу после подтверждения остановки кровообращения — электроды накладывают, "
                "не прекращая компрессий",
                "Только после интубации",
                "После приезда скорой помощи",
            ),
            "en": (
                "After the first shock",
                "Immediately after arrest is confirmed — pads are applied without stopping compressions",
                "Only after intubation",
                "After the ambulance arrives",
            ),
        },
        correct=1,
        explain={
            "ru": "АНД включают как можно раньше, а электроды клеят, не останавливая непрямой массаж. "
                  "Каждая пауза в компрессиях снижает шанс на восстановление кровообращения.",
            "en": "The AED is switched on as early as possible and pads are applied without stopping "
                  "compressions. Every pause reduces the chance of restoring circulation.",
        },
        checklist="п. 40–41",
        triggers={
            "ru": (
                ("после первого разряда", "после разряда"),
                ("сразу", "как можно раньше", "сразу после", "не прекращая", "не останавливая",
                 "во время компрессий", "сразу после подтверждения"),
                ("после интубации", "интубаци"),
                ("после приезда", "скорая приехала", "после скорой"),
            ),
            "en": (
                ("after the first shock", "after the shock"),
                ("immediately", "as early as possible", "right after", "without stopping",
                 "during compressions"),
                ("after intubation", "intubation"),
                ("after the ambulance", "ambulance arrives"),
            ),
        },
    ),
    VideoQuestion(
        id=6,
        clip="06_aed_rhythm",
        title={
            "ru": "Врач поднимает руки и отводит всех от кушетки",
            "en": "The doctor raises his hands and waves everyone away from the couch",
        },
        question={
            "ru": "Зачем врач поднимает руки и просит всех отойти?",
            "en": "Why does the doctor raise his hands and ask everyone to step back?",
        },
        options={
            "ru": (
                "Чтобы освободить место для носилок",
                "Чтобы никто не касался пациента во время оценки ритма и разряда",
                "Чтобы показать помощнице, что она свободна",
                "Чтобы проверить освещение",
            ),
            "en": (
                "To free space for the stretcher",
                "So that nobody touches the patient during rhythm analysis and the shock",
                "To show the assistant she is free",
                "To check the lighting",
            ),
        },
        correct=1,
        explain={
            "ru": "Прикосновение к пациенту искажает запись ритма и опасно в момент разряда. "
                  "Отойти должны все, включая того, кто проводит вентиляцию.",
            "en": "Touching the patient distorts rhythm analysis and is dangerous at the moment of the "
                  "shock. Everyone must step back, including the person ventilating.",
        },
        checklist="п. 42, 44",
        triggers={
            "ru": (
                ("носилк", "место"),
                ("не касаться", "не прикасаться", "никто не трогал", "оценки ритма", "разряда",
                 "отошли", "никто не касался"),
                ("свободна", "помощнице"),
                ("освещение", "свет"),
            ),
            "en": (
                ("stretcher", "space"),
                ("nobody touches", "not touch", "rhythm analysis", "shock", "step back"),
                ("free", "assistant"),
                ("lighting", "light"),
            ),
        },
    ),
    VideoQuestion(
        id=7,
        clip="07_airway",
        title={
            "ru": "Врач вводит воздуховод",
            "en": "The doctor inserts an airway",
        },
        question={
            "ru": "В какой момент алгоритма ставят орофарингеальный воздуховод?",
            "en": "When in the algorithm is an oropharyngeal airway inserted?",
        },
        options={
            "ru": (
                "До первого разряда АНД",
                "Сразу после первого разряда",
                "Только после приезда скорой помощи",
                "Вместо вентиляции мешком",
            ),
            "en": (
                "Before the first AED shock",
                "Right after the first shock",
                "Only after the ambulance arrives",
                "Instead of bag ventilation",
            ),
        },
        correct=1,
        explain={
            "ru": "По алгоритму станции воздуховод ставят после первого разряда, затем переходят "
                  "к вентиляции мешком. Воздуховод не заменяет вентиляцию, а дополняет её.",
            "en": "In the station algorithm the airway goes in after the first shock, then bag "
                  "ventilation follows. The airway supports ventilation rather than replacing it.",
        },
        checklist="п. 47–48",
        triggers={
            "ru": (
                ("до первого разряда", "до разряда", "перед разрядом"),
                ("после первого разряда", "после разряда", "сразу после"),
                ("после приезда", "после скорой"),
                ("вместо", "вместо вентиляции"),
            ),
            "en": (
                ("before the first shock", "before the shock"),
                ("after the first shock", "after the shock", "right after"),
                ("after the ambulance",),
                ("instead", "instead of ventilation"),
            ),
        },
    ),
    VideoQuestion(
        id=8,
        clip="08_vent",
        title={
            "ru": "Врач и помощница работают вдвоём у кушетки",
            "en": "The doctor and the assistant work together at the couch",
        },
        question={
            "ru": "Какое соотношение компрессий грудной клетки и вдохов правильное?",
            "en": "What is the correct compression-to-breath ratio?",
        },
        options={"ru": ("15:2", "30:2", "5:1", "10:2"), "en": ("15:2", "30:2", "5:1", "10:2")},
        correct=1,
        explain={
            "ru": "Для одного спасателя и для двух — 30 компрессий и 2 вдоха. Меняться местами "
                  "нужно каждые две минуты, чтобы не падала глубина компрессий.",
            "en": "For one or two rescuers it is 30 compressions to 2 breaths. Swap roles every two "
                  "minutes so that compression depth does not drop.",
        },
        checklist="п. 47–48",
        triggers={
            "ru": (
                ("15 на 2", "15 к 2", "пятнадцать на два"),
                ("30 на 2", "30 к 2", "тридцать на два", "тридцать к двум"),
                ("5 на 1", "пять на один"),
                ("10 на 2", "десять на два"),
            ),
            "en": (
                ("15 to 2", "15 2", "fifteen to two"),
                ("30 to 2", "30 2", "thirty to two"),
                ("5 to 1", "five to one"),
                ("10 to 2", "ten to two"),
            ),
        },
    ),
    VideoQuestion(
        id=9,
        clip="09_repeat",
        title={
            "ru": "Повторная оценка ритма и команда АНД",
            "en": "Repeated rhythm analysis and the AED prompt",
        },
        question={
            "ru": "Что делает врач по команде АНД после повторной оценки ритма?",
            "en": "What does the doctor do after the repeated rhythm analysis?",
        },
        options={
            "ru": (
                "Снова начинает компрессии и вентиляцию 30:2 и продолжает до приезда скорой",
                "Прекращает реанимацию и ждёт скорую",
                "Проверяет пульс и давление сразу после разряда",
                "Отключает АНД и снимает электроды",
            ),
            "en": (
                "Resumes compressions and ventilation 30:2 and continues until the ambulance arrives",
                "Stops resuscitation and waits for the ambulance",
                "Checks pulse and blood pressure right after the shock",
                "Switches the AED off and removes the pads",
            ),
        },
        correct=0,
        explain={
            "ru": "Реанимацию продолжают без пауз до восстановления кровообращения или приезда СМП. "
                  "Проверять пульс и давление сразу после разряда бессмысленно: сердце ещё не наполнилось.",
            "en": "Resuscitation continues without pauses until circulation returns or the ambulance "
                  "arrives. Checking pulse and pressure right after a shock is pointless: the heart "
                  "has not refilled yet.",
        },
        checklist="п. 49, 51–52",
        triggers={
            "ru": (
                ("продолжает", "возобновляет", "снова начинает", "компрессии", "30 на 2",
                 "до приезда", "реанимацию продолжаем"),
                ("прекращает", "останавливает", "ждет скорую"),
                ("проверяет пульс", "давление сразу", "пульс сразу"),
                ("отключает", "снимает электроды"),
            ),
            "en": (
                ("resumes", "continues", "compressions", "30 to 2", "until the ambulance"),
                ("stops", "waits for the ambulance"),
                ("checks pulse", "blood pressure right after"),
                ("switches off", "removes the pads"),
            ),
        },
    ),
    VideoQuestion(
        id=10,
        clip="02_ekg",
        title={
            "ru": "Плёнка ЭКГ снята, врач смотрит на запись",
            "en": "The ECG is recorded, the doctor looks at the trace",
        },
        question={
            "ru": "Что обязательно сделать сразу после записи ЭКГ?",
            "en": "What must be done right after recording the ECG?",
        },
        options={
            "ru": (
                "Интерпретировать запись: ритм, ишемия, признаки ТЭЛА",
                "Подшить плёнку в карту и продолжить осмотр",
                "Переснять ЭКГ три раза подряд",
                "Ничего, интерпретация не входит в чек-лист",
            ),
            "en": (
                "Interpret the trace: rhythm, ischaemia, signs of pulmonary embolism",
                "File the trace and continue the examination",
                "Record the ECG three times in a row",
                "Nothing — interpretation is not part of the checklist",
            ),
        },
        correct=0,
        explain={
            "ru": "В оценочном листе ЭКГ идёт двумя пунктами: снять и истолковать. "
                  "Запись без интерпретации — половина балла.",
            "en": "The checklist has two items for the ECG: record and interpret. "
                  "A trace without interpretation is half the score.",
        },
        checklist="п. 19",
        triggers={
            "ru": (
                ("интерпрет", "истолков", "оценить запись", "прочитать экг", "ритм", "ишемия", "тэла"),
                ("подшить", "в карту", "продолжить осмотр"),
                ("три раза", "переснять", "повторить запись"),
                ("ничего", "не входит"),
            ),
            "en": (
                ("interpret", "read the ecg", "rhythm", "ischaemia", "pulmonary embolism"),
                ("file", "continue the examination"),
                ("three times", "repeat the recording"),
                ("nothing", "not part"),
            ),
        },
    ),
    VideoQuestion(
        id=11,
        clip="03_call_smp",
        title={
            "ru": "Врач с телефоном у кушетки, помощница рядом",
            "en": "The doctor with the phone at the couch, the assistant nearby",
        },
        question={
            "ru": "Когда сообщают предполагаемый диагноз диспетчеру скорой?",
            "en": "When is the provisional diagnosis reported to the dispatcher?",
        },
        options={
            "ru": (
                "При вызове скорой помощи, вместе с остальными данными",
                "Только когда бригада приедет на место",
                "Только после окончания реанимации",
                "Диагноз диспетчеру не сообщают",
            ),
            "en": (
                "When calling the ambulance, together with the other details",
                "Only when the team arrives",
                "Only after resuscitation is finished",
                "The diagnosis is not reported to the dispatcher",
            ),
        },
        correct=0,
        explain={
            "ru": "Диагноз — один из пяти элементов вызова. Без него бригада не знает, "
                  "что везти и куда госпитализировать.",
            "en": "The diagnosis is one of the five elements of the call. Without it the team "
                  "does not know what to bring and where to take the patient.",
        },
        checklist="п. 28, 39",
        triggers={
            "ru": (
                ("при вызове", "во время вызова", "сразу", "вместе"),
                ("когда приедет", "после приезда", "бригада приедет"),
                ("после реанимации", "после окончания"),
                ("не сообщают", "не передают"),
            ),
            "en": (
                ("when calling", "during the call", "immediately", "together"),
                ("when the team arrives", "after arrival"),
                ("after resuscitation",),
                ("not reported", "do not report"),
            ),
        },
    ),
    VideoQuestion(
        id=12,
        clip="01_pulseox",
        title={
            "ru": "Врач надевает датчик и смотрит на монитор",
            "en": "The doctor applies the probe and looks at the monitor",
        },
        question={
            "ru": "Когда по алгоритму проводят кислородотерапию?",
            "en": "When does the algorithm call for oxygen therapy?",
        },
        options={
            "ru": (
                "По показаниям — при гипоксемии, в сценариях 1–3 и 5–7",
                "Всем пациентам без исключения",
                "Только после первого разряда АНД",
                "Никогда, кислород не входит в станцию",
            ),
            "en": (
                "When indicated — in hypoxaemia, in scenarios 1–3 and 5–7",
                "To every patient without exception",
                "Only after the first AED shock",
                "Never — oxygen is not part of the station",
            ),
        },
        correct=0,
        explain={
            "ru": "Кислород не «на всякий случай»: в сценариях 4, 8 и 9 он не показан, "
                  "и лишний кислород — тоже ошибка. Показание — низкая сатурация.",
            "en": "Oxygen is not given “just in case”: in scenarios 4, 8 and 9 it is not indicated, "
                  "and extra oxygen is also a mistake. The indication is low saturation.",
        },
        checklist="п. 6",
        triggers={
            "ru": (
                ("по показаниям", "при гипоксемии", "при низкой сатурации", "сценариях"),
                ("всем", "без исключения", "всем пациентам"),
                ("после разряда", "после первого разряда"),
                ("никогда", "не входит"),
            ),
            "en": (
                ("when indicated", "hypoxaemia", "low saturation"),
                ("every patient", "without exception"),
                ("after the shock",),
                ("never", "not part"),
            ),
        },
    ),
    VideoQuestion(
        id=13,
        clip="04_arrest",
        title={
            "ru": "Врач выпрямился и подаёт команду помощнице",
            "en": "The doctor straightens up and gives the assistant an order",
        },
        question={
            "ru": "За сколько секунд нужно начать компрессии грудной клетки?",
            "en": "How many seconds are allowed before chest compressions must start?",
        },
        options={
            "ru": (
                "В течение 20 секунд после сообщения о прекращении экскурсий грудной клетки",
                "В течение 2 минут — сначала нужно всё записать",
                "Только после приезда скорой помощи",
                "Сразу после того, как снята ЭКГ в 12 отведениях",
            ),
            "en": (
                "Within 20 seconds of the report that chest excursions have stopped",
                "Within 2 minutes — everything must be documented first",
                "Only after the ambulance arrives",
                "Right after the 12-lead ECG is recorded",
            ),
        },
        correct=0,
        explain={
            "ru": "Двадцать секунд — это максимум по чек-листу. Каждая минута без компрессий "
                  "снижает выживаемость примерно на 10 %.",
            "en": "Twenty seconds is the checklist maximum. Every minute without compressions "
                  "cuts survival by roughly 10 %.",
        },
        checklist="п. 38",
        triggers={
            "ru": (
                ("20 секунд", "двадцать секунд", "в течение 20"),
                ("2 минут", "две минуты", "двух минут"),
                ("после приезда", "после скорой"),
                ("после экг", "после снятия"),
            ),
            "en": (
                ("20 seconds", "twenty seconds", "within 20"),
                ("2 minutes", "two minutes"),
                ("after the ambulance",),
                ("after the ecg",),
            ),
        },
    ),
    VideoQuestion(
        id=14,
        clip="05_aed_on",
        title={
            "ru": "Электроды АНД на грудной клетке пациента",
            "en": "AED pads on the patient's chest",
        },
        question={
            "ru": "Куда наклеивают электроды АНД?",
            "en": "Where are the AED pads applied?",
        },
        options={
            "ru": (
                "На грудную клетку по схеме на самом электроде",
                "На живот и на бедро",
                "На спину и на шею",
                "Куда удобно — на результат это не влияет",
            ),
            "en": (
                "On the chest, following the diagram printed on the pad",
                "On the abdomen and the thigh",
                "On the back and the neck",
                "Anywhere — it does not affect the result",
            ),
        },
        correct=0,
        explain={
            "ru": "Схема нарисована на электроде: правое подключичье и левая подмышечная линия. "
                  "Наклеенные «как получилось» электроды дают неверную оценку ритма.",
            "en": "The diagram is printed on the pad: right infraclavicular and left mid-axillary line. "
                  "Randomly placed pads give a wrong rhythm analysis.",
        },
        checklist="п. 40",
        triggers={
            "ru": (
                ("по схеме", "на грудную", "на груди", "подключич", "подмышечн"),
                ("живот", "бедро"),
                ("спина", "шея", "на спину"),
                ("куда удобно", "не влияет"),
            ),
            "en": (
                ("diagram", "on the chest", "infraclavicular", "axillary"),
                ("abdomen", "thigh"),
                ("back", "neck"),
                ("anywhere", "does not affect"),
            ),
        },
    ),
    VideoQuestion(
        id=15,
        clip="06_aed_rhythm",
        title={
            "ru": "Повторная команда АНД, врач отводит руки",
            "en": "Repeated AED prompt, the doctor pulls his hands away",
        },
        question={
            "ru": "Что делают по повторной команде АНД?",
            "en": "What is done at the repeated AED prompt?",
        },
        options={
            "ru": (
                "Прекращают СЛР для анализа ритма и не прикасаются к пациенту",
                "Продолжают массаж, не обращая внимания на команду",
                "Снимают электроды и выключают аппарат",
                "Начинают вентиляцию мешком чаще обычного",
            ),
            "en": (
                "Stop CPR for rhythm analysis and do not touch the patient",
                "Continue compressions, ignoring the prompt",
                "Remove the pads and switch the device off",
                "Start bag ventilation more often than usual",
            ),
        },
        correct=0,
        explain={
            "ru": "Анализ ритма требует тишины по прикосновениям: иначе аппарат «увидит» помехи. "
                  "После команды СЛР либо возобновляют, либо готовят разряд.",
            "en": "Rhythm analysis needs no touching: otherwise the device sees interference. "
                  "After the prompt you either resume CPR or prepare a shock.",
        },
        checklist="п. 42, 45",
        triggers={
            "ru": (
                ("прекращают", "останавливают слр", "не прикасаются", "для анализа ритма"),
                ("продолжают массаж", "не обращая"),
                ("снимают электроды", "выключают"),
                ("вентиляцию", "мешком чаще"),
            ),
            "en": (
                ("stop cpr", "do not touch", "rhythm analysis"),
                ("continue compressions", "ignoring"),
                ("remove the pads", "switch off"),
                ("ventilation", "more often"),
            ),
        },
    ),
    VideoQuestion(
        id=16,
        clip="07_airway",
        title={
            "ru": "Врач осматривает полость рта перед воздуховодом",
            "en": "The doctor inspects the mouth before inserting the airway",
        },
        question={
            "ru": "Что проверяют перед постановкой воздуховода?",
            "en": "What is checked before inserting an airway?",
        },
        options={
            "ru": (
                "Проходимость дыхательных путей и полость рта на инородные тела",
                "Пульс на сонной артерии",
                "Фотореакцию зрачков",
                "Уровень глюкозы крови",
            ),
            "en": (
                "Airway patency and the mouth for foreign bodies",
                "Carotid pulse",
                "Pupil light reaction",
                "Blood glucose",
            ),
        },
        correct=0,
        explain={
            "ru": "Это пункт A — airway. Сначала убедиться, что путь свободен, и только потом "
                  "ставить воздуховод: иначе его просто вытолкнет или он перекроет вход.",
            "en": "This is step A — airway. Confirm the passage is clear before inserting the airway, "
                  "otherwise it is pushed out or blocks the entrance.",
        },
        checklist="п. 16",
        triggers={
            "ru": (
                ("проходимость", "полость рта", "инородные", "дыхательных путей"),
                ("сонной", "пульс"),
                ("зрачк", "фотореакци"),
                ("глюкоз", "сахар"),
            ),
            "en": (
                ("patency", "mouth", "foreign bodies", "airway"),
                ("carotid", "pulse"),
                ("pupil", "light reaction"),
                ("glucose", "sugar"),
            ),
        },
    ),
    VideoQuestion(
        id=17,
        clip="08_vent",
        title={
            "ru": "Двое спасателей работают у кушетки",
            "en": "Two rescuers working at the couch",
        },
        question={
            "ru": "Как часто спасатели меняются местами при реанимации?",
            "en": "How often should rescuers swap roles during resuscitation?",
        },
        options={
            "ru": (
                "Каждые 2 минуты — иначе падает глубина компрессий",
                "Каждую минуту",
                "Каждые 10 минут",
                "Не меняются до приезда скорой",
            ),
            "en": (
                "Every 2 minutes — otherwise compression depth drops",
                "Every minute",
                "Every 10 minutes",
                "They do not swap until the ambulance arrives",
            ),
        },
        correct=0,
        explain={
            "ru": "Через две минуты непрерывного массажа качество падает даже у опытных. "
                  "Смена занимает 5 секунд, а глубину возвращает.",
            "en": "After two minutes of continuous compressions quality drops even for experienced "
                  "rescuers. A swap takes 5 seconds and restores depth.",
        },
        checklist="п. 47–48",
        triggers={
            "ru": (
                ("2 минуты", "две минуты", "каждые две"),
                ("каждую минуту", "каждую 1"),
                ("10 минут", "десять минут"),
                ("не меняются", "до приезда"),
            ),
            "en": (
                ("2 minutes", "two minutes", "every two"),
                ("every minute",),
                ("10 minutes", "ten minutes"),
                ("do not swap", "until the ambulance"),
            ),
        },
    ),
    VideoQuestion(
        id=18,
        clip="09_repeat",
        title={
            "ru": "Реанимация продолжается, рядом помощница",
            "en": "Resuscitation continues, the assistant is nearby",
        },
        question={
            "ru": "Когда прекращают реанимационные мероприятия?",
            "en": "When is resuscitation stopped?",
        },
        options={
            "ru": (
                "При восстановлении кровообращения или по приезде СМП",
                "После третьего разряда АНД",
                "Ровно через 10 минут от начала",
                "Когда врач устал",
            ),
            "en": (
                "When circulation returns or the ambulance arrives",
                "After the third AED shock",
                "Exactly 10 minutes after the start",
                "When the doctor is tired",
            ),
        },
        correct=0,
        explain={
            "ru": "Реанимацию ведут без пауз до восстановления кровообращения или передачи бригаде. "
                  "Фиксированного «через 10 минут» в алгоритме нет.",
            "en": "Resuscitation continues without pauses until circulation returns or the team takes "
                  "over. There is no fixed “after 10 minutes” in the algorithm.",
        },
        checklist="п. 49",
        triggers={
            "ru": (
                ("восстановлени", "приезде", "передаче", "до приезда скорой"),
                ("третьего разряда", "после третьего"),
                ("10 минут", "десять минут", "ровно через"),
                ("устал", "по желанию"),
            ),
            "en": (
                ("circulation returns", "ambulance arrives", "handover"),
                ("third shock",),
                ("10 minutes", "ten minutes"),
                ("tired",),
            ),
        },
    ),
    VideoQuestion(
        id=19,
        clip="01_pulseox",
        title={
            "ru": "Врач осматривает пациента по шагам",
            "en": "The doctor examines the patient step by step",
        },
        question={
            "ru": "В какой последовательности идёт осмотр по паспорту станции?",
            "en": "In what order does the station passport require the examination?",
        },
        options={
            "ru": (
                "ABCDE: дыхательные пути, дыхание, кровообращение, неврология, осмотр",
                "Сначала анализы и ЭКГ, затем осмотр",
                "CABDE: сразу кровообращение, потом дыхание",
                "В любом удобном порядке",
            ),
            "en": (
                "ABCDE: airway, breathing, circulation, neurological status, examination",
                "Labs and ECG first, then the examination",
                "CABDE: circulation first, then breathing",
                "In any convenient order",
            ),
        },
        correct=0,
        explain={
            "ru": "ABCDE — это и порядок, и страховка: сначала то, что убивает быстрее. "
                  "При остановке кровообращения порядок меняется на КГК и АНД, но не на «как удобно».",
            "en": "ABCDE is both the order and the safety net: the fastest killer first. In cardiac "
                  "arrest the sequence switches to compressions and AED, never to “any order”.",
        },
        checklist="п. 41",
        triggers={
            "ru": (
                ("abcde", "а б ц д е", "дыхательные пути, дыхание", "по порядку abcde"),
                ("сначала анализы", "сначала экг", "анализы и экг"),
                ("cabde", "сразу кровообращение"),
                ("любом порядке", "как удобно"),
            ),
            "en": (
                ("abcde", "airway breathing circulation"),
                ("labs first", "ecg first", "tests first"),
                ("cabde", "circulation first"),
                ("any order", "convenient"),
            ),
        },
    ),
    VideoQuestion(
        id=20,
        clip="04_arrest",
        title={
            "ru": "Врач у кушетки с помощницей, рядом укладка",
            "en": "The doctor at the couch with the assistant, the kit nearby",
        },
        question={
            "ru": "Что входит в шаг D — неврологический статус?",
            "en": "What belongs to step D — neurological status?",
        },
        options={
            "ru": (
                "Фотореакция зрачков, мышечный тонус и глюкоза крови глюкометром",
                "Только измерение артериального давления",
                "Только пальпация живота",
                "Только аускультация лёгких",
            ),
            "en": (
                "Pupil light reaction, muscle tone and blood glucose with a glucometer",
                "Blood pressure measurement only",
                "Abdominal palpation only",
                "Lung auscultation only",
            ),
        },
        correct=0,
        explain={
            "ru": "Шаг D — это зрачки, тонус конечностей и глюкоза с интерпретацией. "
                  "Давление и лёгкие — это шаги C и B, их путают чаще всего.",
            "en": "Step D covers pupils, limb tone and glucose with interpretation. Blood pressure "
                  "and lungs belong to steps C and B — the most common mix-up.",
        },
        checklist="п. 20–22",
        triggers={
            "ru": (
                ("зрачк", "тонус", "глюкоз", "фотореакци"),
                ("давлени", "ад"),
                ("живот", "пальпаци"),
                ("легких", "аускультаци"),
            ),
            "en": (
                ("pupil", "tone", "glucose"),
                ("blood pressure",),
                ("abdomen", "palpation"),
                ("lungs", "auscultation"),
            ),
        },
    ),
)

TOTAL = len(QUESTIONS)

# ----------------------------- разделы видеотеста -----------------------------
# Каждый раздел — мини-подборка по теме станции: картинка (постер фрагмента),
# короткое описание и набор вопросов. В заходе ВСЕГДА RUN_SIZE вопросов (= весь банк):
# если в разделе вопросов меньше, добираем остальные, чтобы заход был одинаковым по длине.
RUN_SIZE = TOTAL


@dataclass(frozen=True)
class Section:
    key: str
    title: dict[str, str]
    description: dict[str, str]
    cover: str                     # имя клипа, из которого берётся постер
    question_ids: tuple[int, ...]

    def public(self, lang: str = "ru") -> dict:
        lang = lang if lang in LANGS else "ru"
        return {
            "key": self.key,
            "title": self.title[lang],
            "description": self.description[lang],
            "cover": self.cover,
            "own": len(self.question_ids),      # сколько вопросов именно по теме раздела
            "run_size": min(RUN_SIZE, TOTAL),   # сколько будет в заходе (добираем из общего банка)
            "total": TOTAL,
        }


SECTIONS: tuple[Section, ...] = (
    Section(
        key="all",
        title={"ru": "Все разделы", "en": "All sections"},
        description={
            "ru": "Все 20 вопросов банка в случайном порядке: осмотр, СЛР, вентиляция, вызов СМП.",
            "en": "All 20 questions in random order: examination, CPR, ventilation, the emergency call.",
        },
        cover="04_arrest",
        question_ids=tuple(q.id for q in QUESTIONS),
    ),
    Section(
        key="exam",
        title={"ru": "Осмотр пациента и ABCDE", "en": "Patient examination and ABCDE"},
        description={
            "ru": "Пульсоксиметрия, ЭКГ в 12 отведениях, кислородотерапия по показаниям, порядок ABCDE.",
            "en": "Pulse oximetry, 12-lead ECG, oxygen therapy by indication, the ABCDE order.",
        },
        cover="01_pulseox",
        question_ids=(1, 2, 10, 12, 19, 20),
    ),
    Section(
        key="cpr",
        title={"ru": "СЛР, АНД и реанимация", "en": "CPR, AED and resuscitation"},
        description={
            "ru": "Констатация остановки, включение АНД, электроды, разряд, когда заканчивать реанимацию.",
            "en": "Confirming arrest, switching the AED on, pads, shock, when to stop resuscitation.",
        },
        cover="05_aed_on",
        question_ids=(4, 5, 6, 13, 14, 15, 18),
    ),
    Section(
        key="airway",
        title={"ru": "Дыхательные пути и вентиляция", "en": "Airway and ventilation"},
        description={
            "ru": "Воздуховод, вентиляция мешком, соотношение 30:2, смена спасателей.",
            "en": "Airway, bag ventilation, the 30:2 ratio, swapping rescuers.",
        },
        cover="07_airway",
        question_ids=(7, 8, 16, 17),
    ),
    Section(
        key="call",
        title={"ru": "Вызов СМП и работа в команде", "en": "Calling the ambulance and teamwork"},
        description={
            "ru": "Пять элементов вызова, передача диагноза, указания помощнику.",
            "en": "The five elements of the call, reporting the diagnosis, instructions to the assistant.",
        },
        cover="03_call_smp",
        question_ids=(3, 11),
    ),
)

SECTION_BY_KEY = {section.key: section for section in SECTIONS}

# порог → вердикт (сверху вниз)
VERDICTS: tuple[tuple[float, str, str], ...] = (
    (90, "excellent", "Алгоритм знаете уверенно"),
    (70, "partial", "Есть пробелы — пересмотрите отмеченные пункты"),
    (50, "weak", "Алгоритм стоит повторить целиком"),
    (0, "bad", "Алгоритм не усвоен — начните с инструкции по ЭМП"),
)

VERDICTS_EN: tuple[tuple[float, str, str], ...] = (
    (90, "excellent", "You know the algorithm confidently"),
    (70, "partial", "Some gaps — review the highlighted items"),
    (50, "weak", "Worth repeating the whole algorithm"),
    (0, "bad", "Algorithm not learnt — start with the emergency care guide"),
)

# куда ведёт совет в вердикте (страница есть на сайте)
GUIDE_URL = "/instruction/emergency-help"
GUIDE_LABEL = {"ru": "инструкции по ЭМП", "en": "the emergency care guide"}


def by_id(question_id: int) -> VideoQuestion | None:
    for question in QUESTIONS:
        if question.id == question_id:
            return question
    return None


def verdict(percent: float, lang: str = "ru") -> tuple[str, str]:
    """Процент → (код вердикта, текст)."""
    table = VERDICTS_EN if lang == "en" else VERDICTS
    for threshold, code, text in table:
        if percent >= threshold:
            return code, text
    return "bad", table[-1][2]


def pick_questions(section_key: str = "all", count: int = RUN_SIZE,
                   rng=None) -> list[VideoQuestion]:
    """Случайная подборка вопросов раздела: каждый заход — новый набор и новый порядок."""
    import random

    rng = rng or random
    section = SECTION_BY_KEY.get(section_key) or SECTION_BY_KEY["all"]
    own = [q for q in (by_id(qid) for qid in section.question_ids) if q is not None]
    rng.shuffle(own)
    picked = own[:count]
    if len(picked) < count:
        # в разделе меньше вопросов, чем нужно на заход — добираем остальными
        rest = [q for q in QUESTIONS if q not in picked]
        rng.shuffle(rest)
        picked += rest[:count - len(picked)]
    return picked


def option_order(question: VideoQuestion, rng=None) -> list[int]:
    """Порядок показа вариантов: перемешиваем, чтобы ответы не запоминались по номеру."""
    import random

    rng = rng or random
    order = list(range(len(question.options["ru"])))
    rng.shuffle(order)
    return order


def check(question: VideoQuestion, answer: int, lang: str = "ru") -> dict:
    """Проверка одного ответа: вердикт, правильный вариант, пояснение, пункт листа."""
    lang = lang if lang in LANGS else "ru"
    return {
        "question_id": question.id,
        "correct": answer == question.correct,
        "correct_index": question.correct,
        "explain": question.explain[lang],
        "checklist": question.checklist,
    }
