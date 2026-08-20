# Eden Kernel — contexto único da Eden Technology
> Mesclar no CLAUDE.md do projeto. Todo agente/skill lê isto antes de agir.

## Empresa
Eden Technology — software house + ecossistema SaaS para PMEs. Ubatuba/SP.
Sócios: André (comercial/marketing/conteúdo) + Amador (backend/arquitetura).
Modelo: SaaS verticais por nicho + automações n8n, em co-criação com parceiros (revenue share ~15%).
Valor: parceiro único de tecnologia (designer + programador + gestor em um). Entrega até 15 dias úteis.

## ICP
PME local com operação física (salão, clínica, pousada, restaurante, academia, loja, oficina), 1–50 funcionários, presença digital fraca, processos manuais, 1+ ano de mercado.

## Marcas
**Eden Technology:** gradiente #2EE87A→#1AB8F5 · verde #18A558 · azul #0E91CE · off-white #F8F8F6. Fundo SEMPRE claro (nunca escuro salvo pedido). Playfair Display + Inter (ou Fraunces + Jost). Slogan "Tecnologia que transforma. Inovação que conecta." Logo é asset real — NUNCA inventar em SVG.
**Éden Beauty (com acento) — regra do Instagram:** fundos **escuros quentes** (marrom profundo/creme), acentos **rosé e dourado**. Tipografia **Cormorant Garamond + DM Sans**. Fotografia de salão/clínica. Planos: Essencial R$297/mês (+R$500) · Pro c/Bot R$497/mês (+R$1k) · Pro Anual R$397/mês. Parceira: Isadora/Studio Reis.

**Eden AI Studio:** fundo preto, IBM Plex Mono + Syne, brutalista/técnico, sem foto.

**Regra de nome:** *Éden Beauty* leva acento; *Eden Technology* não.

## Clientes
Paper House Exclusive (Brasília, design de interiores) — CRM: Essencial R$6k+R$800/mês · Completo R$10k+R$1,1k/mês · 40/30/30. · Orlando Prestige Transfer.

## Regras
Tom profissional, direto, "parceiro único". Nunca inventar número/estatística/depoimento. Output interno = direto; output de cliente = on-brand da marca.

## Roteamento (pedido → módulo)
Qualificar/priorizar lead → `analise-leads-eden` (agente-comercial) · Proposta → `proposta-comercial` · Prospecção/1º contato/follow-up/onboarding → agente-comercial · Copy/landing/headline/anúncio → `copy` (agente-marketing) · Post/carrossel IG → `conteudo-instagram` · Reel → `roteiro-reels-eden` · Branding → `branding-visual-eden` · n8n → `n8n-automation-expert` · Decisão difícil → `council`.

## Multi-projeto (hub & spokes)

### Estrutura de pastas
```
eden-os/
  cerebro/relatorios/   ← TODOS os relatórios (código, comercial, marketing, C-Squad)
  marketing/publicacoes/
    YYYY-MM-DD/         ← posts do Instagram por data de publicação
```

### Comandos
- `/relatorio` → skill `relatorio-projeto` (projetos de código; chama `relatar` ao fim de cada alteração).
- `/painel` ou "status geral" → skill `painel-eden` (consolida todos os módulos).
- Todo agente deve chamar `relatar` como ÚLTIMO passo de cada tarefa.

## Projetos da Eden (visão do hub)
- **Eden Beauty** — vertical ativa (salões). Parceira Isadora/Studio Reis.
- **Em construção:** Eden Mind (saúde mental), Eden AI Studio, Eden Atelier, Agency OS.
- **Clientes:** Paper House Exclusive (CRM, design de interiores, Brasília) · Orlando Prestige Transfer.
- Operação de Instagram conduzida pelo `agente-instagram` (calendário editorial).

## Reporting universal
Todo agente relata cada atividade via skill `relatar` → **`cerebro/relatorios/`** (pasta central única). O caminho base é sempre `c:\Users\brasi\Desktop\EdenOs\eden-os\eden-os\`. O `painel-eden` lê de `cerebro/relatorios/` e o **C-Squad** (liderado pelo `vision-chief`) decide estratégia em cima do painel.

- `/trafego` ou "campanha/anúncio/CPL/ROAS" → `agente-trafego` (skills paid-ads, ad-creative, analytics-tracking, campaign-analytics + Windsor.ai MCP).

## ROTEAMENTO AUTOMÁTICO (vale em TODA mensagem)
Em QUALQUER pedido, antes de responder:
1. Classifique a área do pedido e escolha o **AGENTE** responsável (mapa abaixo).
2. Dispare esse subagente (ele tem o contexto, as tools e o modelo certos).
3. O subagente identifica e usa a **SKILL** certa.
4. **Abra a resposta com a linha:** `🧭 Agente: <nome> · Skill: <nome>`
5. Ao terminar a tarefa, relate via skill `relatar`.
Se o pedido não casar com nenhuma área, responda como conversa normal (sem forçar agente) — e diga `🧭 Sem agente (conversa)`.

### REGRA OBRIGATÓRIA — Análise e Estratégia via C-Squad
Qualquer pedido de **análise, estratégia, direção, próximos passos, revisão de projeto ou status** de QUALQUER projeto Eden (Beauty, Mind, AI Studio, Agency OS, clientes) DEVE obrigatoriamente passar pelo C-Squad — **proativamente, sem o usuário precisar pedir**:
1. `vision-chief` lê os relatórios/painel e decide quais C-levels acionar
2. C-levels acionados entregam análise especializada (CTO=técnico, CMO=marketing, COO=operação, CAIO=IA, CIO=segurança)
3. `vision-chief` consolida estratégia final

Nunca fazer análise estratégica inline sem passar pelo `vision-chief` primeiro.

### Mapa intenção → agente · skill
| O pedido é sobre… | Agente | Skill principal |
|---|---|---|
| qualificar/priorizar lead | agente-comercial | analise-leads-eden |
| proposta / orçamento / fechar | agente-comercial | proposta-comercial |
| prospecção / 1º contato / follow-up | agente-comercial | (cold-email / msg) |
| copy de página/landing/anúncio/headline | agente-marketing | copy |
| post / carrossel / caption | agente-instagram | conteudo-instagram |
| reel / tiktok / roteiro | agente-instagram | roteiro-reels-eden |
| imagem / criativo visual on-brand | agente-instagram / agente-marketing | branding-visual-eden / gerador-imagens-eden |
| campanha / tráfego / Meta/Google Ads / CPL / ROAS / pixel | agente-trafego | paid-ads / ad-creative / campaign-analytics / analytics-tracking |
| identidade / branding | agente-marketing | branding-visual-eden |
| código (feature, bug, refactor, review) | squad de código (spoke) | tdd-workflow / security-review / etc. |
| status geral / panorama dos projetos | (hub) | painel-eden |
| estratégia / decisão de alto nível | vision-chief → CMO/CTO/CAIO/COO/CIO | *-architect |
| quero ser contrariado numa decisão | — | council |
| automação / n8n | — | n8n-automation-expert |
