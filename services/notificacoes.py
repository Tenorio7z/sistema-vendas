from database import conectar
from datetime import datetime


def notificar_gerente(funcionario, produto, valor, empresa_id):

    conn = conectar()
    cursor = conn.cursor()

    print("SALVANDO NOTIFICAÇÃO")
    print("FUNCIONARIO:", funcionario)
    print("PRODUTO:", produto)
    print("VALOR:", valor)
    print("EMPRESA:", empresa_id)

    cursor.execute(
        """
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
        """,
        (

            empresa_id,
            funcionario,
            produto,
            valor,
            "Nova Venda",
            f"{funcionario} vendeu {produto} por R$ {valor:.2f}",
            str(datetime.now()),
            0

        )
    )

    conn.commit()

    print("NOTIFICAÇÃO GRAVADA")

    conn.close()
