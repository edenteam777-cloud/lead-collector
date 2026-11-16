"""Driver de captação em lote — São Paulo bairros nobres (2026-10-14).

Roda cli.py em sequência para cada combo (nicho, bairro), registrando num
JSONL quais leads entraram no banco em cada busca (o schema do leads.db não
guarda bairro/local — sem isso não dá pra agrupar a abordagem por bairro).

Uso: python _batch_sp_20261112.py
Log: _batch_sp_20261112.log · Estado: _batch_sp_20261112.jsonl
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).parent
VENV_PY = BASE / ".venv" / "Scripts" / "python.exe"
CLI = BASE / "cli.py"
DB = BASE / "leads.db"
LOG = BASE / "_batch_sp_20261112.log"
STATE = BASE / "_batch_sp_20261112.jsonl"

for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


BAIRROS = [
    "Jardins, São Paulo - SP",
    "Itaim Bibi, São Paulo - SP",
    "Moema, São Paulo - SP",
    "Pinheiros, São Paulo - SP",
    "Vila Nova Conceição, São Paulo - SP",
    "Higienópolis, São Paulo - SP",
    "Perdizes, São Paulo - SP",
    "Brooklin, São Paulo - SP",
]
NICHOS = [
    ("clínica odontológica implantes", "odontologia/implantes", 7),
    ("dermatologista clínica médica particular", "dermatologia/clínica médica", 7),
    ("fisioterapia e pilates studio", "fisioterapia/pilates", 6),
    ("escritório de advocacia", "advocacia boutique", 5),
]

def db_new_ids(before_max):
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT id, chave, nome, nicho, telefone, instagram, site, cidade, "
            "estado, cnpj, nota_maps, num_reviews, score_local, score_final, tier "
            "FROM leads WHERE id > ? ORDER BY id", (before_max,)
        ).fetchall()
    return [dict(r) for r in rows]


def db_max_id():
    try:
        with sqlite3.connect(DB) as c:
            return c.execute("SELECT COALESCE(MAX(id),0) FROM leads").fetchone()[0]
    except Exception:
        return 0


def main():
    env = dict(os.environ)
    # Exporta per-run para o Eden OS real (D:\Projetos\EdenOs), não a cópia do Desktop.
    env["EDEN_OS_PATH"] = r"D:\Projetos\EdenOs\eden-os\eden-os"

    combos = [(n, nlabel, mx, b) for n, nlabel, mx in NICHOS for b in BAIRROS]
    done = set()
    if STATE.exists():
        for line in STATE.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                done.add((rec["nicho_busca"], rec["bairro"]))
            except Exception:
                pass
    log(f"=== Início: {len(combos)} combos ({len(done)} já feitos) ===")

    for i, (nicho, nicho_label, mx, bairro) in enumerate(combos, 1):
        if (nicho, bairro) in done:
            continue
        log(f"--- [{i}/{len(combos)}] {nicho} @ {bairro} (max {mx}) ---")
        before = db_max_id()
        t0 = time.time()
        err = ""
        try:
            p = subprocess.run(
                [str(VENV_PY), str(CLI), "--nicho", nicho, "--local", bairro, "--max", str(mx)],
                cwd=str(BASE), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=1800,
            )
            tail = "\n".join((p.stdout or "").splitlines()[-14:])
            log(f"rc={p.returncode} em {time.time()-t0:.0f}s | tail:\n{tail}")
            if p.returncode != 0:
                err = (p.stderr or "")[-400:]
        except Exception as e:
            err = f"{e}\n{traceback.format_exc()[-300:]}"
            log(f"[!] Exceção na busca: {e}")

        # DB fica em WAL; dá um respiro antes de ler
        time.sleep(2)
        novos = db_new_ids(before)
        rec = {
            "nicho_busca": nicho, "nicho_rotulo": nicho_label, "bairro": bairro,
            "novos": len(novos), "erro": err, "leads": novos,
        }
        with open(STATE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log(f"    → {len(novos)} lead(s) novo(s) no banco")

    total = sum(
        json.loads(l)["novos"] for l in STATE.read_text(encoding="utf-8").splitlines()
        if l.strip()
    )
    log(f"=== FIM: {total} leads novos no lote SP ===")


if __name__ == "__main__":
    main()
