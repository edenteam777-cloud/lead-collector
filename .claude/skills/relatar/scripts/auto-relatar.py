#!/usr/bin/env python3
"""
Auto-relata atividade ao final de cada sessão Eden OS.
Chamado pelo hook Stop do Claude Code — silencioso por padrão.

Regras:
  1. Se relatório foi gerado nos últimos 5 min → pula (evita duplicata)
  2. Se nenhum arquivo relevante foi modificado nos últimos 120 s → pula (apenas Q&A)
  3. Caso contrário → chama relatar.py com contexto inferido do CWD
"""
import os, sys, json, datetime, pathlib, subprocess

# Auto-detecta raiz a partir da localização do script:
# scripts/ → relatar/ → skills/ → _comum/ → eden-os/
_EDEN_ROOT = pathlib.Path(__file__).resolve().parents[4]
_RELATAR = _EDEN_ROOT / "_comum" / "skills" / "relatar" / "scripts" / "relatar.py"
_CEREBRO_REL = _EDEN_ROOT / "cerebro" / "relatorios"

# Extensões que indicam trabalho real (não só leitura)
_WORK_EXTS = {".md", ".html", ".py", ".ts", ".tsx", ".json", ".css", ".js", ".txt"}

# Mapeamento CWD → (area, agente)
_AREA_MAP = [
    ("marketing",  "marketing",  "agente-marketing"),
    ("instagram",  "instagram",  "agente-instagram"),
    ("trafego",    "trafego",    "agente-trafego"),
    ("comercial",  "comercial",  "agente-comercial"),
    ("cerebro",    "cerebro",    "vision-chief"),
    ("projeto",    "projeto",    "eden-engineer"),
    ("codigo",     "codigo",     "eden-engineer"),
]


def _infer_area(cwd: pathlib.Path):
    cwd_str = str(cwd).lower().replace("\\", "/")
    for keyword, area, agente in _AREA_MAP:
        if keyword in cwd_str:
            return area, agente
    return "geral", "claude"


def _recent_report(minutes=5) -> bool:
    if not _CEREBRO_REL.exists():
        return False
    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
    for f in _CEREBRO_REL.rglob("*.md"):
        if datetime.datetime.fromtimestamp(f.stat().st_mtime) > cutoff:
            return True
    return False


def _recent_files(cwd: pathlib.Path, seconds=120):
    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=seconds)
    found = []
    try:
        for f in cwd.rglob("*"):
            if f.is_file() and f.suffix in _WORK_EXTS:
                try:
                    if datetime.datetime.fromtimestamp(f.stat().st_mtime) > cutoff:
                        found.append(f.name)
                        if len(found) >= 8:
                            break
                except OSError:
                    pass
    except (PermissionError, OSError):
        pass
    return found


def main():
    # Lê stdin (contexto do hook Stop — pode ser vazio)
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    cwd = pathlib.Path(os.getcwd())
    area, agente = _infer_area(cwd)

    # Regra 1: relatório recente → pula
    if _recent_report(minutes=5):
        sys.exit(0)

    # Regra 2: sem arquivos modificados recentemente → apenas Q&A, pula
    modified = _recent_files(cwd, seconds=120)
    if not modified:
        sys.exit(0)

    # Infere atividade a partir dos arquivos modificados
    names = ", ".join(modified[:4])
    atividade = f"Sessão encerrada — arquivos modificados: {names}"
    if len(modified) > 4:
        atividade += f" (+{len(modified)-4} outros)"

    # Chama relatar.py (silencia stdout/stderr do subprocesso)
    try:
        subprocess.run(
            [
                sys.executable, str(_RELATAR),
                "--agente",    agente,
                "--area",      area,
                "--atividade", atividade,
                "--status",    "ok",
                "--resultado", f"{len(modified)} arquivo(s) modificado(s) nesta sessão",
                "--proximo",   "Verificar relatório gerado no cerebro/relatorios/",
            ],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        pass  # Nunca bloqueia o Claude


if __name__ == "__main__":
    main()
