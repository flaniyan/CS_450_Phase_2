# Frontend

Rendered with Jinja templates and served by FastAPI on the same port as the API.

## Routes

- `/` -> `frontend/templates/home.html`
- `/directory` -> `frontend/templates/directory.html`
- `/rate` -> `frontend/templates/rate.html`
- `/upload` -> `frontend/templates/upload.html`
- `/admin` -> `frontend/templates/admin.html`

## Static assets

- Served at `/static/*` from `frontend/static/`.
- Use `{{ request.url_for('static', path='styles.css') }}` in templates.

## Local Run

```powershell
. .venv/Scripts/Activate.ps1
python -m uvicorn src.index:app --host 0.0.0.0 --port 8000 --reload
```
