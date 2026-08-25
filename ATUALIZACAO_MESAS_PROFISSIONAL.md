# Atualização — Mesas e pré-conta profissional

## O que foi adicionado

- Visualização completa da comanda diretamente no painel de mesas.
- Lista de itens com quantidade, valor unitário, subtotal e observações.
- Botão **Imprimir conta** na mesa e na página detalhada da comanda.
- Pré-conta térmica em PDF sem fechar a mesa, registrar pagamento ou alterar estoque.
- Configuração da largura da bobina em **48 mm, 58 mm ou 80 mm** dentro do sistema.
- Configuração isolada por empresa.

## Instalação

Execute uma vez, na pasta do sistema:

```powershell
python executar_otimizacao_mesas.py
```

Depois, reinicie o servidor Flask normalmente.

> O serviço também cria a estrutura automaticamente no primeiro acesso, mas a
> execução explícita da migração é recomendada em produção.

## Otimizações incluídas

- O painel inteiro de mesas passou de várias consultas separadas para uma
  consulta consolidada.
- A agregação de itens considera apenas comandas abertas, sem varrer o
  histórico completo.
- Os clientes são carregados apenas quando o usuário abre ou fecha uma comanda.
- A busca de produtos é feita no servidor, com limite de 60 resultados por
  consulta, evitando enviar milhares de produtos ao navegador.
- A configuração da bobina fica em cache por cinco minutos e deixa de executar
  DDL repetidamente.
- Índices específicos foram adicionados para mesas, comandas e itens ativos.
- No pagamento em dinheiro, o operador informa o valor entregue pelo cliente e
  o troco é calculado imediatamente sobre o total após desconto.
- O servidor bloqueia pagamentos em dinheiro insuficientes, mesmo que a
  validação do navegador seja contornada.
- Valor recebido e troco ficam registrados na comanda e aparecem no cupom final.

## Fluxo de uso

1. Abra **Mesas**.
2. Clique em **Impressão** e selecione a largura da bobina.
3. Em uma mesa ocupada, clique em **Ver comanda**.
4. Confira todos os itens e clique em **Imprimir conta**.
5. A impressão abre um PDF no tamanho real configurado.
6. Somente **Fechar mesa** registra o pagamento, baixa estoque e libera a mesa.

## Arquivos da atualização

- `routes/mesas.py`
- `services/comanda_impressao_service.py`
- `templates/mesas.html`
- `templates/comanda.html`
- `static/css/mesas.css`
- `static/css/comanda.css`
- `migrations/014_configuracao_impressao.sql`
- `executar_configuracao_impressao.py`
- `migrations/015_otimizacao_mesas.sql`
- `migrations/016_troco_comandas.sql`
- `executar_otimizacao_mesas.py`
