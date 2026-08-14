from database import conectar, criar_cursor

from services.fornecedores_service import (
    FornecedoresService,
)


def buscar_empresa():
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT
                id,
                nome

            FROM empresa

            ORDER BY id

            LIMIT 1
            """
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


def executar():
    empresa = buscar_empresa()

    if not empresa:
        raise RuntimeError(
            "Nenhuma empresa encontrada para o teste."
        )

    print(
        "Empresa usada:",
        empresa["nome"],
        "- ID:",
        empresa["id"],
    )

    fornecedor = FornecedoresService.criar(
        empresa_id=empresa["id"],
        dados={
            "nome": "Fornecedor Teste Nexus",
            "nome_fantasia": "Distribuidora Nexus",
            "cpf_cnpj": None,
            "telefone": "11999998888",
            "whatsapp": "11999998888",
            "email": "fornecedor@nexus.com",
            "cidade": "São Paulo",
            "estado": "SP",
            "contato_responsavel": "Contato Teste",
            "observacoes": (
                "Fornecedor criado para validar o módulo."
            ),
        },
    )

    print()
    print("Fornecedor criado:")
    print("ID:", fornecedor["id"])
    print("Nome:", fornecedor["nome"])
    print("Status:", fornecedor["ativo"])

    fornecedores = FornecedoresService.listar(
        empresa_id=empresa["id"],
        status="todos",
    )

    print()
    print(
        "Fornecedores encontrados:",
        len(fornecedores),
    )

    resumo = FornecedoresService.resumo(
        empresa["id"]
    )

    print()
    print("Resumo:", dict(resumo))


if __name__ == "__main__":
    executar()