/* Общий помощник для запросов к API.
   Подключается на страницах, которые ходят в /api/*. */

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
  });

  let data = {};
  try {
    data = await response.json();
  } catch (e) {
    data = {};
  }

  if (!response.ok) {
    const error = new Error(data.detail || ('Ошибка ' + response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

/* Перезагрузить страницу после успешного действия */
function reloadPage() {
  window.location.reload();
}

/* Показать ошибку в блоке с id (alert) или через alert() */
function showError(elementId, message) {
  if (!elementId) {
    alert(message);
    return;
  }
  const box = document.getElementById(elementId);
  if (!box) {
    alert(message);
    return;
  }
  box.textContent = message;
  box.classList.remove('hidden');
}

function hideError(elementId) {
  const box = document.getElementById(elementId);
  if (box) box.classList.add('hidden');
}
