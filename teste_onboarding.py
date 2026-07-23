from database import conectar, criar_cursor

from services.onboarding_empresa_service import (
    OnboardingEmpresaService,
)


def buscar_master():
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT
                id,
                usuario

            FROM usuarios

            WHERE nivel = 'master'

            ORDER BY id

            LIMIT 1
            """
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


def executar():
    master = buscar_master()

    if not master:
        raise RuntimeError(
            "Nenhum usuário master foi encontrado."
        )

    print(
        "Master utilizado:",
        master["usuario"],
        "- ID:",
        master["id"],
    )

    convite = (
        OnboardingEmpresaService.criar_convite(
            criado_por=master["id"],
            url_base="http://127.0.0.1:5000",
            validade_horas=72,
            nome_destinatario="Cliente Teste",
            telefone_destinatario="11999999999",
            email_destinatario="cliente@teste.com",
            endereco_ip="127.0.0.1",
        )
    )

    print()
    print("Convite criado:")
    print("ID:", convite["id"])
    print("Status:", convite["status"])
    print("Expira em:", convite["expira_em"])
    print("Link:", convite["link"])

    validado = (
        OnboardingEmpresaService.validar_convite(
            convite["token"]
        )
    )

    print()
    print("Validação concluída:")
    print("Convite:", validado["id"])
    print("Destinatário:", validado["nome_destinatario"])


if __name__ == "__main__":
    executar()