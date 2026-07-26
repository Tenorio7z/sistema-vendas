import os
from datetime import timedelta

print("######## APP INICIADO ########")

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "nexus-dev-altere-em-producao",
)

app.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=timedelta(hours=12),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.getenv("COOKIE_SECURE", "false").lower() == "true"
    ),
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
)

from routes.ia import ia_bp
from routes.auth import registrar_rotas as auth
from routes.dashboard import registrar_rotas as dashboard
from routes.emprestimos import emprestimos_bp
from routes.produtos import registrar_rotas as produtos
from routes.vendas import registrar_rotas as vendas
from routes.admin import registrar_rotas as admin
from routes.caixa import registrar_rotas as caixa
from routes.perfis import registrar_rotas as perfis_rotas
from routes.funcionario_dashboard import (
    registrar_rotas as funcionario_dashboard,
)
from routes.historico_caixas import (
    registrar_rotas as historico_caixas_rotas,
)
from routes.notificacoes import registrar_rotas as notificacoes
from routes.api_mobile import (
    registrar_rotas as api_mobile_login,
)
from routes import planos
from routes import estatisticas
from routes.clientes import (
    registrar_rotas as clientes_rotas,
)
from routes.estatisticas_funcionario import (
    registrar_rotas as registrar_rotas_estatisticas_funcionario,
)
from routes.onboarding_publico import (
    registrar_rotas as registrar_rotas_onboarding_publico,
)
from routes.onboarding_admin import (
    registrar_rotas_onboarding_admin,
)
from routes.custos import (
    registrar_rotas as registrar_rotas_custos,
)
from services.modulos_empresa_service import (
    registrar_modulos_app,
)

from routes.mesas import (
    registrar_rotas as mesas_rotas,
)


notificacoes(app)
historico_caixas_rotas(app)
estatisticas.registrar_rotas(app)
planos.registrar_rotas(app)
registrar_rotas_estatisticas_funcionario(app)
perfis_rotas(app)
funcionario_dashboard(app)
vendas(app, socketio)
registrar_rotas_onboarding_publico(app)
registrar_rotas_onboarding_admin(app)
auth(app)
dashboard(app)
produtos(app)
clientes_rotas(app)
mesas_rotas(
    app,
    socketio,
)
admin(app)
caixa(app)
registrar_rotas_custos(app)

app.register_blueprint(ia_bp)
app.register_blueprint(emprestimos_bp)

api_mobile_login(app, socketio)

# Registre depois das rotas. O before_request continua protegendo todas elas.
registrar_modulos_app(app)

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
