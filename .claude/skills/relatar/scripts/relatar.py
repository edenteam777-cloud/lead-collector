#!/usr/bin/env python3
"""Registra QUALQUER atividade de um agente no Eden OS, roteando para a pasta certa."""
import os, datetime, argparse, pathlib

# Auto-detecta a raiz do eden-os a partir da localização deste script:
# scripts/ → relatar/ → skills/ → _comum/ → eden-os/
_EDEN_ROOT = pathlib.Path(__file__).resolve().parents[4]

# Todos os relatórios vão para cerebro/relatorios/ (pasta central de comando)
AREA_MODULO = {
    "instagram": "cerebro",
    "marketing": "cerebro",
    "trafego": "cerebro",
    "comercial": "cerebro",
    "projeto": "cerebro",
    "codigo": "cerebro",
    "cerebro": "cerebro",
    "painel": "cerebro",
    "geral": "cerebro",
}

ap = argparse.ArgumentParser(description="Relata atividade de um agente do Eden OS.")
ap.add_argument("--agente", required=True, help="Nome do agente")
ap.add_argument("--atividade", required=True, help="O que foi feito")
ap.add_argument("--area", default="geral",
                help="instagram | marketing | trafego | comercial | projeto | cerebro | geral")
ap.add_argument("--status", default="ok", choices=["ok", "atencao", "bloqueado"])
ap.add_argument("--resultado", default="")
ap.add_argument("--proximo", default="")
ap.add_argument("--publicacao", action="store_true",
                help="Marca como publicação → salva em marketing/publicacoes/YYYY-MM-DD/")
a = ap.parse_args()

ts = datetime.datetime.now()
ts_str = ts.strftime("%Y-%m-%dT%H:%M")
data_str = ts.strftime("%Y-%m-%d")

if a.publicacao:
    modulo = "marketing"
    destino = _EDEN_ROOT / "marketing" / "publicacoes" / data_str
else:
    modulo = AREA_MODULO.get(a.area.lower(), "cerebro")
    destino = _EDEN_ROOT / modulo / "relatorios"

destino.mkdir(parents=True, exist_ok=True)
nome = f"{ts_str.replace('T', '').replace(':', '')}-{a.agente}.md"
out = destino / nome

out.write_text(f"""---
area: {a.area}
modulo: {modulo}
data: {ts_str}
agente: {a.agente}
status: {a.status}
---
## O que mudou
{a.atividade}

## Resultado
{a.resultado or '—'}

## Próximo passo
{a.proximo or '—'}
""", encoding="utf-8")
print(f"OK Relatado em: {out.relative_to(_EDEN_ROOT)}")
