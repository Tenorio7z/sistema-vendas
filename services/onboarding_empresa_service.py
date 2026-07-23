import hashlib
import re
import secrets

from datetime import datetime

from psycopg2.extras import Json

from werkzeug.security import (
    generate_password_hash,
)

from database import (
    conectar,
    criar_cursor,
)


class OnboardingEmpresaErro(ValueError):
    pass


class OnboardingEmpresaService:

    TAMANHO_TOKEN = 48
    VALIDADE_PADRAO_HORAS = 72
    VALIDADE_MAXIMA_HORAS = 24 * 30

    # =====================================================
    # FUNÇÕES INTERNAS
    # =====================================================

    @staticmethod
    def _texto(
        valor,
        limite=None,
    ):
        texto = str(
            valor or ""
        ).strip()

        if limite:
            texto = texto[:limite]

        return texto

    @classmethod
    def _hash_token(
        cls,
        token,
    ):
        token = cls._texto(
            token
        )

        if not token:
            raise OnboardingEmpresaErro(
                "Token de convite não informado."
            )

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _somente_numeros(
        valor,
    ):
        return re.sub(
            r"\D",
            "",
            str(valor or ""),
        )

    @staticmethod
    def _registrar_auditoria(
        cursor,
        *,
        acao,
        descricao,
        convite_id=None,
        solicitacao_id=None,
        usuario_id=None,
        endereco_ip=None,
        dados_anteriores=None,
        dados_novos=None,
    ):
        dados_anteriores_json = (
            Json(dados_anteriores)
            if dados_anteriores is not None
            else None
        )

        dados_novos_json = (
            Json(dados_novos)
            if dados_novos is not None
            else None
        )

        cursor.execute(
            """
            INSERT INTO onboarding_auditoria (
                solicitacao_id,
                convite_id,
                usuario_id,
                acao,
                descricao,
                dados_anteriores,
                dados_novos,
                endereco_ip
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                solicitacao_id,
                convite_id,
                usuario_id,
                acao,
                descricao,
                dados_anteriores_json,
                dados_novos_json,
                endereco_ip,
            ),
        )

    # =====================================================
    # GERAR CONVITE
    # =====================================================

    @classmethod
    def criar_convite(
        cls,
        *,
        criado_por,
        url_base,
        validade_horas=VALIDADE_PADRAO_HORAS,
        nome_destinatario=None,
        telefone_destinatario=None,
        email_destinatario=None,
        endereco_ip=None,
    ):
        try:
            criado_por = int(
                criado_por
            )

        except (
            TypeError,
            ValueError,
        ) as erro:
            raise OnboardingEmpresaErro(
                "Administrador inválido."
            ) from erro

        if criado_por <= 0:
            raise OnboardingEmpresaErro(
                "Administrador inválido."
            )

        url_base = cls._texto(
            url_base,
            500,
        ).rstrip("/")

        if not url_base:
            raise OnboardingEmpresaErro(
                "URL base do sistema não informada."
            )

        try:
            validade_horas = int(
                validade_horas
                or cls.VALIDADE_PADRAO_HORAS
            )

        except (
            TypeError,
            ValueError,
        ) as erro:
            raise OnboardingEmpresaErro(
                "Validade do convite inválida."
            ) from erro

        if not 1 <= validade_horas <= cls.VALIDADE_MAXIMA_HORAS:
            raise OnboardingEmpresaErro(
                (
                    "A validade deve ficar entre "
                    "1 hora e 30 dias."
                )
            )

        nome_destinatario = cls._texto(
            nome_destinatario,
            160,
        ) or None

        telefone_destinatario = cls._texto(
            telefone_destinatario,
            30,
        ) or None

        email_destinatario = cls._texto(
            email_destinatario,
            180,
        ).lower() or None

        token_original = secrets.token_urlsafe(
            cls.TAMANHO_TOKEN
        )

        token_hash = cls._hash_token(
            token_original
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    usuario,
                    nivel

                FROM usuarios

                WHERE id = %s
                  AND nivel = 'master'

                LIMIT 1
                """,
                (
                    criado_por,
                ),
            )

            administrador = cursor.fetchone()

            if not administrador:
                raise OnboardingEmpresaErro(
                    (
                        "Somente um usuário master "
                        "pode gerar convites."
                    )
                )

            cursor.execute(
                """
                INSERT INTO onboarding_convites (
                    token_hash,
                    criado_por,
                    nome_destinatario,
                    telefone_destinatario,
                    email_destinatario,
                    status,
                    expira_em
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'ativo',
                    CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 hour')
                )
                RETURNING
                    id,
                    status,
                    expira_em,
                    criado_em
                """,
                (
                    token_hash,
                    criado_por,
                    nome_destinatario,
                    telefone_destinatario,
                    email_destinatario,
                    validade_horas,
                ),
            )

            convite = cursor.fetchone()

            cls._registrar_auditoria(
                cursor,
                convite_id=convite["id"],
                usuario_id=criado_por,
                acao="convite_criado",
                descricao=(
                    "Convite de cadastro de empresa criado."
                ),
                endereco_ip=endereco_ip,
                dados_novos={
                    "validade_horas": validade_horas,
                    "nome_destinatario": nome_destinatario,
                    "telefone_destinatario": (
                        telefone_destinatario
                    ),
                    "email_destinatario": (
                        email_destinatario
                    ),
                },
            )

            conn.commit()

            return {
                "id": convite["id"],
                "status": convite["status"],
                "expira_em": convite["expira_em"],
                "criado_em": convite["criado_em"],
                "token": token_original,
                "link": (
                    f"{url_base}/convite/"
                    f"{token_original}"
                ),
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # VALIDAR CONVITE
    # =====================================================

    @classmethod
    def validar_convite(
        cls,
        token,
    ):
        token_hash = cls._hash_token(
            token
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.status,
                    c.expira_em,
                    c.utilizado_em,
                    c.revogado_em,
                    c.criado_em,

                    c.nome_destinatario,
                    c.telefone_destinatario,
                    c.email_destinatario,

                    c.criado_por,

                    u.usuario AS criado_por_nome,

                    EXISTS (
                        SELECT 1

                        FROM onboarding_solicitacoes s

                        WHERE s.convite_id = c.id
                    ) AS possui_solicitacao

                FROM onboarding_convites c

                LEFT JOIN usuarios u
                    ON u.id = c.criado_por

                WHERE c.token_hash = %s

                LIMIT 1

                FOR UPDATE OF c
                """,
                (
                    token_hash,
                ),
            )

            convite = cursor.fetchone()

            if not convite:
                raise OnboardingEmpresaErro(
                    "Convite não encontrado."
                )

            agora = datetime.now()

            if (
                convite["status"] == "ativo"
                and convite["expira_em"]
                and convite["expira_em"] <= agora
            ):
                cursor.execute(
                    """
                    UPDATE onboarding_convites

                    SET status = 'expirado'

                    WHERE id = %s
                      AND status = 'ativo'
                    """,
                    (
                        convite["id"],
                    ),
                )

                cls._registrar_auditoria(
                    cursor,
                    convite_id=convite["id"],
                    usuario_id=None,
                    acao="convite_expirado",
                    descricao=(
                        "Convite expirado automaticamente."
                    ),
                )

                conn.commit()

                raise OnboardingEmpresaErro(
                    (
                        "Este convite expirou. "
                        "Solicite um novo link."
                    )
                )

            if convite["status"] == "revogado":
                raise OnboardingEmpresaErro(
                    "Este convite foi revogado."
                )

            if convite["status"] == "expirado":
                raise OnboardingEmpresaErro(
                    (
                        "Este convite expirou. "
                        "Solicite um novo link."
                    )
                )

            if (
                convite["status"] == "utilizado"
                or convite["possui_solicitacao"]
            ):
                raise OnboardingEmpresaErro(
                    "Este convite já foi utilizado."
                )

            if convite["status"] != "ativo":
                raise OnboardingEmpresaErro(
                    "Este convite não está disponível."
                )

            conn.commit()

            return dict(
                convite
            )

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # ENVIAR SOLICITAÇÃO DE CADASTRO
    # =====================================================

    @classmethod
    def criar_solicitacao(
        cls,
        *,
        token,
        nome_empresa,
        nome_responsavel,
        cpf_cnpj,
        telefone,
        email,
        usuario,
        senha,
        confirmar_senha,
        segmento=None,
        cidade=None,
        estado=None,
        observacoes_cliente=None,
        aceitou_termos=False,
        aceitou_whatsapp=False,
        endereco_ip=None,
        user_agent=None,
    ):
        token_hash = cls._hash_token(
            token
        )

        nome_empresa = cls._texto(
            nome_empresa,
            180,
        )

        nome_responsavel = cls._texto(
            nome_responsavel,
            180,
        )

        cpf_cnpj = cls._texto(
            cpf_cnpj,
            30,
        )

        telefone = cls._texto(
            telefone,
            30,
        )

        email = cls._texto(
            email,
            180,
        ).lower()

        usuario = cls._texto(
            usuario,
            120,
        )

        senha = str(
            senha or ""
        )

        confirmar_senha = str(
            confirmar_senha or ""
        )

        segmento = cls._texto(
            segmento,
            120,
        ) or None

        cidade = cls._texto(
            cidade,
            120,
        ) or None

        estado = cls._texto(
            estado,
            2,
        ).upper() or None

        observacoes_cliente = cls._texto(
            observacoes_cliente,
            2000,
        ) or None

        endereco_ip = cls._texto(
            endereco_ip,
            80,
        ) or None

        user_agent = cls._texto(
            user_agent,
            1000,
        ) or None

        telefone_normalizado = cls._somente_numeros(
            telefone
        )

        cpf_cnpj_normalizado = cls._somente_numeros(
            cpf_cnpj
        )

        # ==========================================
        # VALIDAÇÕES
        # ==========================================

        if len(nome_empresa) < 2:
            raise OnboardingEmpresaErro(
                "Informe o nome da empresa."
            )

        if len(nome_responsavel) < 2:
            raise OnboardingEmpresaErro(
                "Informe o nome do responsável."
            )

        if not 10 <= len(telefone_normalizado) <= 13:
            raise OnboardingEmpresaErro(
                "Informe um WhatsApp válido com DDD."
            )

        if (
            cpf_cnpj_normalizado
            and len(cpf_cnpj_normalizado) not in (11, 14)
        ):
            raise OnboardingEmpresaErro(
                "Informe um CPF ou CNPJ válido."
            )

        if not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email,
        ):
            raise OnboardingEmpresaErro(
                "Informe um e-mail válido."
            )

        if not re.fullmatch(
            r"[A-Za-z0-9._-]{3,120}",
            usuario,
        ):
            raise OnboardingEmpresaErro(
                (
                    "O usuário deve possuir pelo menos "
                    "3 caracteres e usar somente letras, "
                    "números, ponto, hífen ou underline."
                )
            )

        if len(senha) < 8:
            raise OnboardingEmpresaErro(
                (
                    "A senha deve possuir pelo menos "
                    "8 caracteres."
                )
            )

        if not re.search(
            r"[A-Za-z]",
            senha,
        ):
            raise OnboardingEmpresaErro(
                (
                    "A senha deve possuir pelo menos "
                    "uma letra."
                )
            )

        if not re.search(
            r"\d",
            senha,
        ):
            raise OnboardingEmpresaErro(
                (
                    "A senha deve possuir pelo menos "
                    "um número."
                )
            )

        if senha != confirmar_senha:
            raise OnboardingEmpresaErro(
                "As senhas informadas não são iguais."
            )

        if estado and not re.fullmatch(
            r"[A-Z]{2}",
            estado,
        ):
            raise OnboardingEmpresaErro(
                "Informe uma UF válida."
            )

        if not aceitou_termos:
            raise OnboardingEmpresaErro(
                (
                    "Você precisa aceitar os termos "
                    "e a política de privacidade."
                )
            )

        senha_hash = generate_password_hash(
            senha
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            # ======================================
            # BLOQUEAR E VALIDAR O CONVITE
            # ======================================

            cursor.execute(
                """
                SELECT
                    id,
                    status,
                    expira_em,
                    utilizado_em,
                    revogado_em

                FROM onboarding_convites

                WHERE token_hash = %s

                LIMIT 1

                FOR UPDATE
                """,
                (
                    token_hash,
                ),
            )

            convite = cursor.fetchone()

            if not convite:
                raise OnboardingEmpresaErro(
                    "Convite não encontrado."
                )

            if (
                convite["status"] == "ativo"
                and convite["expira_em"]
                and convite["expira_em"] <= datetime.now()
            ):
                cursor.execute(
                    """
                    UPDATE onboarding_convites

                    SET status = 'expirado'

                    WHERE id = %s
                    """,
                    (
                        convite["id"],
                    ),
                )

                cls._registrar_auditoria(
                    cursor,
                    convite_id=convite["id"],
                    usuario_id=None,
                    acao="convite_expirado",
                    descricao=(
                        "Convite expirado automaticamente."
                    ),
                    endereco_ip=endereco_ip,
                )

                conn.commit()

                raise OnboardingEmpresaErro(
                    (
                        "Este convite expirou. "
                        "Solicite um novo link."
                    )
                )

            if convite["status"] == "utilizado":
                raise OnboardingEmpresaErro(
                    "Este convite já foi utilizado."
                )

            if convite["status"] == "revogado":
                raise OnboardingEmpresaErro(
                    "Este convite foi revogado."
                )

            if convite["status"] == "expirado":
                raise OnboardingEmpresaErro(
                    (
                        "Este convite expirou. "
                        "Solicite um novo link."
                    )
                )

            if convite["status"] != "ativo":
                raise OnboardingEmpresaErro(
                    "Este convite não está disponível."
                )

            cursor.execute(
                """
                SELECT id

                FROM onboarding_solicitacoes

                WHERE convite_id = %s

                LIMIT 1
                """,
                (
                    convite["id"],
                ),
            )

            if cursor.fetchone():
                raise OnboardingEmpresaErro(
                    (
                        "Este convite já possui "
                        "uma solicitação."
                    )
                )

            # ======================================
            # VERIFICAR USUÁRIO EXISTENTE
            # ======================================

            cursor.execute(
                """
                SELECT id

                FROM usuarios

                WHERE LOWER(usuario) = LOWER(%s)

                LIMIT 1
                """,
                (
                    usuario,
                ),
            )

            if cursor.fetchone():
                raise OnboardingEmpresaErro(
                    (
                        "Este nome de usuário já está "
                        "sendo utilizado."
                    )
                )

            cursor.execute(
                """
                SELECT id

                FROM onboarding_solicitacoes

                WHERE LOWER(usuario) = LOWER(%s)
                  AND status IN (
                      'aguardando',
                      'em_analise',
                      'aprovada'
                  )

                LIMIT 1
                """,
                (
                    usuario,
                ),
            )

            if cursor.fetchone():
                raise OnboardingEmpresaErro(
                    (
                        "Já existe uma solicitação "
                        "com este usuário."
                    )
                )

            # ======================================
            # VERIFICAR CPF OU CNPJ PENDENTE
            # ======================================

            if cpf_cnpj_normalizado:
                cursor.execute(
                    """
                    SELECT id

                    FROM onboarding_solicitacoes

                    WHERE cpf_cnpj_normalizado = %s
                      AND status IN (
                          'aguardando',
                          'em_analise',
                          'aprovada'
                      )

                    LIMIT 1
                    """,
                    (
                        cpf_cnpj_normalizado,
                    ),
                )

                if cursor.fetchone():
                    raise OnboardingEmpresaErro(
                        (
                            "Já existe uma solicitação "
                            "para este CPF ou CNPJ."
                        )
                    )

            # ======================================
            # CADASTRAR SOLICITAÇÃO
            # ======================================

            cursor.execute(
                """
                INSERT INTO onboarding_solicitacoes (
                    convite_id,

                    nome_empresa,
                    nome_responsavel,

                    cpf_cnpj,
                    cpf_cnpj_normalizado,

                    telefone,
                    telefone_normalizado,

                    email,
                    usuario,
                    senha_hash,

                    segmento,
                    cidade,
                    estado,

                    observacoes_cliente,

                    aceitou_termos,
                    aceitou_whatsapp,
                    aceitou_termos_em,

                    ip_cadastro,
                    user_agent,

                    status
                )
                VALUES (
                    %s,

                    %s,
                    %s,

                    %s,
                    %s,

                    %s,
                    %s,

                    %s,
                    %s,
                    %s,

                    %s,
                    %s,
                    %s,

                    %s,

                    TRUE,
                    %s,
                    CURRENT_TIMESTAMP,

                    %s,
                    %s,

                    'aguardando'
                )
                RETURNING
                    id,
                    status,
                    criada_em
                """,
                (
                    convite["id"],

                    nome_empresa,
                    nome_responsavel,

                    cpf_cnpj or None,
                    cpf_cnpj_normalizado or None,

                    telefone,
                    telefone_normalizado,

                    email,
                    usuario,
                    senha_hash,

                    segmento,
                    cidade,
                    estado,

                    observacoes_cliente,

                    bool(
                        aceitou_whatsapp
                    ),

                    endereco_ip,
                    user_agent,
                ),
            )

            solicitacao = cursor.fetchone()

            # ======================================
            # CONSUMIR CONVITE
            # ======================================

            cursor.execute(
                """
                UPDATE onboarding_convites

                SET
                    status = 'utilizado',
                    utilizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    convite["id"],
                ),
            )

            cls._registrar_auditoria(
                cursor,
                convite_id=convite["id"],
                solicitacao_id=solicitacao["id"],
                usuario_id=None,
                acao="solicitacao_criada",
                descricao=(
                    "Solicitação pública de empresa enviada."
                ),
                endereco_ip=endereco_ip,
                dados_novos={
                    "nome_empresa": nome_empresa,
                    "nome_responsavel": nome_responsavel,
                    "telefone": telefone_normalizado,
                    "email": email,
                    "usuario": usuario,
                    "segmento": segmento,
                    "cidade": cidade,
                    "estado": estado,
                    "aceitou_whatsapp": bool(
                        aceitou_whatsapp
                    ),
                    "status": "aguardando",
                },
            )

            conn.commit()

            return {
                "id": solicitacao["id"],
                "status": solicitacao["status"],
                "criada_em": solicitacao["criada_em"],
                "nome_empresa": nome_empresa,
                "nome_responsavel": nome_responsavel,
                "email": email,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

        # =====================================================
    # VALIDAR USUÁRIO MASTER
    # =====================================================

    @staticmethod
    def _validar_master(
        cursor,
        usuario_id,
    ):
        try:
            usuario_id = int(usuario_id)

        except (TypeError, ValueError) as erro:
            raise OnboardingEmpresaErro(
                "Administrador inválido."
            ) from erro

        cursor.execute(
            """
            SELECT
                id,
                usuario,
                nivel,
                status

            FROM usuarios

            WHERE id = %s
              AND nivel = 'master'

            LIMIT 1
            """,
            (usuario_id,),
        )

        administrador = cursor.fetchone()

        if not administrador:
            raise OnboardingEmpresaErro(
                "Somente um usuário master pode realizar esta operação."
            )

        if administrador.get("status") not in (None, "ativo"):
            raise OnboardingEmpresaErro(
                "O usuário master informado está inativo."
            )

        return administrador

    # =====================================================
    # LISTAR SOLICITAÇÕES
    # =====================================================

    @classmethod
    def listar_solicitacoes(
        cls,
        *,
        status=None,
        busca=None,
        limite=100,
    ):
        status = cls._texto(
            status,
            30,
        ).lower()

        busca = cls._texto(
            busca,
            180,
        )

        status_validos = {
            "",
            "aguardando",
            "em_analise",
            "aprovada",
            "rejeitada",
            "cancelada",
        }

        if status not in status_validos:
            raise OnboardingEmpresaErro(
                "Status de solicitação inválido."
            )

        try:
            limite = int(limite)

        except (TypeError, ValueError):
            limite = 100

        limite = max(
            1,
            min(limite, 500),
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.convite_id,

                    s.nome_empresa,
                    s.nome_responsavel,

                    s.cpf_cnpj,
                    s.telefone,
                    s.telefone_normalizado,
                    s.email,
                    s.usuario,

                    s.segmento,
                    s.cidade,
                    s.estado,

                    s.status,

                    s.plano_aprovado,
                    s.emprestimos_ativo,
                    s.dias_teste,

                    s.observacoes_cliente,
                    s.observacoes_admin,
                    s.motivo_rejeicao,

                    s.aceitou_termos,
                    s.aceitou_whatsapp,

                    s.analisada_por,
                    s.analisada_em,

                    s.empresa_criada_id,
                    s.usuario_criado_id,

                    s.criada_em,
                    s.atualizada_em,

                    c.nome_destinatario,
                    c.telefone_destinatario,
                    c.email_destinatario,

                    administrador.usuario
                        AS analisada_por_nome

                FROM onboarding_solicitacoes s

                INNER JOIN onboarding_convites c
                    ON c.id = s.convite_id

                LEFT JOIN usuarios administrador
                    ON administrador.id = s.analisada_por

                WHERE (
                    %s = ''
                    OR s.status = %s
                )

                AND (
                    %s = ''
                    OR s.nome_empresa ILIKE '%%' || %s || '%%'
                    OR s.nome_responsavel ILIKE '%%' || %s || '%%'
                    OR s.email ILIKE '%%' || %s || '%%'
                    OR s.telefone_normalizado ILIKE '%%' || %s || '%%'
                    OR s.usuario ILIKE '%%' || %s || '%%'
                    OR COALESCE(
                        s.cpf_cnpj_normalizado,
                        ''
                    ) ILIKE '%%' || %s || '%%'
                )

                ORDER BY
                    CASE
                        WHEN s.status = 'aguardando' THEN 1
                        WHEN s.status = 'em_analise' THEN 2
                        WHEN s.status = 'aprovada' THEN 3
                        WHEN s.status = 'rejeitada' THEN 4
                        ELSE 5
                    END,
                    s.criada_em DESC

                LIMIT %s
                """,
                (
                    status,
                    status,

                    busca,
                    busca,
                    busca,
                    busca,
                    busca,
                    busca,
                    busca,

                    limite,
                ),
            )

            return cursor.fetchall() or []

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # BUSCAR SOLICITAÇÃO
    # =====================================================

    @classmethod
    def buscar_solicitacao(
        cls,
        solicitacao_id,
    ):
        try:
            solicitacao_id = int(
                solicitacao_id
            )

        except (TypeError, ValueError) as erro:
            raise OnboardingEmpresaErro(
                "Solicitação inválida."
            ) from erro

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    s.*,

                    c.nome_destinatario,
                    c.telefone_destinatario,
                    c.email_destinatario,
                    c.criado_em AS convite_criado_em,

                    criador.usuario
                        AS convite_criado_por_nome,

                    administrador.usuario
                        AS analisada_por_nome,

                    e.nome AS empresa_criada_nome,
                    e.plano AS empresa_criada_plano,

                    gerente.usuario
                        AS usuario_criado_nome

                FROM onboarding_solicitacoes s

                INNER JOIN onboarding_convites c
                    ON c.id = s.convite_id

                LEFT JOIN usuarios criador
                    ON criador.id = c.criado_por

                LEFT JOIN usuarios administrador
                    ON administrador.id = s.analisada_por

                LEFT JOIN empresa e
                    ON e.id = s.empresa_criada_id

                LEFT JOIN usuarios gerente
                    ON gerente.id = s.usuario_criado_id

                WHERE s.id = %s

                LIMIT 1
                """,
                (solicitacao_id,),
            )

            solicitacao = cursor.fetchone()

            if not solicitacao:
                raise OnboardingEmpresaErro(
                    "Solicitação não encontrada."
                )

            return solicitacao

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # MARCAR COMO EM ANÁLISE
    # =====================================================

    @classmethod
    def marcar_em_analise(
        cls,
        *,
        solicitacao_id,
        usuario_id,
        endereco_ip=None,
    ):
        try:
            solicitacao_id = int(
                solicitacao_id
            )

        except (TypeError, ValueError) as erro:
            raise OnboardingEmpresaErro(
                "Solicitação inválida."
            ) from erro

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            administrador = cls._validar_master(
                cursor,
                usuario_id,
            )

            cursor.execute(
                """
                SELECT
                    id,
                    convite_id,
                    status

                FROM onboarding_solicitacoes

                WHERE id = %s

                LIMIT 1

                FOR UPDATE
                """,
                (solicitacao_id,),
            )

            solicitacao = cursor.fetchone()

            if not solicitacao:
                raise OnboardingEmpresaErro(
                    "Solicitação não encontrada."
                )

            if solicitacao["status"] == "em_analise":
                conn.commit()
                return False

            if solicitacao["status"] != "aguardando":
                raise OnboardingEmpresaErro(
                    "Esta solicitação não pode mais ser colocada em análise."
                )

            cursor.execute(
                """
                UPDATE onboarding_solicitacoes

                SET
                    status = 'em_analise',
                    analisada_por = %s,
                    analisada_em = CURRENT_TIMESTAMP,
                    atualizada_em = CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    administrador["id"],
                    solicitacao_id,
                ),
            )

            cls._registrar_auditoria(
                cursor,
                convite_id=solicitacao["convite_id"],
                solicitacao_id=solicitacao_id,
                usuario_id=administrador["id"],
                acao="solicitacao_em_analise",
                descricao=(
                    "Solicitação colocada em análise pelo administrador."
                ),
                endereco_ip=endereco_ip,
                dados_anteriores={
                    "status": solicitacao["status"],
                },
                dados_novos={
                    "status": "em_analise",
                },
            )

            conn.commit()

            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # APROVAR SOLICITAÇÃO
    # =====================================================

    @classmethod
    def aprovar_solicitacao(
        cls,
        *,
        solicitacao_id,
        usuario_id,
        plano,
        emprestimos_ativo=False,
        dias_teste=0,
        observacoes_admin=None,
        url_login=None,
        endereco_ip=None,
    ):
        try:
            solicitacao_id = int(
                solicitacao_id
            )

            dias_teste = int(
                dias_teste or 0
            )

        except (TypeError, ValueError) as erro:
            raise OnboardingEmpresaErro(
                "Dados da aprovação inválidos."
            ) from erro

        plano = cls._texto(
            plano,
            30,
        ).lower()

        observacoes_admin = cls._texto(
            observacoes_admin,
            2000,
        ) or None

        url_login = cls._texto(
            url_login,
            500,
        ) or None

        emprestimos_ativo = bool(
            emprestimos_ativo
        )

        if plano not in ("comum", "premium"):
            raise OnboardingEmpresaErro(
                "Selecione um plano válido."
            )

        if not 0 <= dias_teste <= 365:
            raise OnboardingEmpresaErro(
                "O período de teste deve ficar entre 0 e 365 dias."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            administrador = cls._validar_master(
                cursor,
                usuario_id,
            )

            cursor.execute(
                """
                SELECT
                    id,
                    convite_id,

                    nome_empresa,
                    nome_responsavel,

                    telefone,
                    telefone_normalizado,
                    email,

                    usuario,
                    senha_hash,

                    aceitou_whatsapp,

                    status,
                    empresa_criada_id,
                    usuario_criado_id

                FROM onboarding_solicitacoes

                WHERE id = %s

                LIMIT 1

                FOR UPDATE
                """,
                (solicitacao_id,),
            )

            solicitacao = cursor.fetchone()

            if not solicitacao:
                raise OnboardingEmpresaErro(
                    "Solicitação não encontrada."
                )

            if solicitacao["status"] == "aprovada":
                raise OnboardingEmpresaErro(
                    "Esta solicitação já foi aprovada."
                )

            if solicitacao["status"] in (
                "rejeitada",
                "cancelada",
            ):
                raise OnboardingEmpresaErro(
                    "Esta solicitação já foi encerrada."
                )

            if solicitacao["status"] not in (
                "aguardando",
                "em_analise",
            ):
                raise OnboardingEmpresaErro(
                    "Esta solicitação não pode ser aprovada."
                )

            if (
                solicitacao["empresa_criada_id"]
                or solicitacao["usuario_criado_id"]
            ):
                raise OnboardingEmpresaErro(
                    "Esta solicitação já possui uma conta vinculada."
                )

            cursor.execute(
                """
                SELECT id

                FROM usuarios

                WHERE LOWER(usuario) = LOWER(%s)

                LIMIT 1

                FOR UPDATE
                """,
                (solicitacao["usuario"],),
            )

            if cursor.fetchone():
                raise OnboardingEmpresaErro(
                    "O usuário solicitado já está sendo utilizado."
                )

            # ==========================================
            # CRIAR EMPRESA
            # ==========================================

            cursor.execute(
                """
                INSERT INTO empresa (
                    nome,
                    plano,
                    emprestimos_ativo
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    solicitacao["nome_empresa"],
                    plano,
                    emprestimos_ativo,
                ),
            )

            empresa = cursor.fetchone()
            empresa_id = empresa["id"]

            # ==========================================
            # CRIAR USUÁRIO GERENTE
            # ==========================================

            cursor.execute(
                """
                INSERT INTO usuarios (
                    usuario,
                    senha,
                    nivel,
                    empresa_id,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    'gerente',
                    %s,
                    'ativo'
                )
                RETURNING id
                """,
                (
                    solicitacao["usuario"],
                    solicitacao["senha_hash"],
                    empresa_id,
                ),
            )

            gerente = cursor.fetchone()
            gerente_id = gerente["id"]

            # ==========================================
            # FINALIZAR SOLICITAÇÃO
            # ==========================================

            cursor.execute(
                """
                UPDATE onboarding_solicitacoes

                SET
                    status = 'aprovada',

                    plano_aprovado = %s,
                    emprestimos_ativo = %s,
                    dias_teste = %s,

                    observacoes_admin = %s,
                    motivo_rejeicao = NULL,

                    analisada_por = %s,
                    analisada_em = CURRENT_TIMESTAMP,

                    empresa_criada_id = %s,
                    usuario_criado_id = %s,

                    atualizada_em = CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    plano,
                    emprestimos_ativo,
                    dias_teste,

                    observacoes_admin,

                    administrador["id"],

                    empresa_id,
                    gerente_id,

                    solicitacao_id,
                ),
            )

            # ==========================================
            # PREPARAR MENSAGEM DO WHATSAPP
            # ==========================================

            mensagem_whatsapp = None
            mensagem_id = None

            if solicitacao["aceitou_whatsapp"]:
                login_texto = (
                    f"\n\nAcesse: {url_login}"
                    if url_login
                    else ""
                )

                teste_texto = (
                    (
                        f"\nPeríodo de teste: "
                        f"{dias_teste} dia(s)"
                    )
                    if dias_teste > 0
                    else ""
                )

                modulo_texto = (
                    "\nMódulo de empréstimos: ativado"
                    if emprestimos_ativo
                    else ""
                )

                mensagem_whatsapp = (
                    f"Olá, {solicitacao['nome_responsavel']}! 👋\n\n"
                    f"O cadastro da empresa "
                    f"*{solicitacao['nome_empresa']}* "
                    f"foi aprovado no Nexus PDV.\n\n"
                    f"Plano: {plano.title()}\n"
                    f"Usuário: {solicitacao['usuario']}"
                    f"{teste_texto}"
                    f"{modulo_texto}\n\n"
                    f"Utilize a senha criada durante o cadastro."
                    f"{login_texto}\n\n"
                    f"Seja bem-vindo ao Nexus PDV! 🚀"
                )

                cursor.execute(
                    """
                    INSERT INTO whatsapp_mensagens (
                        solicitacao_id,
                        empresa_id,

                        telefone,
                        telefone_normalizado,

                        tipo,
                        mensagem,

                        status,
                        tentativas,
                        maximo_tentativas
                    )
                    VALUES (
                        %s,
                        %s,

                        %s,
                        %s,

                        'onboarding_aprovado',
                        %s,

                        'pendente',
                        0,
                        5
                    )
                    RETURNING id
                    """,
                    (
                        solicitacao_id,
                        empresa_id,

                        solicitacao["telefone"],
                        solicitacao["telefone_normalizado"],

                        mensagem_whatsapp,
                    ),
                )

                mensagem_id = cursor.fetchone()["id"]

            cls._registrar_auditoria(
                cursor,
                convite_id=solicitacao["convite_id"],
                solicitacao_id=solicitacao_id,
                usuario_id=administrador["id"],
                acao="solicitacao_aprovada",
                descricao=(
                    "Solicitação aprovada e conta da empresa criada."
                ),
                endereco_ip=endereco_ip,
                dados_anteriores={
                    "status": solicitacao["status"],
                },
                dados_novos={
                    "status": "aprovada",
                    "plano": plano,
                    "emprestimos_ativo": emprestimos_ativo,
                    "dias_teste": dias_teste,
                    "empresa_id": empresa_id,
                    "gerente_id": gerente_id,
                    "mensagem_whatsapp_id": mensagem_id,
                },
            )

            conn.commit()

            return {
                "solicitacao_id": solicitacao_id,
                "status": "aprovada",

                "empresa_id": empresa_id,
                "empresa_nome": solicitacao["nome_empresa"],

                "usuario_id": gerente_id,
                "usuario": solicitacao["usuario"],

                "plano": plano,
                "emprestimos_ativo": emprestimos_ativo,
                "dias_teste": dias_teste,

                "mensagem_whatsapp_id": mensagem_id,
                "mensagem_whatsapp": mensagem_whatsapp,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # REJEITAR SOLICITAÇÃO
    # =====================================================

    @classmethod
    def rejeitar_solicitacao(
        cls,
        *,
        solicitacao_id,
        usuario_id,
        motivo,
        observacoes_admin=None,
        endereco_ip=None,
    ):
        try:
            solicitacao_id = int(
                solicitacao_id
            )

        except (TypeError, ValueError) as erro:
            raise OnboardingEmpresaErro(
                "Solicitação inválida."
            ) from erro

        motivo = cls._texto(
            motivo,
            2000,
        )

        observacoes_admin = cls._texto(
            observacoes_admin,
            2000,
        ) or None

        if len(motivo) < 5:
            raise OnboardingEmpresaErro(
                "Informe o motivo da rejeição."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            administrador = cls._validar_master(
                cursor,
                usuario_id,
            )

            cursor.execute(
                """
                SELECT
                    id,
                    convite_id,
                    nome_empresa,
                    nome_responsavel,
                    telefone,
                    telefone_normalizado,
                    aceitou_whatsapp,
                    status,
                    empresa_criada_id,
                    usuario_criado_id

                FROM onboarding_solicitacoes

                WHERE id = %s

                LIMIT 1

                FOR UPDATE
                """,
                (solicitacao_id,),
            )

            solicitacao = cursor.fetchone()

            if not solicitacao:
                raise OnboardingEmpresaErro(
                    "Solicitação não encontrada."
                )

            if solicitacao["status"] == "rejeitada":
                raise OnboardingEmpresaErro(
                    "Esta solicitação já foi rejeitada."
                )

            if solicitacao["status"] == "aprovada":
                raise OnboardingEmpresaErro(
                    "Uma solicitação aprovada não pode ser rejeitada."
                )

            if solicitacao["status"] == "cancelada":
                raise OnboardingEmpresaErro(
                    "Esta solicitação foi cancelada."
                )

            if (
                solicitacao["empresa_criada_id"]
                or solicitacao["usuario_criado_id"]
            ):
                raise OnboardingEmpresaErro(
                    "Esta solicitação já possui uma conta criada."
                )

            cursor.execute(
                """
                UPDATE onboarding_solicitacoes

                SET
                    status = 'rejeitada',
                    motivo_rejeicao = %s,
                    observacoes_admin = %s,

                    analisada_por = %s,
                    analisada_em = CURRENT_TIMESTAMP,

                    atualizada_em = CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    motivo,
                    observacoes_admin,
                    administrador["id"],
                    solicitacao_id,
                ),
            )

            mensagem_id = None

            if solicitacao["aceitou_whatsapp"]:
                mensagem = (
                    f"Olá, {solicitacao['nome_responsavel']}.\n\n"
                    f"A solicitação de cadastro da empresa "
                    f"*{solicitacao['nome_empresa']}* "
                    f"foi analisada pelo Nexus PDV.\n\n"
                    f"Resultado: não aprovada.\n"
                    f"Motivo: {motivo}\n\n"
                    f"Entre em contato com nossa equipe "
                    f"caso precise de mais informações."
                )

                cursor.execute(
                    """
                    INSERT INTO whatsapp_mensagens (
                        solicitacao_id,

                        telefone,
                        telefone_normalizado,

                        tipo,
                        mensagem,

                        status,
                        tentativas,
                        maximo_tentativas
                    )
                    VALUES (
                        %s,

                        %s,
                        %s,

                        'onboarding_rejeitado',
                        %s,

                        'pendente',
                        0,
                        5
                    )
                    RETURNING id
                    """,
                    (
                        solicitacao_id,

                        solicitacao["telefone"],
                        solicitacao["telefone_normalizado"],

                        mensagem,
                    ),
                )

                mensagem_id = cursor.fetchone()["id"]

            cls._registrar_auditoria(
                cursor,
                convite_id=solicitacao["convite_id"],
                solicitacao_id=solicitacao_id,
                usuario_id=administrador["id"],
                acao="solicitacao_rejeitada",
                descricao=(
                    "Solicitação de empresa rejeitada pelo administrador."
                ),
                endereco_ip=endereco_ip,
                dados_anteriores={
                    "status": solicitacao["status"],
                },
                dados_novos={
                    "status": "rejeitada",
                    "motivo": motivo,
                    "mensagem_whatsapp_id": mensagem_id,
                },
            )

            conn.commit()

            return {
                "solicitacao_id": solicitacao_id,
                "status": "rejeitada",
                "motivo": motivo,
                "mensagem_whatsapp_id": mensagem_id,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()


    # =====================================================
    # LISTAR CONVITES
    # =====================================================

    @classmethod
    def listar_convites(
        cls,
        *,
        limite=100,
    ):
        try:
            limite = int(
                limite
            )

        except (
            TypeError,
            ValueError,
        ):
            limite = 100

        limite = max(
            1,
            min(
                limite,
                500,
            ),
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE onboarding_convites

                SET status = 'expirado'

                WHERE status = 'ativo'
                  AND expira_em <= CURRENT_TIMESTAMP
                """
            )

            cursor.execute(
                """
                SELECT
                    c.id,
                    c.status,
                    c.nome_destinatario,
                    c.telefone_destinatario,
                    c.email_destinatario,
                    c.expira_em,
                    c.utilizado_em,
                    c.revogado_em,
                    c.criado_em,

                    u.usuario AS criado_por_nome,

                    s.id AS solicitacao_id,
                    s.status AS solicitacao_status,
                    s.nome_empresa,
                    s.nome_responsavel

                FROM onboarding_convites c

                LEFT JOIN usuarios u
                    ON u.id = c.criado_por

                LEFT JOIN onboarding_solicitacoes s
                    ON s.convite_id = c.id

                ORDER BY c.criado_em DESC

                LIMIT %s
                """,
                (
                    limite,
                ),
            )

            convites = (
                cursor.fetchall()
                or []
            )

            conn.commit()

            return convites

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # REVOGAR CONVITE
    # =====================================================

    @classmethod
    def revogar_convite(
        cls,
        *,
        convite_id,
        usuario_id,
        endereco_ip=None,
    ):
        try:
            convite_id = int(
                convite_id
            )

            usuario_id = int(
                usuario_id
            )

        except (
            TypeError,
            ValueError,
        ) as erro:
            raise OnboardingEmpresaErro(
                "Convite ou administrador inválido."
            ) from erro

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT id

                FROM usuarios

                WHERE id = %s
                  AND nivel = 'master'

                LIMIT 1
                """,
                (
                    usuario_id,
                ),
            )

            if not cursor.fetchone():
                raise OnboardingEmpresaErro(
                    (
                        "Somente um usuário master "
                        "pode revogar convites."
                    )
                )

            cursor.execute(
                """
                SELECT
                    id,
                    status

                FROM onboarding_convites

                WHERE id = %s

                LIMIT 1

                FOR UPDATE
                """,
                (
                    convite_id,
                ),
            )

            convite = cursor.fetchone()

            if not convite:
                raise OnboardingEmpresaErro(
                    "Convite não encontrado."
                )

            if convite["status"] == "utilizado":
                raise OnboardingEmpresaErro(
                    (
                        "Não é possível revogar um "
                        "convite já utilizado."
                    )
                )

            if convite["status"] == "revogado":
                return False

            cursor.execute(
                """
                UPDATE onboarding_convites

                SET
                    status = 'revogado',
                    revogado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    convite_id,
                ),
            )

            cls._registrar_auditoria(
                cursor,
                convite_id=convite_id,
                usuario_id=usuario_id,
                acao="convite_revogado",
                descricao=(
                    "Convite revogado pelo administrador."
                ),
                endereco_ip=endereco_ip,
                dados_anteriores={
                    "status": convite["status"],
                },
                dados_novos={
                    "status": "revogado",
                },
            )

            conn.commit()

            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()