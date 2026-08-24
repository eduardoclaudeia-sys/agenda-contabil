import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
csrf = CSRFProtect()

def normalize_database_url(url: str) -> str:
    if not url:
        return "sqlite:///agenda_local_teste.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this")
app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(os.environ.get("DATABASE_URL", ""))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER", "").lower() == "true"
app.permanent_session_lifetime = 60 * 60 * 8

db.init_app(app)
csrf.init_app(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ---------- Models ----------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    cnpj = db.Column(db.String(30))
    contact_name = db.Column(db.String(120))
    phone = db.Column(db.String(60))
    email = db.Column(db.String(180))
    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(60), nullable=False, default="Tarefa geral")
    task_date = db.Column(db.Date, nullable=False)
    task_time = db.Column(db.Time)
    priority = db.Column(db.String(30), nullable=False, default="Normal")
    status = db.Column(db.String(30), nullable=False, default="Pendente")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class Admission(db.Model):
    __tablename__ = "admissions"
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(180), nullable=False, index=True)
    cpf = db.Column(db.String(30))
    role = db.Column(db.String(120))
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="SET NULL"))
    company = db.relationship("Company", backref=db.backref("admissions", lazy=True))
    admission_date = db.Column(db.Date, nullable=False)
    deadline = db.Column(db.Date)
    status = db.Column(db.String(60), nullable=False, default="Aguardando documentos")
    documents_received = db.Column(db.Text)
    documents_pending = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="SET NULL"))
    company = db.relationship("Company", backref=db.backref("certificates", lazy=True))
    certificate_name = db.Column(db.String(180), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False, index=True)
    password_reference = db.Column(db.String(180))  # NÃO guardar senha real.
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class ExternalService(db.Model):
    __tablename__ = "external_services"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="SET NULL"))
    company = db.relationship("Company", backref=db.backref("external_services", lazy=True))
    location = db.Column(db.String(180))
    address = db.Column(db.String(255))
    due_date = db.Column(db.Date, nullable=False, index=True)
    priority = db.Column(db.String(30), nullable=False, default="Normal")
    status = db.Column(db.String(40), nullable=False, default="Preciso ir")
    documents = db.Column(db.Text)
    protocol = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# ---------- Helpers ----------

def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()

def parse_time(value):
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()

def login_required():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None

@app.template_filter("brdate")
def brdate(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)

@app.template_filter("brtime")
def brtime(value):
    if not value:
        return "--:--"
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)

