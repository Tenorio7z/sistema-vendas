from database import conectar
from datetime import datetime


def notificar_gerente(usuario_id, produto, valor, empresa_id):

    conn = conectar()
    cursor = conn.cursor()

    # Buscar o nome do funcionário
    cursor.execute("""
        SELECT usuario
        FROM usuarios
        WHERE id = %s
        AND empresa_id = %s
    """, (usuario_id, empresa_id))

    resultado = cursor.fetchone()

    if resultado:
        funcionario = resultado[0]
    else:
        funcionario = "Funcionário"

    cursor.execute("""
        INSERT INTO notificacoes (

            empresa_id,
            funcionario,
            valor,
            titulo,
            mensagem,
            data,
            lida,
            produto

        )

        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (

        empresa_id,
        funcionario,
        valor,
        "Nova Venda",
        f"{funcionario} realizou uma venda de R$ {valor:.2f}",
        datetime.now(),
        0,
        produto

    ))

    conn.commit()
    conn.close()