---
name: relatar
description: Registra qualquer atividade de um agente do Eden OS na pasta correta do módulo, para o Centro de Comando consolidar no painel. Use SEMPRE ao FINAL de qualquer tarefa de qualquer agente (comercial, marketing, instagram, etc.) — não só código. Dispare em "relata isso", "registra a atividade", "manda pro hub", ou como último passo automático de toda tarefa.
---

# Relatar (toda atividade → módulo certo)

Todo agente do Eden OS chama esta skill como ÚLTIMO passo de qualquer tarefa.

## Uso

```
python _comum/skills/relatar/scripts/relatar.py \
  --agente "<nome>" \
  --area "<area>" \
  --atividade "o que foi feito" \
  --status ok|atencao|bloqueado \
  --resultado "..." \
  --proximo "..."
```

## Destino por área

| --area | Pasta de destino |
|---|---|
| `instagram` | `marketing/relatorios/` |
| `marketing` | `marketing/relatorios/` |
| `trafego` | `marketing/relatorios/` |
| `comercial` | `comercial/relatorios/` |
| `projeto` / `codigo` / `<nome-projeto>` | `projeto-codigo/relatorios/` |
| `cerebro` / `painel` / `geral` | `cerebro/relatorios/` |

## Para publicações do Instagram

Adicionar `--publicacao` salva em `marketing/publicacoes/YYYY-MM-DD/` em vez de relatorios:

```
python _comum/skills/relatar/scripts/relatar.py \
  --agente "agente-instagram" \
  --area "instagram" \
  --atividade "Post carrossel Éden Beauty · Dor gerado" \
  --status ok \
  --publicacao
```

## Estrutura gerada

```
eden-os/
  cerebro/relatorios/         ← C-Squad, vision-chief, painel
  comercial/relatorios/       ← agente-comercial
  marketing/relatorios/       ← agente-marketing, instagram, trafego
  marketing/publicacoes/
    2026-06-21/               ← posts do dia
      2026062114H30-agente-instagram.md
  projeto-codigo/relatorios/  ← projetos de código
```

O `painel-eden` (hub) lê tudo com `agregar.py` e consolida. Resumo objetivo, sem floreio. Sempre preencher `--proximo` se há pendência.
