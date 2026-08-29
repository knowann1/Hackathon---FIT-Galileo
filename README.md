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

## Internacionalización (i18n) / Idiomas
La aplicación soporta varios idiomas seleccionables desde el menú "Idioma" del navbar (visible en todas las páginas, incluido el dashboard).

- Los idiomas disponibles se configuran en `config.py` (`Config.LANGUAGES`) y el idioma por defecto en `Config.BABEL_DEFAULT_LOCALE` (`es`).
- Los catálogos de traducción viven en `translations/<código_idioma>/LC_MESSAGES/messages.po` (fuente editable) y `messages.mo` (compilado, usado en producción). `translations/messages.pot` es la plantilla con todas las claves.
- Las cadenas de texto en las plantillas usan `{{ _('Texto en español') }}`; en Python se usa `i18n.gettext('Texto en español')` (ver `routes/expenses.py`).
- La resolución del idioma actual y la traducción de mensajes las gestiona `i18n.py`, que **nunca lanza una excepción**: si el idioma solicitado no es válido/soportado, o falta una clave de traducción, se hace *fallback* seguro al idioma por defecto o al texto original, evitando un `Internal Server Error`.
  - Esto es necesario porque algunos idiomas del selector (por ejemplo Kaqchikel `cak` y Q'eqchi' `qeq`) no forman parte de los datos CLDR que usa Babel para `Locale.parse`, y provocarían un error 500 si se dejaran pasar directamente a Flask-Babel.
- La preferencia de idioma se guarda en la sesión (`session['lang']`) y, si el usuario está autenticado, también en `user.language`, por lo que se mantiene al navegar entre páginas sin necesidad de repetir `?lang=` en cada URL.

### Añadir un nuevo idioma
1. Agregar el código y nombre del idioma en `Config.LANGUAGES` (`config.py`).
2. Crear la carpeta `translations/<código>/LC_MESSAGES/` y un archivo `messages.po` con todas las claves de `translations/messages.pot` traducidas (puedes copiar un `.po` existente como base).
3. Compilar el catálogo a binario (necesario para producción):
   ```bash
   pybabel compile -d translations
   ```
4. Añadir el enlace correspondiente en el selector de idioma de `templates/base.html` (`?lang=<código>`).
5. Si agregas nuevas cadenas a las plantillas, actualiza la plantilla `.pot` y los `.po` existentes:
   ```bash
   pybabel extract -F babel.cfg -o translations/messages.pot .
   pybabel update -i translations/messages.pot -d translations
   ```

## Pruebas
- Pruebas automatizadas de i18n en `tests/test_i18n.py` (usa `unittest`, sin dependencias adicionales). Ejecutar con:
  ```bash
  python -m unittest discover -s tests
  ```

## Notas
- Los servicios que integran OpenAI están contenidos en `services/`.
- Las llamadas al modelo multimodal y de audio dependen de la versión del SDK; revisar la documentación oficial si hay cambios.

---

Este README es una guía inicial. Ajustar configuraciones reales de producción (TLS, variables de entorno, backups y políticas de retención de datos) antes de desplegar.
