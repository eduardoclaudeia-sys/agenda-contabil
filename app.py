from __future__ import annotations

from flask import Flask, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, limiter
from helpers import cnpjfmt, moeda, pct
from servicos.explanations import EXPLICACOES
from servicos.rules import registrar_regras_arquivo
from servicos.migrations import aplicar_migracoes_seguras
from sqlalchemy import text


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    Config.apply(app)
    if config_overrides:
        app.config.update(config_overrides)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Importa modelos para registrar metadata antes de create_all.
    import models  # noqa: F401

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.empresas import bp as empresas_bp
    from routes.simples import bp as simples_bp
    from routes.presumido import bp as presumido_bp
    from routes.real import bp as real_bp
    from routes.comparador import bp as comparador_bp
    from routes.historico import bp as historico_bp
    from routes.usuarios import bp as usuarios_bp

    for bp in (
        auth_bp, dashboard_bp, empresas_bp, simples_bp, presumido_bp,
        real_bp, comparador_bp, historico_bp, usuarios_bp,
    ):
        app.register_blueprint(bp)

    app.add_template_filter(moeda, "moeda")
    app.add_template_filter(pct, "pct")
    app.add_template_filter(cnpjfmt, "cnpjfmt")

    @app.context_processor
    def inject_globals():
        return {"explicacoes": EXPLICACOES}

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "ok", "app": "Motor Tributário JSM", "versao": "5.0"}), 200
        except Exception:
            db.session.rollback()
            return jsonify({"status": "degraded", "database": "erro", "versao": "5.0"}), 503

    @app.errorhandler(413)
    def arquivo_grande(_):
        return render_template("erro.html", codigo=413, titulo="Arquivo muito grande",
                               mensagem="O arquivo ultrapassou o limite aceito pelo sistema."), 413

    @app.errorhandler(429)
    def limite_requisicoes(_):
        return render_template("erro.html", codigo=429, titulo="Muitas tentativas",
                               mensagem="Aguarde alguns minutos antes de tentar novamente."), 429

    @app.errorhandler(404)
    def nao_encontrado(_):
        return render_template("erro.html", codigo=404, titulo="Página não encontrada",
                               mensagem="O endereço solicitado não existe ou foi movido."), 404

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        )
        return response

    with app.app_context():
        db.create_all()
        aplicar_migracoes_seguras()
        registrar_regras_arquivo()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
