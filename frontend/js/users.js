/* Пользователи: смена роли, блокировка и удаление */

async function patchUser(userId, body) {
  try {
    await apiFetch('/api/users/' + userId, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
    reloadPage();
  } catch (error) {
    alert(error.message);
  }
}

async function deleteUser(button) {
  const userId = button.dataset.userId;
  const fullName = button.dataset.userName || 'пользователя';
  const question = 'Удалить пользователя «' + fullName + '»?\n\n' +
    'Вместе с ним удалятся его испытания, попытки и результаты.\n' +
    'Это действие необратимо.';
  if (!confirm(question)) return;

  button.disabled = true;
  try {
    await apiFetch('/api/users/' + userId, { method: 'DELETE' });
    reloadPage();
  } catch (error) {
    button.disabled = false;
    alert(error.message);
  }
}
