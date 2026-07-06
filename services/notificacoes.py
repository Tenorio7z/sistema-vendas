from database import conectar
from datetime import datetime


def notificar_gerente(usuario_id, produto, valor, empresa_id):

    conn = conectar()
    cursor = conn.cursor()

    # Buscar nome do funcionário
    cursor.execute("""
        SELECT usuario
        FROM usuarios
        WHERE id = %s
        AND empresa_id = %s
    """, (usuario_id, empresa_id))

    usuario = cursor.fetchone()

    if usuario:
        funcionario = usuario[0]
    else:
        funcionario = "Funcionário"

    cursor.execute("""
        INSERT INTO notificacoes (
            empresa_id,
            funcionario,
            produto,
            valor,
            titulo,
            mensagem,
            data,
            lida
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (

        empresa_id,
        funcionario,
        produto,
        valor,
        "Nova Venda",
        f"{funcionario} vendeu {produto} por R$ {valor:.2f}",
        datetime.now(),
        False

    ))

    conn.commit()
    conn.close()