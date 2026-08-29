// Language system for NexoAI - Multiidioma (Español, K'iche', Q'eqchi', Kaqchikel)

let currentLanguage = localStorage.getItem('nexoai_language') || 'es';
let translations = {};

// Load translations
async function loadTranslations() {
  try {
    const response = await fetch('/static/translations.json');
    translations = await response.json();
    applyLanguage(currentLanguage);
  } catch (error) {
    console.error('Error loading translations:', error);
  }
}

// Apply language to page
function applyLanguage(lang) {
  currentLanguage = lang;
  localStorage.setItem('nexoai_language', lang);

  const langData = translations[lang];
  if (!langData) return;

  // Get all elements with data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(element => {
    const key = element.getAttribute('data-i18n');
    if (langData[key]) {
      element.textContent = langData[key];
    }
  });

  // Get all elements with data-i18n-html attribute (for HTML content)
  document.querySelectorAll('[data-i18n-html]').forEach(element => {
    const key = element.getAttribute('data-i18n-html');
    if (langData[key]) {
      element.innerHTML = langData[key];
    }
  });

  // Set HTML lang attribute
  document.documentElement.lang = lang;

  // Update active button in language selector
  updateLanguageButtonState();
}

// Update language button state
function updateLanguageButtonState() {
  const buttons = document.querySelectorAll('.lang-btn');
  buttons.forEach(btn => {
    const btnLang = btn.getAttribute('data-lang');
    if (btnLang === currentLanguage) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}

// Create language selector
function createLanguageSelector() {
  const nav = document.querySelector('nav .nav-inner');
  if (!nav) return;

  const langContainer = document.createElement('div');
  langContainer.className = 'lang-selector';
  langContainer.innerHTML = `
    <button class="lang-btn" data-lang="es">Español</button>
    <button class="lang-btn" data-lang="kiche">K'iche'</button>
    <button class="lang-btn" data-lang="qeqchi">Q'eqchi'</button>
    <button class="lang-btn" data-lang="kaqchikel">Kaqchikel</button>
  `;

  // Add event listeners
  langContainer.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      applyLanguage(btn.getAttribute('data-lang'));
    });
  });

  nav.appendChild(langContainer);
  updateLanguageButtonState();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadTranslations().then(() => {
    createLanguageSelector();
  });
});
