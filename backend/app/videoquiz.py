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
)

TOTAL = len(QUESTIONS)

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
