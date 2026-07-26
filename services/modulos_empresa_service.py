import time
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for
from psycopg2.extras import Json

from database import conectar, criar_cursor


class ModulosEmpresaService:
    MODULOS = {
        "vendas": {
            "nome": "Vendas / PDV",
            "descricao": "Carrinho, descontos, clientes e finalização de vendas.",
            "dependencias": ["produtos", "caixa"],
        },
        "produtos": {
            "nome": "Produtos e estoque",
            "descricao": "Cadastro de produtos, preços, imagens e estoque.",
            "dependencias": [],
        },
        "clientes": {
            "nome": "Clientes",
            "descricao": "Cadastro, relacionamento e histórico de compras.",
            "dependencias": [],
        },
        "caixa": {
            "nome": "Caixa",
            "descricao": "Abertura, movimentações, fechamento e histórico.",
            "dependencias": [],
        },
        "estatisticas": {
            "nome": "Estatísticas",
            "descricao": "Indicadores, relatórios e visão financeira.",
            "dependencias": [],
        },
        "custos": {
            "nome": "Custos empresariais",
            "descricao": "Despesas, pagamentos e vencimentos.",
            "dependencias": ["estatisticas"],
        },
        "mesas": {
            "nome": "Mesas e comandas",
            "descricao": "Atendimento por mesa para bares e restaurantes.",
            "dependencias": ["vendas", "produtos", "caixa"],
        },
        "emprestimos": {
            "nome": "Empréstimos",
            "descricao": "Clientes, contratos, parcelas e cobranças.",
            "dependencias": [],
        },
        "nami": {
            "nome": "Assistente Nami",
            "descricao": "Assistente inteligente integrada ao Nexus PDV.",
            "dependencias": [],
        },
    }

    MODULOS_PADRAO = {
        "vendas",
        "produtos",
        "clientes",
        "caixa",
        "estatisticas",
        "custos",
        "nami",
    }

    @classmethod
    def catalogo(cls):
        return {
            codigo: {
                "codigo": codigo,
                **dados,
            }
            for codigo, dados in cls.MODULOS.items()
        }

    @classmethod
    def normalizar(cls, modulos):
        selecionados = {
            str(modulo).strip().lower()
            for modulo in (modulos or [])
            if str(modulo).strip().lower() in cls.MODULOS
        }

        pendentes = list(selecionados)

        while pendentes:
            modulo = pendentes.pop()

            for dependencia in cls.MODULOS[modulo]["dependencias"]:
                if dependencia not in selecionados:
                    selecionados.add(dependencia)
                    pendentes.append(dependencia)

        return selecionados

    @classmethod
    def salvar_com_cursor(
        cls,
        cursor,
        empresa_id,
        modulos,
        *,
        desativar_ausentes=True,
    ):
        selecionados = cls.normalizar(modulos)

        for codigo in cls.MODULOS:
            ativo = codigo in selecionados

            if not desativar_ausentes and not ativo:
                continue

            cursor.execute(
                """
                INSERT INTO empresa_modulos (
                    empresa_id,
                    modulo,
                    ativo,
                    configuracoes,
                    criado_em,
                    atualizado_em
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (empresa_id, modulo)
                DO UPDATE SET
                    ativo = EXCLUDED.ativo,
                    atualizado_em = CURRENT_TIMESTAMP
                """,
                (
                    int(empresa_id),
                    codigo,
                    ativo,
                    Json({}),
                ),
            )

        cursor.execute(
            """
            UPDATE empresa
            SET emprestimos_ativo = %s
            WHERE id = %s
            """,
            (
                "emprestimos" in selecionados,
                int(empresa_id),
            ),
        )

        return selecionados

    @classmethod
    def salvar(cls, empresa_id, modulos):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            selecionados = cls.salvar_com_cursor(
                cursor,
                empresa_id,
                modulos,
            )
            conn.commit()
            return selecionados
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def listar(cls, empresa_id):
        if not empresa_id:
            return set()

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT modulo
                FROM empresa_modulos
                WHERE empresa_id = %s
                  AND ativo = TRUE
                """,
                (int(empresa_id),),
            )

            encontrados = {
                registro["modulo"]
                for registro in cursor.fetchall()
            }

            if encontrados:
                return cls.normalizar(encontrados)

            cursor.execute(
                """
                SELECT COALESCE(emprestimos_ativo, FALSE)
                       AS emprestimos_ativo
                FROM empresa
                WHERE id = %s
                LIMIT 1
                """,
                (int(empresa_id),),
            )

            empresa = cursor.fetchone()
            iniciais = set(cls.MODULOS_PADRAO)

            if empresa and empresa["emprestimos_ativo"]:
                iniciais.add("emprestimos")

            cls.salvar_com_cursor(
                cursor,
                empresa_id,
                iniciais,
            )
            conn.commit()
            return iniciais
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def detalhes_empresa(cls, empresa_id):
        ativos = cls.listar(empresa_id)

        return [
            {
                **dados,
                "ativo": codigo in ativos,
            }
            for codigo, dados in cls.catalogo().items()
        ]


ROTAS_POR_MODULO = (
    ("/mesas", "mesas"),
    ("/comandas", "mesas"),
    ("/produtos", "produtos"),
    ("/clientes", "clientes"),
    ("/vendas", "vendas"),
    ("/caixa", "caixa"),
    ("/historico_caixa", "caixa"),
    ("/historico_caixas", "caixa"),
    ("/relatorio_caixa", "caixa"),
    ("/estatisticas", "estatisticas"),
    ("/minhas-estatisticas", "estatisticas"),
    ("/custos", "custos"),
    ("/emprestimos", "emprestimos"),
    ("/ia", "nami"),
)


def _carregar_modulos_sessao(forcar=False):
    if not session.get("logado"):
        return set()

    if session.get("nivel") == "master":
        return set(ModulosEmpresaService.MODULOS)

    empresa_id = session.get("empresa_id")

    if not empresa_id:
        return set()

    agora = time.time()
    atualizado_em = float(
        session.get("modulos_atualizados_em", 0) or 0
    )

    if (
        forcar
        or "modulos_empresa" not in session
        or agora - atualizado_em >= 60
    ):
        ativos = ModulosEmpresaService.listar(empresa_id)
        session["modulos_empresa"] = sorted(ativos)
        session["modulos_atualizados_em"] = agora
        session["emprestimos_ativo"] = "emprestimos" in ativos

    return set(session.get("modulos_empresa", []))


def modulo_ativo(codigo):
    if session.get("nivel") == "master":
        return True

    return codigo in _carregar_modulos_sessao()


def modulo_obrigatorio(codigo):
    def decorador(funcao):
        @wraps(funcao)
        def protegida(*args, **kwargs):
            if not session.get("logado"):
                return redirect(url_for("login"))

            if not modulo_ativo(codigo):
                abort(403)

            return funcao(*args, **kwargs)

        return protegida

    return decorador


def registrar_modulos_app(app):
    @app.before_request
    def proteger_modulos_da_empresa():
        if (
            not session.get("logado")
            or session.get("nivel") == "master"
        ):
            return None

        caminho = request.path.rstrip("/") or "/"

        for prefixo, modulo in ROTAS_POR_MODULO:
            if caminho == prefixo or caminho.startswith(prefixo + "/"):
                if not modulo_ativo(modulo):
                    flash(
                        "Este módulo não está liberado para sua empresa.",
                        "erro",
                    )
                    return redirect(url_for("dashboard"))

        return None

    @app.context_processor
    def disponibilizar_modulos_templates():
        return {
            "modulo_ativo": modulo_ativo,
            "catalogo_modulos": ModulosEmpresaService.catalogo(),
        }

