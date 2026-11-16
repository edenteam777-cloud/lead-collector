"""Descartes do lote 1 de demos SP decididos pelo André em 2026-10-15 (após a fase 1).

Marca DESCARTE no leads-sites.json (sai da página de abordagens e das fichas) e move
as pastas de estudo para sao-paulo/_descartados/ (o estudo fica guardado).
Pode rodar de novo.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _gerar_abordagens_sp_20261014 import OUT  # noqa: E402

SP = Path(r"D:/Projetos/sites/prospeccao/sao-paulo")
DESC = {
    "kauffmann imóveis": ("jardins/kauffmann-imoveis",
                          "site completo e funcional (imobiliária de 75 anos) — fase 1, André 15/10"),
    "clínica de estética salomão": ("paulista/clinica-de-estetica-salomao",
                                    "já tem site WordPress (esteticasalomao.com.br) e freela de marketing — fase 1, André 15/10"),
    "eap empório": ("vila-olimpia/eap-emporio-alto-dos-pinheiros",
                    "já tem site com tap list digital — fase 1, André 15/10"),
}

p = OUT / "leads-sites.json"
leads = json.loads(p.read_text(encoding="utf-8"))
for l in leads:
    for frag, (_, motivo) in DESC.items():
        if l["nome"].lower().startswith(frag) and l["categoria"] != "DESCARTE":
            l["categoria_pre_descarte"] = l["categoria"]
            l["categoria"], l["tier"], l["revisao"] = "DESCARTE", "Descarte", motivo
            print("descartado:", l["nome"])
p.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

for pasta, motivo in DESC.values():
    src, dst = SP / pasta, SP / "_descartados" / Path(pasta).name
    if src.exists():
        dst.parent.mkdir(exist_ok=True)
        shutil.move(str(src), str(dst))
        (dst / "DESCARTADO.md").write_text(f"# Descartado em 2026-10-15\n\n{motivo}\n", encoding="utf-8")
        print("movido:", dst)
