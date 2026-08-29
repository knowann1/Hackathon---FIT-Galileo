# Financial AI (Gestión y Educación Financiera Personal)

Proyecto Flask para gestión y educación financiera personal, orientado inicialmente a Guatemala (GTQ).

## Qué hace
- Registrar gastos manualmente, por texto (IA), por foto de factura (IA) y por voz.
- Analizar gastos, detectar patrones y generar recomendaciones educativas mediante IA.
- Dashboard con gráficos (Chart.js) y métricas de salud financiera.

## Tecnologías
- Python 3.11+
- Flask, Jinja2
- SQLAlchemy, Flask-Migrate
- PostgreSQL
- OpenAI Python SDK
- Bootstrap 5
- Chart.js
- Gunicorn

## Arquitectura
- app.py: crea la aplicación
- config.py: configuración por entorno
- extensions.py: inicialización de extensiones
- models.py: modelos SQLAlchemy
- routes/: blueprints HTTP
- services/: lógica de IA, parsing y análisis
- templates/: vistas Jinja2
- static/: CSS y JS

## Instalación local
1. Clonar el repo
2. Crear y activar virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Crear `.env` a partir de `.env.example` y rellenar variables (NO pegar claves en el repositorio):

```
OPENAI_API_KEY=
DATABASE_URL=postgresql://user:pass@localhost:5432/financial_ai
SECRET_KEY=change-me
```

4. Crear la base de datos PostgreSQL y ejecutar migraciones:

```bash
export FLASK_APP=app:create_app
flask db init
flask db migrate -m "Initial"
flask db upgrade
```

5. Ejecutar la app en desarrollo:

```bash
flask run
```

## OpenAI
- Proveedor: OpenAI
- La variable de entorno para la API key debe llamarse `OPENAI_API_KEY`.
- Nunca incluir la API key en el código ni en archivos públicos.

## Despliegue en Render
- El archivo `render.yaml` contiene configuración mínima.
- Comando de producción: `gunicorn app:create_app`
- En Render, añade variables de entorno: DATABASE_URL, SECRET_KEY, OPENAI_API_KEY

## Seguridad y privacidad
- Las claves y `.env` deben quedar fuera del control de versiones.
- Los usuarios solo pueden acceder a sus datos.
- Passwords hasheadas con Werkzeug.
- CSRF habilitado mediante Flask-WTF.

## Notas
- Los servicios que integran OpenAI están contenidos en `services/`.
- Las llamadas al modelo multimodal y de audio dependen de la versión del SDK; revisar la documentación oficial si hay cambios.

## Internacionalización (i18n)
La aplicación soporta múltiples idiomas mediante catálogos `gettext` (`.po`/`.mo`).

- **Idiomas configurados**: se definen en `config.py` (`Config.LANGUAGES`), actualmente
  `es` (Español), `qu` (K'iche'), `cak` (Kaqchikel) y `qeq` (Q'eqchi').
- **Archivos de traducción**: viven en `translations/<código>/LC_MESSAGES/messages.po`
  (editable a mano) y se compilan a `messages.mo` (usado en tiempo de ejecución).
- **Selector de idioma**: el menú desplegable "Idioma" del navbar (`templates/base.html`)
  se genera automáticamente a partir de `Config.LANGUAGES`, y cambia el idioma mediante
  `?lang=<código>`. La preferencia se guarda en la sesión del usuario, por lo que se
  mantiene en la navegación posterior y en las redirecciones (login, logout, formularios,
  etc.) hasta que el usuario la cambie explícitamente.
- **Por qué se usa `gettext` (stdlib) en vez de solo Flask-Babel**: algunos idiomas del
  selector (p. ej. Kaqchikel `cak` y Q'eqchi' `qeq`) no son identificadores de locale
  reconocidos por Unicode CLDR, por lo que `babel.Locale.parse()` lanzaba
  `UnknownLocaleError` y provocaba un error 500 al seleccionarlos. Para evitarlo,
  `i18n.py` carga los catálogos directamente con el módulo estándar `gettext`
  (que no depende de CLDR) y expone `_()`/`gettext()`/`ngettext()` a las plantillas.
  Flask-Babel se sigue inicializando, pero usando un "locale seguro" únicamente para
  su maquinaria interna, nunca para elegir el catálogo de textos.
- **Manejo de fallback**: si falta el catálogo compilado de un idioma o una clave de
  traducción, se aplica automáticamente un respaldo al idioma por defecto (`es`) y,
  en última instancia, al texto original; nunca se produce un error 500. Se registran
  advertencias (`app.logger.warning` / `logging`) para facilitar el diagnóstico.

### Cómo agregar un nuevo idioma
1. Añade el código de idioma y su nombre visible en `Config.LANGUAGES` (`config.py`).
2. Genera/edita el catálogo `.po` para ese idioma:
   ```bash
   pybabel init -i translations/messages.pot -d translations -l <codigo>
   # o, si ya existe, actualízalo con:
   pybabel update -i translations/messages.pot -d translations -l <codigo>
   ```
3. Traduce las cadenas en `translations/<codigo>/LC_MESSAGES/messages.po`.
4. Compila los catálogos a `.mo` (obligatorio para que se muestren las traducciones):
   ```bash
   pybabel compile -d translations
   ```
5. Si agregas nuevos textos traducibles en plantillas o código Python, extráelos primero:
   ```bash
   pybabel extract -F babel.cfg -o translations/messages.pot .
   ```
   y luego repite los pasos 2-4 para cada idioma.
6. En plantillas Jinja usa `{{ _('Texto en español') }}`; en código Python usa
   `from i18n import translate as _` y `_('Texto en español')` (por ejemplo, en
   mensajes de `flash()`).

## Tests
Ejecutar la suite de pruebas (incluye pruebas de i18n: cambio de idioma, fallback,
persistencia del idioma en redirecciones, etc.):

```bash
pip install -r requirements.txt
pytest
```

---

Este README es una guía inicial. Ajustar configuraciones reales de producción (TLS, variables de entorno, backups y políticas de retención de datos) antes de desplegar.
