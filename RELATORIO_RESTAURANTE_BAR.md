# Nexus PDV — atualização restaurante/bar

## Validações realizadas

- 72 arquivos Python compilados sem erro.
- 33 templates Jinja analisados sem erro.
- JavaScript externo validado com `node --check`.
- Aplicação importada e mapa de 101 endpoints carregado.
- Endpoints novos confirmados:
  - `/producao/cozinha`
  - `/producao/bar`
  - `/producao/<setor>/itens/<item_id>/status`
  - `/comandas/<comanda_id>/finalizar`

## Fluxo implementado

1. O garçom abre a mesa e adiciona produtos à comanda.
2. Ao enviar a rodada, os itens são separados entre cozinha, bar e entrega direta.
3. Cozinha e bar recebem os pedidos em tempo real via Socket.IO.
4. A produção muda cada item de pendente para preparando e pronto.
5. Itens de entrega direta ficam prontos automaticamente.
6. O botão de recebimento somente é liberado quando:
   - a comanda possui itens;
   - todos os itens foram enviados;
   - nenhum item está pendente ou em preparo.
7. No recebimento, o sistema:
   - bloqueia comanda, caixa e produtos contra concorrência;
   - impede pagamento duplicado;
   - valida cliente, estoque, pagamento e desconto;
   - distribui o desconto entre os itens;
   - registra as linhas na tabela `vendas`;
   - usa o garçom responsável como `usuario_id` da venda;
   - atualiza estoque e saldo do caixa;
   - fecha pedidos e itens;
   - fecha a comanda;
   - libera a mesa;
   - registra auditoria;
   - gera cupom e notificação depois do commit.

## Arquivos criados

- `templates/producao.html`
- `static/css/producao.css`
- `RELATORIO_RESTAURANTE_BAR.md`

## Arquivos alterados nesta atualização

- `services/mesas_service.py`
- `routes/mesas.py`
- `routes/produtos.py`
- `templates/mesas.html`
- `templates/produtos.html`
- `templates/editar_produto.html`
- `static/css/mesas.css`

## Observação sobre o teste com PostgreSQL

O ambiente do Codex bloqueou a conexão de saída para o PostgreSQL do Render.
Por isso, a validação realizada aqui foi estática, estrutural e de carregamento
da aplicação. Antes do deploy, execute localmente:

1. `python executar_modulo_mesas.py`
2. `python executar_fluxo_garcom.py`
3. `python app.py`

Depois teste uma comanda com um produto de cada setor.
