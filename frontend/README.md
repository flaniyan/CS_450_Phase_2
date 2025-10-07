# Frontend (Jinja Templates served by FastAPI)

The UI is rendered via Jinja templates and static assets, served by the FastAPI app on the same port as the API.

## Run

```powershell
cd ".."  # repository root
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
python -m uvicorn src.index:app --host 0.0.0.0 --port 3000 --reload
```

Open:
- Home: `http://localhost:3000/`
- Directory: `http://localhost:3000/directory`
- Rate: `http://localhost:3000/rate`
- Upload: `http://localhost:3000/upload`
- Admin: `http://localhost:3000/admin`

## Structure

```
frontend/
  templates/
    base.html
    home.html
    directory.html
    rate.html
    upload.html
    admin.html
  static/
    styles.css
```

Templates are standard Jinja; use `request.url_for('static', path='...')` for asset URLs.

