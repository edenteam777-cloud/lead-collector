#!/usr/bin/env python3
"""Gera um relatório estruturado na pasta cerebro/relatorios/ do Eden OS."""
import os, sys, subprocess, datetime, argparse, pathlib

# Auto-detecta raiz: scripts/ → relatorio-projeto/ → skills/ → projeto-codigo/ → eden-os/
_EDEN_ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = os.environ.get("EDEN_RELATORIOS") or str(_EDEN_ROOT / "cerebro" / "relatorios")

def sh(cmd, cwd=None):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       stderr=subprocess.DEVNULL, cwd=cwd).strip()
    except Exception:
        return ""

ap = argparse.ArgumentParser()
ap.add_argument("--resumo", default="", help="O que mudou (auto-detectado do git se omitido)")
ap.add_argument("--status", default="ok", choices=["ok", "atencao", "bloqueado"])
ap.add_argument("--agente", default="agente-codigo")
ap.add_argument("--porque", default="")
ap.add_argument("--proximo", default="")
a = ap.parse_args()

cwd = os.getcwd()
projeto = sh("git rev-parse --show-toplevel", cwd=cwd)
projeto = os.path.basename(projeto) if projeto else os.path.basename(cwd)

arquivos_raw = sh("git diff --name-only HEAD", cwd=cwd) or sh("git diff --name-only --cached", cwd=cwd)
arquivos = arquivos_raw.split("\n") if arquivos_raw else []

# Auto-detecta resumo se não foi passado
resumo = a.resumo
if not resumo:
    resumo = sh("git log -1 --pretty=%s", cwd=cwd)
if not resumo and arquivos:
    resumo = f"Alterações em: {', '.join(arquivos[:5])}"
if not resumo:
    resumo = "Alterações de código sem commit registrado"

ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
arqs_str = ", ".join(arquivos) if arquivos else "—"

d = pathlib.Path(BASE) / projeto
d.mkdir(parents=True, exist_ok=True)
out = d / f"{ts.replace('T','').replace(':','')}.md"

out.write_text(f"""---
projeto: {projeto}
data: {ts}
agente: {a.agente}
status: {a.status}
arquivos: {arqs_str}
---
## O que mudou
{resumo}

## Por quê
{a.porque or '—'}

## Próximo passo
{a.proximo or '—'}
""", encoding="utf-8")
print(f"✅ Relatório salvo: {out.relative_to(_EDEN_ROOT)}")
