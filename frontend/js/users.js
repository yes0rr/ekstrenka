/* Пользователи: смена роли и блокировка */

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
