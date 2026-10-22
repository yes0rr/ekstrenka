/* Редактор испытания: публикация, добавление и удаление вопросов.
   ID испытания приходит из data-атрибута на <body>: data-test-id */

const TEST_ID = Number(document.body.dataset.testId);

/* ---------- публикация ---------- */
const publishBtn = document.getElementById('publishBtn');
if (publishBtn) {
  publishBtn.addEventListener('click', async () => {
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

  const kind = document.getElementById('qkind').value;
  const text = document.getElementById('qtext').value.trim();
  if (!text) {
    showError('qerr', 'Введите текст вопроса');
    return;
  }

  const options = (kind === 'single' || kind === 'multiple') ? lines('qoptions') : [];
  const correctLines = lines('qcorrect');
  let correct = null;
  if (kind === 'single') correct = correctLines[0] || null;
  else if (kind === 'multiple') correct = correctLines;
  else if (kind === 'text') correct = correctLines;

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
  if (!confirm('Удалить вопрос?')) return;
  try {
    await apiFetch('/api/questions/' + questionId, { method: 'DELETE' });
    reloadPage();
  } catch (error) {
    alert(error.message);
  }
}
