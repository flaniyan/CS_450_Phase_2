import os
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from dotenv import load_dotenv
from api import api_client

load_dotenv()

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/directory")
    def directory():
        q = request.args.get("q", "")
        if q:
            packages = api_client.search(q)
        else:
            packages = api_client.get_all()
        return render_template("directory.html", packages=packages, q=q)

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        if request.method == "POST":
            file = request.files.get("file")
            debloat = request.form.get("debloat") == "on"
            if not file or not file.filename.endswith(".zip"):
                flash("Please select a .zip file", "warning")
            else:
                ok, msg = api_client.upload(file, debloat)
                flash(msg, "success" if ok else "error")
                if ok:
                    return redirect(url_for("upload"))
        return render_template("upload.html")

    @app.post("/admin/reset")
    def reset():
        ok, msg = api_client.reset()
        flash(msg, "success" if ok else "error")
        return redirect(url_for("admin"))

    @app.get("/admin")
    def admin():
        return render_template("admin.html")

    @app.get("/rate")
    def rate():
        name = request.args.get("name")
        rating = None
        if name:
            rating = api_client.rate(name)
        return render_template("rate.html", name=name or "", rating=rating)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=3000, debug=True)


