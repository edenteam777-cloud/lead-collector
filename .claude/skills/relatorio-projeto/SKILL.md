---
name: relatorio-projeto
description: Gera um relatório estruturado de alterações de um projeto de código e salva em projeto-codigo/relatorios/<projeto>/ dentro do Eden OS, para o Centro de Comando consolidar. Use SEMPRE ao FINAL de uma tarefa de código que alterou arquivos, ou quando o usuário disser "gera o relatório", "registra o que mudou", "reporta pro Eden OS". Os agentes de código devem chamar esta skill como último passo de cada alteração.
---

# Relatório de Projeto (spoke)

Ao terminar uma alteração de código, gere o relatório e salve no Eden OS.

## Como
Rode o script com um resumo do que foi feito:
```
python <caminho-eden-os>/projeto-codigo/skills/relatorio-projeto/scripts/gerar.py \
  --resumo "..." \
  --status ok|atencao|bloqueado \
  --agente "<nome do agente>" \
  --porque "..." \
  --proximo "..."
```
- `projeto` e `arquivos` são detectados automaticamente via git.
- Destino automático: `projeto-codigo/relatorios/<projeto>/<timestamp>.md`

## Quando usar
- Último passo de QUALQUER tarefa que alterou arquivos.
- `status`: `ok` (feito), `atencao` (feito mas tem ressalva), `bloqueado` (travou, precisa do André).

## Safety net automático
O hook `Stop` do Eden OS (`scripts/hooks/auto-relatorio.js`) gera um relatório automático ao fim de cada sessão se detectar arquivos alterados via git. O relatório manual (acima) deve ser preferido pois contém contexto — o automático é o fallback.

## Regra
Resumo objetivo, sem floreio. Sempre preencher `--proximo` se ficou pendência.
