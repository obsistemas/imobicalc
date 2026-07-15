# Padrões de Interface — Proptech Avaliador

Adaptado do blueprint genérico. Este produto tem, no MVP, **um único arquétipo de perfil** (o corretor/gestor da imobiliária, com dois papéis de RBAC: `admin` e `corretor`), usado de forma híbrida desktop+mobile. Os demais arquétipos do blueprint (operador de campo, operador de balcão, cliente sem cadastro, consumidor web, kiosk/TV) **não se aplicam** a este produto por ora — não há operação de campo intensiva, ponto de venda físico, cliente final com acesso próprio, nem painel público.

## 1. Arquétipo de perfil deste produto

| Perfil | Características da interface |
|---|---|
| **Gestor/Corretor** (papéis `admin` e `corretor`) | Desktop-first responsivo (menu lateral colapsável + cabeçalho fixo, densidade de informação alta, tabelas com filtros/busca, dashboards), **mas totalmente utilizável no celular** — o corretor cadastra imóvel e tira fotos direto na visita, sem fluxo mobile dedicado separado (mesmo bundle, layout responsivo). `admin` vê todos os imóveis/leads/dashboards do tenant; `corretor` vê e gerencia apenas a própria carteira. |

Um único bundle Vite (`frontend/apps/corretor`) cobre esse perfil no MVP. Novos bundles só entram se surgir um perfil realmente distinto (ex.: portal público de acompanhamento para o proprietário do imóvel, cogitado para fase futura).

## 2. Estrutura de navegação

**Desktop:** menu lateral por módulo (Imóveis, Avaliação, Leads, Dashboard) colapsável + cabeçalho fixo com breadcrumb, busca global, indicador de plano/limite de uso, notificações (via WebSocket), avatar.

**Mobile (mesmo bundle, responsivo):** tab bar fixa no rodapé, 5 posições, ação principal em destaque no botão central:
`[Início] [Imóveis] [+ CADASTRAR/AVALIAR] [Leads] [Dashboard/Perfil]`

**Regra de ouro:** estado que afeta o trabalho do corretor (ex.: limite do plano atingido, lead novo chegando) fica permanentemente visível, nunca escondido em menu.

## 3. Design system

- Pacote único `packages/ui` compartilhado (mesmo com um bundle só no MVP, já nasce separado para reuso futuro): componentes, tokens (cores, tipografia, espaçamento, raios), ícones, padrões de formulário/tabela/modal.
- **Theming por tenant via CSS variables**: branding do tenant (logo, cor primária) carregado da API — usado no MVP para personalizar o painel do corretor; branding em canais públicos fica para quando existir portal de acompanhamento do proprietário.
- Modo escuro disponível (uso prolongado em escritório/campo).
- Acessibilidade AA: contraste, alvos de toque ≥ 44px, fontes escaláveis, foco visível.

## 4. Padrões de interação aplicáveis a este produto

1. **Cadastro progressivo:** formulário de imóvel em seções (Localização → Características → Valores → Documentação), campos essenciais primeiro, autocomplete de CEP com "+ criar novo" quando o bairro não existe na base de preços.
2. **Fila de trabalho:** pipeline de leads com estados por cor (novo→contatado→visita→proposta→fechado/perdido), avançar estado com um toque/clique.
3. **Sistema sugere, humano decide:** a sugestão de preço de anúncio (3 perfis de urgência) é sempre uma recomendação — o corretor define o valor final publicado; nenhuma alteração de preço é aplicada automaticamente a um anúncio.
4. **Notificação em tempo real:** novo lead e atualização de métricas do dashboard chegam via WebSocket sem precisar de F5, com toast discreto (não bloqueia a tela).
5. **De-para memorizado:** ao importar/mapear dado externo (ex.: origem de lead vinda de um portal), o sistema lembra o mapeamento para próximas entradas.
6. **Import/export CSV** em cadastros volumosos (imóveis, leads); inativação lógica em vez de exclusão física onde há histórico associado (ex.: imóvel com avaliações).

## 5. Feedback e estado

- Toda ação assíncrona: estado otimista + confirmação/erro discretos (toast) — bloqueio de tela só quando inevitável (ex.: cálculo de avaliação).
- Erros de negócio: mensagem acionável ("Limite de imóveis do plano atingido — fazer upgrade") em vez de código técnico.
- Processos com resultado calculado (avaliação): sempre mostrar a faixa de confiança e as observações técnicas, nunca só o número final.

## 6. Dashboards

- Primeiro nível: cartões de estado acionáveis (ex.: "3 leads sem contato há mais de 3 dias" com link direto).
- Números do dia com comparativo; gráficos apenas onde há decisão a tomar (vendas/mês, leads/origem); drill-down até o registro de origem.
