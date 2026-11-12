/* Редактор испытания: публикация, добавление и удаление вопросов.
   ID испытания берём из блока edit-config, который печатает шаблон;
   запасные пути — data-test-id на <body> и номер из адреса страницы. */

function readTestId() {
  const node = document.getElementById('edit-config');
  if (node) {
    try {
      const id = Number(JSON.parse(node.textContent).testId);
      if (Number.isFinite(id) && id > 0) return id;
    } catch (e) { /* ниже попробуем другие способы */ }
  }
  const fromBody = Number(document.body.dataset.testId);
  if (Number.isFinite(fromBody) && fromBody > 0) return fromBody;
  const match = window.location.pathname.match(/\/teacher\/tests\/(\d+)/);
  return match ? Number(match[1]) : 0;
}

const TEST_ID = readTestId();

function requireTestId() {
  if (TEST_ID) return true;
  showError('qerr', 'Не удалось определить испытание — обновите страницу.');
  return false;
}

/* ---------- публикация ---------- */
const publishBtn = document.getElementById('publishBtn');
if (publishBtn) {
  publishBtn.addEventListener('click', async () => {
    if (!requireTestId()) return;
    const publish = publishBtn.dataset.published !== 'true';
    try {
      await apiFetch('/api/tests/' + TEST_ID, {
        method: 'PATCH',
        body: JSON.stringify({ is_published: publish }),
      });
      reloadPage();
    } catch (error) {
      alert(error.message);
    }
  });
}

/* ---------- форма вопроса ---------- */
const kindSelect = document.getElementById('qkind');
if (kindSelect) {
  kindSelect.addEventListener('change', (event) => {
    const kind = event.target.value;
    const isChoice = kind === 'single' || kind === 'multiple';
    document.getElementById('optionsField').classList.toggle('hidden', !isChoice);
    document.getElementById('correctField').classList.toggle('hidden', kind === 'text_manual');
  });
}

function lines(elementId) {
  return document.getElementById(elementId).value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

async function addQuestion() {
  hideError('qerr');
  if (!requireTestId()) return;

  const kind = document.getElementById('qkind').value;
  const text = document.getElementById('qtext').value.trim();
  if (!text) {
    showError('qerr', 'Введите текст вопроса');
    return;
  }

  const options = (kind === 'single' || kind === 'multiple') ? lines('qoptions') : [];
  if ((kind === 'single' || kind === 'multiple') && options.length < 2) {
    showError('qerr', 'Нужно минимум два варианта ответа (каждый — с новой строки)');
    return;
  }
  const correctLines = lines('qcorrect');
  let correct = null;
  if (kind === 'single') correct = correctLines[0] || null;
  else if (kind === 'multiple') correct = correctLines;
  else if (kind === 'text') correct = correctLines;

  if ((kind === 'single' || kind === 'multiple') && !correctLines.length) {
    showError('qerr', 'Укажите правильный вариант ответа');
    return;
  }
  if (kind === 'single' && correctLines.length > 1) {
    showError('qerr', 'У вопроса с одним ответом может быть только один правильный вариант');
    return;
  }

  try {
    await apiFetch(`/api/tests/${TEST_ID}/questions`, {
      method: 'POST',
      body: JSON.stringify({
        text,
        kind,
        options,
        correct,
        points: parseFloat(document.getElementById('qpoints').value || '1'),
        hint: document.getElementById('qhint').value.trim() || null,
      }),
    });
    reloadPage();
  } catch (error) {
    showError('qerr', error.message);
  }
}

async function deleteQuestion(questionId) {
  if (!requireTestId()) return;
  if (!confirm('Удалить вопрос?')) return;
  try {
    await apiFetch('/api/questions/' + questionId, { method: 'DELETE' });
    reloadPage();
  } catch (error) {
    alert(error.message);
  }
}
