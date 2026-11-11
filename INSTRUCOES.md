# Fidelidade v1 — instalação e uso

O módulo está integrado ao projeto. Os arquivos principais estão em `routes/fidelidade.py`, `services/fidelidade_service.py`, `migrations/020_fidelidade.sql` e `templates/fidelidade_*.html`.

A integração automática cria um check-in depois da venda confirmada, desde que a venda esteja associada a um cliente cadastrado. O cancelamento invalida o check-in quando todas as linhas daquele grupo de venda forem canceladas.

## Aplicar a migração

A migração ainda não foi executada. Faça um backup do PostgreSQL e, na raiz do projeto, com o ambiente Python configurado, execute:

```powershell
python executar_fidelidade.py
```

Depois inicie/reinicie o sistema, entre com um usuário gerente e abra **Fidelidade** no menu para criar a campanha. O prazo começa na criação; o link público mostra as regras, e os dados de clientes ficam só no painel interno.

## Identificação e operação

Use o cadastro existente no módulo Clientes. Na tela de venda, a equipe deve selecionar o cliente antes de finalizar; o relacionamento usa o ID do cadastro, não o nome digitado. Vendas sem cliente vinculado não dão check-in. Cada venda (`venda_grupo`) vale um check-in, mesmo quando contém vários produtos.

O painel do gerente lista prêmios disponíveis e permite marcá-los como resgatados. Se uma compra cancelada afetar um prêmio já resgatado, o status fica como `revisar_cancelamento` para decisão manual.
