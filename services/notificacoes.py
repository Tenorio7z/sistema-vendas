from database import conectar
from datetime import datetime


def notificar_gerente(usuario_id, produto, valor, empresa_id):

    conn = conectar()
    cursor = conn.cursor()

    print("SALVANDO NOTIFICAÇÃO")
    print("FUNCIONARIO:", usuario_id)
    print("PRODUTO:", produto)
    print("VALOR:", valor)
    print("EMPRESA:", empresa_id)

    cursor.execute(
        """
        INSERT INTO notificacoes (

            empresa_id,
            usuario_id,
            produto,
            valor,
            titulo,
            mensagem,
            data,
            lida

        )

        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (

            empresa_id,
            usuario_id,
            produto,
            valor,
            "Nova Venda",
            f"{usuario_id} vendeu {produto} por R$ {valor:.2f}",
            str(datetime.now()),
            0

        )
    )

    conn.commit()

    print("NOTIFICAÇÃO GRAVADA")

    conn.close()
