from flask import *
from database import conectar
import secrets
from datetime import datetime
from services.auth_api import validar_token

def registrar_rotas(app, socketio):

    @app.route("/api/mobile/login", methods=["POST"])
    def api_mobile_login():

        dados = request.get_json()

        usuario = dados.get("usuario")
        senha = dados.get("senha")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM usuarios

        WHERE usuario = ?

        """, (usuario,))

        user = cursor.fetchone()

        conn.close()

        if not user:

            return jsonify({

                "sucesso": False,
                "mensagem": "Usuário não encontrado"

            }), 401

        
        from werkzeug.security import check_password_hash

        if not check_password_hash(
            user["senha"],
            senha
        ):

            return jsonify({

                "sucesso": False,
                "mensagem": "Senha inválida"

            }), 401


        token = secrets.token_hex(32)

        from datetime import timedelta

        expira_em = (
            datetime.now() +
            timedelta(days=30)
        )
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        INSERT INTO api_tokens (

            usuario_id,
            token,
            data_criacao,
            expira_em

        )

        VALUES (?,?,?,?)

        """,

        (

            user["id"],
            token,
            str(datetime.now()),
            str(expira_em)

        ))

        conn.commit()
        conn.close()

        return jsonify({

            "sucesso": True,

            "usuario_id": user["id"],

            "empresa_id": user["empresa_id"],

            "usuario": user["usuario"],

            "nivel": user["nivel"],

            "token": token

        })
    
    @app.route("/api/mobile/dashboard/<int:empresa_id>")
    def api_mobile_dashboard(empresa_id):

        usuario = validar_token()

        if not usuario:

            return jsonify({

                "erro": "Não autorizado"

            }), 401
        
        if usuario["empresa_id"] != empresa_id:

            return jsonify({

                "erro": "Acesso negado"

            }), 403
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT IFNULL(SUM(valor),0) as faturamento

        FROM vendas

        WHERE empresa_id = ?

        """, (empresa_id,))

        faturamento = cursor.fetchone()["faturamento"]

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM vendas

        WHERE empresa_id = ?

        """, (empresa_id,))

        vendas = cursor.fetchone()["total"]

        conn.close()

        return jsonify({

            "faturamento": faturamento,
            "vendas": vendas

        })
        
    @app.route("/api/mobile/notificacoes/<int:empresa_id>")
    def api_mobile_notificacoes(empresa_id):
        
        usuario = validar_token()

        if not usuario:
            return jsonify({
                "erro": "Não autorizado"
            }), 401
        
        if usuario["empresa_id"] != empresa_id:

            return jsonify({

                "erro": "Acesso negado"

            }), 403
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM notificacoes

        WHERE empresa_id = ?

        ORDER BY id DESC

        LIMIT 20

        """, (empresa_id,))

        notificacoes = cursor.fetchall()

        conn.close()

        resultado = []

        for n in notificacoes:

            resultado.append({

                "funcionario": n["funcionario"],
                "produto": n["produto"],
                "valor": n["valor"],
                "data": n["data"]

            })

        return jsonify(resultado)
    
    @app.route("/api/mobile/produtos/<int:empresa_id>")
    def api_mobile_produtos(empresa_id):

        usuario = validar_token()

        if not usuario:
            return jsonify({
                "erro": "Não autorizado"
            }), 401
        
        if usuario["empresa_id"] != empresa_id:

            return jsonify({

                "erro": "Acesso negado"

            }), 403
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT
            id,
            nome,
            preco,
            estoque,
            codigo_barras

        FROM produtos

        WHERE empresa_id = ?

        ORDER BY nome

        """, (empresa_id,))

        produtos = cursor.fetchall()

        conn.close()

        resultado = []

        for p in produtos:

            resultado.append({

                "id": p["id"],
                "nome": p["nome"],
                "preco": p["preco"],
                "estoque": p["estoque"],
                "codigo_barras": p["codigo_barras"]

            })

        return jsonify(resultado)
    
    @app.route("/api/mobile/estoque/<int:empresa_id>")
    def api_mobile_estoque(empresa_id):

        usuario = validar_token()

        if not usuario:
            return jsonify({
                "erro": "Não autorizado"
            }), 401
        
        if usuario["empresa_id"] != empresa_id:

            return jsonify({

                "erro": "Acesso negado"

            }), 403
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM produtos

        WHERE empresa_id = ?

        """, (empresa_id,))

        total_produtos = cursor.fetchone()["total"]

        cursor.execute("""

        SELECT COUNT(*) as baixo

        FROM produtos

        WHERE empresa_id = ?
        AND estoque <= 5

        """, (empresa_id,))

        estoque_baixo = cursor.fetchone()["baixo"]

        conn.close()

        return jsonify({

            "total_produtos": total_produtos,
            "estoque_baixo": estoque_baixo

        })
        
    @app.route("/api/mobile/ultimas_vendas/<int:empresa_id>")
    def api_mobile_ultimas_vendas(empresa_id):

        usuario = validar_token()

        if not usuario:
            return jsonify({
                "erro": "Não autorizado"
            }), 401
        
        if usuario["empresa_id"] != empresa_id:

            return jsonify({

                "erro": "Acesso negado"

            }), 403
        
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT
            v.valor,
            v.data_venda,
            p.nome

        FROM vendas v

        INNER JOIN produtos p
            ON p.id = v.produto_id

        WHERE v.empresa_id = ?

        ORDER BY v.id DESC

        LIMIT 10

        """, (empresa_id,))

        vendas = cursor.fetchall()

        conn.close()

        resultado = []

        for v in vendas:

            resultado.append({

                "produto": v["nome"],
                "valor": v["valor"],
                "data": v["data_venda"]

            })

        return jsonify(resultado)
    
    @app.route("/api/mobile/logout", methods=["POST"])
    def api_mobile_logout():

        token = request.headers.get(
            "Authorization"
        )

        if not token:

            return jsonify({

                "erro": "Token não informado"

            }), 401

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        DELETE FROM api_tokens

        WHERE token = ?

        """,

        (
            token,
        ))

        conn.commit()
        conn.close()

        return jsonify({

            "sucesso": True,
            "mensagem": "Logout realizado"

        })
        
    
    @app.route("/api/mobile/perfil")
    def api_mobile_perfil():

        usuario = validar_token()

        if not usuario:

            return jsonify({
                "erro": "Não autorizado"
            }), 401

        return jsonify({

            "id": usuario["id"],
            "usuario": usuario["usuario"],
            "nivel": usuario["nivel"],
            "empresa_id": usuario["empresa_id"]

        })
    
    
    @app.route("/api/mobile/teste_socket")
    def teste_socket():

        socketio.emit(
            "teste_socket",
            {
                "mensagem": "Socket funcionando"
            }
        )

        return jsonify({
            "sucesso": True
        })
        
        
    @app.route("/api/mobile/salvar_token", methods=["POST"])
    def salvar_token():

        usuario = validar_token()

        if not usuario:
            return jsonify({
                "erro": "Não autorizado"
            }), 401

        dados = request.get_json()
        fcm_token = dados.get("fcm_token")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        UPDATE usuarios

        SET fcm_token = ?

        WHERE id = ?

        """, (fcm_token, usuario["id"]))

        conn.commit()
        conn.close()

        print("TOKEN FCM SALVO:", fcm_token)

        return jsonify({
            "sucesso": True
        })
    