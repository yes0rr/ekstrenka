/* Страница «Новое испытание»: отправка формы в /api/tests */

document.getElementById('testForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  hideError('err');

  const body = {
    title: document.getElementById('title').value.trim(),
    description: document.getElementById('description').value.trim() || null,
    mode: document.getElementById('mode').value,
    subject_type: document.getElementById('subject_type').value,
    duration_min: parseInt(document.getElementById('duration_min').value || '15', 10),
    criteria: document.getElementById('criteria').value.trim() || null,
    use_camera: document.getElementById('use_camera').checked,
    use_mic: document.getElementById('use_mic').checked,
  };

  try {
    const test = await apiFetch('/api/tests', { method: 'POST', body: JSON.stringify(body) });
    window.location.href = '/teacher/tests/' + test.id;
  } catch (error) {
    showError('err', error.message);
  }
});
