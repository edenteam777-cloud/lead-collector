"""Corrige @ de Instagram atribuídos à empresa errada no lote SP 2026-10-14.

O scraper reaproveitou o @ de um card anterior quando a empresa não tinha perfil próprio
(ex.: 5 restaurantes diferentes com @lavecchiabottiglia). Mantém só o @ que vem do link
da própria ficha (instagram.com/<handle>) ou que contém uma palavra do nome da empresa.
Idempotente: o valor original fica em `instagram_scraper`.
"""
import json
import re
import unicodedata
from pathlib import Path

OUT = Path(r"D:/Projetos/EdenOs/eden-os/eden-os/comercial/leads/2026-10-14-leads-sites-sp")


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def main():
    p = OUT / "leads-sites.json"
    leads = json.loads(p.read_text(encoding="utf-8"))
    limpos = 0
    for l in leads:
        if "instagram_scraper" in l:
            continue
        ig = (l.get("instagram") or "").lstrip("@").lower()
        l["instagram_scraper"] = l.get("instagram") or ""
        if not ig:
            continue
        m = re.search(r"instagram\.com/([^/?#]+)", l.get("site") or "", re.I)
        palavras = [w for w in re.findall(r"[a-z]{4,}", norm(l["nome"]))
                    if w not in ("arquitetura", "interiores", "design", "estetica", "clinica", "studio", "imoveis")]
        if (m and m.group(1).lower() == ig) or any(w in norm(ig) for w in palavras):
            continue
        l["instagram"] = ""
        limpos += 1
    p.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print("instagram removido (era de outra empresa):", limpos)


if __name__ == "__main__":
    main()
