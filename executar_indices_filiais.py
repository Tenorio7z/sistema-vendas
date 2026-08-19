from database import conectar


SQL = """
CREATE INDEX IF NOT EXISTS
idx_vendas_filial_usuario_periodo
ON vendas (
    filial_id,
    usuario_id,
    cancelada,
    data_venda DESC
);

CREATE INDEX IF NOT EXISTS
idx_vendas_empresa_filial_periodo
ON vendas (
    empresa_id,
    filial_id,
    cancelada,
    data_venda DESC
);

CREATE INDEX IF NOT EXISTS
idx_caixa_empresa_filial_status
ON caixa (
    empresa_id,
    filial_id,
    status,
    id DESC
);

CREATE INDEX IF NOT EXISTS
idx_notificacoes_empresa_ultimo
ON notificacoes (
    empresa_id,
    id DESC
);

CREATE INDEX IF NOT EXISTS
idx_usuarios_empresa_filial
ON usuarios (
    empresa_id,
    filial_id,
    nivel
);

CREATE INDEX IF NOT EXISTS
idx_produto_filial_consulta
ON produto_filial (
    filial_id,
    ativo,
    produto_id
);
"""


def executar():
    conn = conectar()
    cursor = conn.cursor()

    try:
        print("Criando índices de desempenho...")

        cursor.execute(SQL)
        conn.commit()

        print("Índices criados com sucesso.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()