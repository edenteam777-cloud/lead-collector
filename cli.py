"""Entrypoint headless — mesma pipeline do app.py (Streamlit), sem UI.

Uso:
    python cli.py --nicho "clínica odontológica" --local "Ubatuba - SP" --max 20

Reaproveita exatamente as mesmas funções que app.py::_worker_thread usa
(sources.google_maps, worker.processar_lote, output.excel, storage.exportar_eden) —
só troca threads/queues/session_state do Streamlit por chamadas diretas.
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Console do Windows costuma vir em cp1252 e quebra em UnicodeEncodeError
# nos emojis dos logs (🗺️, 🔥...) — força UTF-8 antes de qualquer print.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sources.google_maps import coletar_google_maps
from worker import processar_lote
from output.excel import gerar_excel
from output.pdf import gerar_pdf
from storage.exportar_eden import exportar as exportar_eden

EXPORTS_DIR = Path(__file__).parent / "exports"

_TIER_ICON = {"QUENTE": "🔥", "MORNO": "🌡", "FRIO": "❄️", "FORA_ICP": "⛔", "CNPJ_INATIVO": "⛔"}


def _log(msg: str):
    print(msg, flush=True)


def _resumo(leads: list, nicho: str, local: str):
    quentes = [l for l in leads if l.get("tier") == "QUENTE"]
    mornos  = [l for l in leads if l.get("tier") == "MORNO"]
    frios   = [l for l in leads if l.get("tier") not in ("QUENTE", "MORNO")]

    print("\n" + "=" * 60)
    print(f"RESUMO — {nicho} · {local}")
    print(f"Total: {len(leads)} | 🔥 Quente: {len(quentes)} | 🌡 Morno: {len(mornos)} | ❄️ Frio/Fora ICP: {len(frios)}")
    print("=" * 60)

    if quentes:
        print("\n🔥 LEADS QUENTE (prioridade máxima):")
        for l in quentes:
            print(
                f"  - {l.get('nome','?')} | score {l.get('score_final', l.get('score_local',''))} "
                f"| tel {l.get('telefone','—')} | ig {l.get('instagram','—')} | {l.get('cidade','')}"
            )
    if mornos:
        print(f"\n🌡 {len(mornos)} lead(s) MORNO — nutrir.")
    print()


def main():
    ap = argparse.ArgumentParser(description="Captação de leads Eden — headless")
    ap.add_argument("--nicho", required=True, help="Nicho/segmento, ex.: 'clínica odontológica'")
    ap.add_argument("--local", required=True, help="Cidade/região, ex.: 'Ubatuba - SP'")
    ap.add_argument("--max", type=int, default=20, help="Quantidade máxima de leads (default 20)")
    args = ap.parse_args()

    nicho, local, max_leads = args.nicho.strip(), args.local.strip(), args.max
    if not nicho or not local:
        print("Erro: --nicho e --local são obrigatórios.", file=sys.stderr)
        sys.exit(1)

    _log(f"🗺️  Coletando '{nicho}' em '{local}' (máx {max_leads})...")
    leads_brutos = coletar_google_maps(nicho, local, max_leads, _log)
    _log(f"⚙️  Enriquecendo {len(leads_brutos)} empresas (BrasilAPI + score + IA)...")

    leads_finais = []

    def _on_result(lead):
        leads_finais.append(lead)

    asyncio.run(
        processar_lote(
            [{**l, "nicho": nicho, "local": local} for l in leads_brutos],
            log_fn=_log,
            result_fn=_on_result,
        )
    )

    if not leads_finais:
        print("\nNenhum lead novo encontrado (ou todos já eram duplicados no banco).")
        return

    EXPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    xlsx_path = EXPORTS_DIR / f"leads_{ts}_{nicho.replace(' ', '_')}_{local.replace(' ', '_')}.xlsx"
    xlsx_path.write_bytes(gerar_excel(leads_finais, nicho, local))
    _log(f"📊 Excel salvo em: {xlsx_path}")

    pdf_path = EXPORTS_DIR / f"leads_{ts}_{nicho.replace(' ', '_')}_{local.replace(' ', '_')}.pdf"
    pdf_path.write_bytes(gerar_pdf(leads_finais, nicho, local))
    _log(f"📄 PDF salvo em: {pdf_path}")

    try:
        exportar_eden(leads_finais, nicho, local)
        _log("📤 Exportado para comercial/leads/ e marketing/leads/ (Eden OS).")
    except Exception as e:
        _log(f"[!] Falha ao exportar para o Eden OS: {e}")

    _resumo(leads_finais, nicho, local)


if __name__ == "__main__":
    main()