@app.template_filter("certlabel")
def certlabel(value):
    if not value:
        return "Sem data"
    days = (value - date.today()).days
    if days < 0:
        return f"Vencido há {abs(days)} dia(s)"
    if days == 0:
        return "Vence hoje"
    return f"{days} dia(s)"

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ---------- Auth ----------

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.count() > 0:
        return redirect(url_for("login"))

    required_token = os.environ.get("SETUP_TOKEN", "")
    if not required_token:
        return render_template("setup_blocked.html"), 503

    if request.method == "POST":
        setup_token = request.form.get("setup_token", "")
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if setup_token != required_token:
            flash("Código de primeiro acesso incorreto.", "danger")
        elif not name or not username or not password:
            flash("Preencha todos os campos.", "danger")
        elif len(password) < 8:
            flash("Use uma senha com pelo menos 8 caracteres.", "danger")
        elif password != confirm:
            flash("As senhas não coincidem.", "danger")
        else:
            user = User(
                name=name,
                username=username,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            flash("Administrador criado. Faça seu login.", "success")
            return redirect(url_for("login"))

    return render_template("setup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if User.query.count() == 0:
        return redirect(url_for("setup"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            session["user_name"] = user.name
            return redirect(url_for("dashboard"))

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- Dashboard ----------

@app.route("/")
def dashboard():
    auth = login_required()
    if auth:
        return auth

    today = date.today()
    task_today = Task.query.filter(Task.task_date == today, Task.status != "Concluída").count()
    pending = Task.query.filter(Task.status != "Concluída").count()
    overdue = Task.query.filter(Task.task_date < today, Task.status != "Concluída").count()
    admissions_open = Admission.query.filter(Admission.status != "Concluída").count()
    externals_open = ExternalService.query.filter(ExternalService.status != "Entregue").count()

    today_tasks = Task.query.filter_by(task_date=today).order_by(Task.task_time.asc()).all()
    cert_alerts = (
        Certificate.query
        .filter(Certificate.expiry_date <= today + timedelta(days=30))
        .order_by(Certificate.expiry_date.asc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard.html",
        task_today=task_today,
        pending=pending,
        overdue=overdue,
        admissions=admissions_open,
        externals=externals_open,
        today_tasks=today_tasks,
        cert_alerts=cert_alerts,
    )

# ---------- Agenda ----------

@app.route("/agenda", methods=["GET", "POST"])
def agenda():
    auth = login_required()
    if auth:
        return auth

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Informe a atividade.", "danger")
        else:
            task = Task(
                title=title,
                category=request.form.get("category", "Tarefa geral"),
                task_date=parse_date(request.form.get("task_date")) or date.today(),
                task_time=parse_time(request.form.get("task_time")),
                priority=request.form.get("priority", "Normal"),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(task)
            db.session.commit()
            flash("Atividade adicionada.", "success")
            return redirect(url_for("agenda"))

    rows = Task.query.order_by(Task.task_date.asc(), Task.task_time.asc()).all()
    return render_template("agenda.html", tasks=rows)

@app.route("/agenda/<int:item_id>/done", methods=["POST"])
def task_done(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Task, item_id)
    item.status = "Concluída"
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("agenda"))

@app.route("/agenda/<int:item_id>/delete", methods=["POST"])
def task_delete(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Task, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Atividade excluída.", "success")
    return redirect(url_for("agenda"))

# ---------- Empresas ----------

@app.route("/empresas", methods=["GET", "POST"])
def companies():
    auth = login_required()
    if auth:
        return auth

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Informe a empresa.", "danger")
        else:
            item = Company(
                name=name,
                cnpj=request.form.get("cnpj", "").strip(),
                contact_name=request.form.get("contact_name", "").strip(),
                phone=request.form.get("phone", "").strip(),
                email=request.form.get("email", "").strip(),
                address=request.form.get("address", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(item)
            db.session.commit()
            flash("Empresa cadastrada.", "success")
            return redirect(url_for("companies"))

    rows = Company.query.order_by(Company.name.asc()).all()
    return render_template("companies.html", rows=rows)

@app.route("/empresas/<int:item_id>/delete", methods=["POST"])
def company_delete(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Company, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Empresa excluída.", "success")
    return redirect(url_for("companies"))

# ---------- Admissões ----------

@app.route("/admissoes", methods=["GET", "POST"])
def admissions():
    auth = login_required()
    if auth:
        return auth

    if request.method == "POST":
        employee = request.form.get("employee_name", "").strip()
        if not employee:
            flash("Informe o funcionário.", "danger")
        else:
            item = Admission(
                employee_name=employee,
                cpf=request.form.get("cpf", "").strip(),
                role=request.form.get("role", "").strip(),
                company_id=request.form.get("company_id") or None,
                admission_date=parse_date(request.form.get("admission_date")) or date.today(),
                deadline=parse_date(request.form.get("deadline")),
                status=request.form.get("status", "Aguardando documentos"),
                documents_received=request.form.get("documents_received", "").strip(),
                documents_pending=request.form.get("documents_pending", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(item)
            db.session.commit()
            flash("Admissão cadastrada.", "success")
            return redirect(url_for("admissions"))

    rows = Admission.query.order_by(Admission.admission_date.desc()).all()
    companies_list = Company.query.order_by(Company.name.asc()).all()
    return render_template("admissions.html", rows=rows, companies=companies_list)

@app.route("/admissoes/<int:item_id>/status", methods=["POST"])
def admission_status(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Admission, item_id)
    item.status = request.form.get("status", "Em andamento")
    db.session.commit()
    return redirect(url_for("admissions"))

@app.route("/admissoes/<int:item_id>/delete", methods=["POST"])
def admission_delete(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Admission, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Admissão excluída.", "success")
    return redirect(url_for("admissions"))

# ---------- Certificados ----------

@app.route("/certificados", methods=["GET", "POST"])
def certificates():
    auth = login_required()
    if auth:
        return auth

    if request.method == "POST":
        name = request.form.get("certificate_name", "").strip()
        expiry = parse_date(request.form.get("expiry_date"))
        if not name or not expiry:
            flash("Informe o certificado e a validade.", "danger")
        else:
            item = Certificate(
                company_id=request.form.get("company_id") or None,
                certificate_name=name,
                expiry_date=expiry,
                password_reference=request.form.get("password_reference", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(item)
            db.session.commit()
            flash("Certificado cadastrado.", "success")
            return redirect(url_for("certificates"))

    rows = Certificate.query.order_by(Certificate.expiry_date.asc()).all()
    companies_list = Company.query.order_by(Company.name.asc()).all()
    return render_template("certificates.html", rows=rows, companies=companies_list)

@app.route("/certificados/<int:item_id>/delete", methods=["POST"])
def certificate_delete(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(Certificate, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Certificado excluído.", "success")
    return redirect(url_for("certificates"))

# ---------- Serviços externos ----------

@app.route("/externos", methods=["GET", "POST"])
def external_services():
    auth = login_required()
    if auth:
        return auth

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        due_date = parse_date(request.form.get("due_date"))
        if not title or not due_date:
            flash("Informe o serviço e o prazo.", "danger")
        else:
            item = ExternalService(
                title=title,
                company_id=request.form.get("company_id") or None,
                location=request.form.get("location", "").strip(),
                address=request.form.get("address", "").strip(),
                due_date=due_date,
                priority=request.form.get("priority", "Normal"),
                status=request.form.get("status", "Preciso ir"),
                documents=request.form.get("documents", "").strip(),
                protocol=request.form.get("protocol", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(item)
            db.session.commit()
            flash("Serviço externo cadastrado.", "success")
            return redirect(url_for("external_services"))

    rows = ExternalService.query.order_by(ExternalService.due_date.asc()).all()
    companies_list = Company.query.order_by(Company.name.asc()).all()
    return render_template("external_services.html", rows=rows, companies=companies_list)

@app.route("/externos/<int:item_id>/status", methods=["POST"])
def external_status(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(ExternalService, item_id)
    item.status = request.form.get("status", "Em andamento")
    item.protocol = request.form.get("protocol", "").strip()
    db.session.commit()
    return redirect(url_for("external_services"))

@app.route("/externos/<int:item_id>/delete", methods=["POST"])
def external_delete(item_id):
    auth = login_required()
    if auth:
        return auth
    item = db.get_or_404(ExternalService, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Serviço externo excluído.", "success")
    return redirect(url_for("external_services"))

# ---------- Health ----------

@app.route("/health")
def health():
    return {"status": "ok"}, 200

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False)
