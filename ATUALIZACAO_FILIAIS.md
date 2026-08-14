# Nexus PDV - Filiais e estoque independente

## Instalação

1. Faça backup do banco PostgreSQL.
2. No diretório do projeto, execute uma única vez:

   `python executar_filiais.py`

3. Depois inicie normalmente:

   `python app.py`

No Render, execute `python executar_filiais.py` no Shell antes do primeiro deploy desta versão.

## Funcionamento

- Cada empresa recebe automaticamente uma filial **Matriz**.
- O gerente administra filiais em **Filiais** no menu lateral.
- O catálogo (nome, preço, código e imagem) continua compartilhado pela empresa.
- Cada filial possui seu próprio estoque em `produto_filial`.
- O gerente alterna a filial na página Produtos.
- Funcionários enxergam somente o estoque da filial vinculada ao seu usuário.
- Novas filiais podem copiar o catálogo da matriz com estoque zerado.
- Vendas e caixas recebem `filial_id`, garantindo baixa e estorno no estoque correto.
- A filial de um funcionário pode ser escolhida no cadastro ou alterada no card da equipe.

## Dashboard da equipe

Foram adicionados indicadores de produtos cadastrados, total vendido, comissão esperada e folha pendente. O painel individual também informa produtos disponíveis na filial e o total esperado (salário-base + comissão).

## Observação de segurança

Não publique esta versão antes de executar a migração. As rotas de login passam a consultar a coluna `filial_id` e a tabela `filiais`.
