/* Результаты: ручной ввод балла преподавателем.
   Форма вызывает saveManual(event, attemptId) */

async function saveManual(event, attemptId) {
  event.preventDefault();
  const form = event.target;
  const score = parseFloat(form.score.value);

  if (Number.isNaN(score)) {
    alert('Введите балл');
    return false;
  }

  try {
    await apiFetch(`/api/attempts/${attemptId}/manual-result`, {
      method: 'POST',
      body: JSON.stringify({
        manual_score: score,
        teacher_comment: form.comment.value || null,
      }),
    });
    reloadPage();
  } catch (error) {
    alert(error.message);
  }
  return false;
}
