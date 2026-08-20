"""Gera um relatório PDF dos leads já salvos no banco — sem captar leads novos.

Uso:
    python relatorio_pdf.py                          # todos os leads
    python relatorio_pdf.py --tier QUENTE             # só os QUENTE
    python relatorio_pdf.py --nicho "clínica"         # filtra por nicho (substring)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from storage.db import carregar_todos
from output.pdf import gerar_pdf

EXPORTS_DIR = Path(__file__).parent / "exports"


def main():
    ap = argparse.ArgumentParser(description="Relatório PDF dos leads já capturados")
    ap.add_argument("--tier", choices=["QUENTE", "MORNO", "FRIO"], help="Filtra por tier")
    ap.add_argument("--nicho", help="Filtra por nicho (substring, sem diferenciar maiúsculas)")
    args = ap.parse_args()

    leads = carregar_todos(filtro_tier=args.tier)
    if args.nicho:
        alvo = args.nicho.lower()
        leads = [l for l in leads if alvo in (l.get("nicho") or "").lower()]

    if not leads:
        print("Nenhum lead encontrado no banco com esses filtros.")
        return

    titulo_nicho = args.nicho or "Todos os segmentos"
    titulo_local = f"Banco consolidado — {args.tier.title() if args.tier else 'todos os tiers'}"

    EXPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    pdf_path = EXPORTS_DIR / f"relatorio_{ts}.pdf"
    pdf_path.write_bytes(gerar_pdf(leads, titulo_nicho, titulo_local))

    print(f"📄 PDF salvo em: {pdf_path}")
    print(f"{len(leads)} lead(s) incluído(s) no relatório.")


if __name__ == "__main__":
    main()
