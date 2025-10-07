# NPM Registry Frontend (Flask)

Python Flask implementation of the ACME Trustworthy Registry UI.

## Quick Start

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-frontend.txt

set FLASK_APP=app
set FLASK_ENV=development
flask run --port 3000
```

App will be available at http://localhost:3000

## Structure

```
frontend_py/
  app.py
  api.py
  templates/
    base.html
    home.html
    directory.html
    upload.html
    rate.html
    admin.html
  static/
    styles.css
  requirements-frontend.txt
```


