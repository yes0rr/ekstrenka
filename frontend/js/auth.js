/* Вход/регистрация: подстановка демо-доступов в один клик. */

const DEMO_ACCOUNTS = {
  teacher: { email: 'teacher@example.com', password: 'teacher123' },
  student: { email: 'student@example.com', password: 'student123' },
};

function fillDemo(role) {
  const account = DEMO_ACCOUNTS[role];
  if (!account) return;

  const emailInput = document.getElementById('email') || document.getElementById('regEmail');
  const passwordInput = document.getElementById('password') || document.getElementById('regPassword');
  if (!emailInput || !passwordInput) return;

  emailInput.value = account.email;
  passwordInput.value = account.password;
  emailInput.classList.add('filled-flash');
  passwordInput.classList.add('filled-flash');
  setTimeout(() => {
    emailInput.classList.remove('filled-flash');
    passwordInput.classList.remove('filled-flash');
  }, 700);

  passwordInput.focus();
}

/* Поддержка ссылок вида /login?demo=teacher — пришли с другой страницы */
document.addEventListener('DOMContentLoaded', () => {
  const role = new URLSearchParams(window.location.search).get('demo');
  if (role) fillDemo(role);
});
