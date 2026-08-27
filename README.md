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

---

Este README es una guía inicial. Ajustar configuraciones reales de producción (TLS, variables de entorno, backups y políticas de retención de datos) antes de desplegar.
