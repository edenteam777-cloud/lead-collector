# -*- coding: utf-8 -*-
"""Consolida os leads-alvo (Ubatuba via banco SQLite do pipeline + Porto via
pesquisa manual, já que o scraper de sources/google_maps.py não capturou
telefone/instagram para listagens em Portugal) para a auditoria de sites.

Não altera nada do pipeline de producao (D:\\Projetos\\lead\\cli.py, sources/, worker.py).
"""
import sqlite3
import re

DB_PATH = r"D:\Projetos\lead\leads.db"


def _fmt_tel_br(raw: str) -> str:
    """Formata telefone brasileiro para E.164 (+55...)."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("55") and len(digits) >= 12:
        pass
    elif len(digits) in (10, 11):
        digits = "55" + digits
    elif len(digits) in (12, 13) and digits.startswith("0"):
        digits = "55" + digits[1:]
    else:
        # tenta remover DDI duplicado tipo "01" na frente (bug de captura: "(01) 2983..." )
        if digits.startswith("01") and len(digits) in (12, 13):
            digits = "55" + digits[2:]
        elif len(digits) >= 10:
            digits = "55" + digits[-11:] if len(digits) - 11 <= 2 else digits
    if not digits.startswith("55"):
        digits = "55" + digits
    return "+" + digits


def carregar_ubatuba():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    out = []

    def rows(nicho_like):
        cur.execute(
            "SELECT nome, telefone, instagram, site, nota_maps, num_reviews "
            "FROM leads WHERE nicho=? AND cidade='Ubatuba' AND (telefone<>'' OR instagram<>'')",
            (nicho_like,),
        )
        return [dict(r) for r in cur.fetchall()]

    mapa = {
        "Salão de beleza": "salão de beleza",
        "apartamento temporada": "pousada",  # tratado como categoria "hospedagem" (equivalente a pousada)
        "pousada": "pousada",
        "restaurante": "restaurante",
    }
    for nicho_db, nicho_label in mapa.items():
        for r in rows(nicho_db):
            out.append({
                "cidade": "Ubatuba",
                "pais": "Brasil",
                "nicho": nicho_label,
                "nome": r["nome"].strip(),
                "telefone": _fmt_tel_br(r["telefone"]),
                "instagram": r["instagram"] or "",
                "site": (r["site"] or "").strip(),
                "nota_maps": r["nota_maps"],
                "num_reviews": r["num_reviews"],
            })
    con.close()
    return out


# Leads de Porto (Portugal) — capturados via cli.py (nome/nota_maps apenas;
# telefone/instagram/site vieram VAZIOS do scraper para 100% dos resultados em
# Portugal, limitação conhecida e documentada) e enriquecidos manualmente via
# WebSearch (fontes: sites oficiais, Facebook/Instagram, diretórios como
# Yelp/Tripadvisor/Booking, consultados em 24/09/2026).
PORTO_LEADS = [
    # cabeleireiro
    dict(nicho="cabeleireiro", nome="Gomes Cortes e Cores", telefone="+351225106847",
         instagram="@gomescortesecores", site="https://gomescortesecores.pt/",
         nota_maps=4.9, num_reviews=None),
    dict(nicho="cabeleireiro", nome="Magikhair", telefone="+351910375085",
         instagram="@magik.hair", site="", nota_maps=4.9, num_reviews=None),
    dict(nicho="cabeleireiro", nome="Foz Concept Cabeleireiro", telefone="+351226189012",
         instagram="@fozconcept", site="", nota_maps=4.9, num_reviews=None),
    dict(nicho="cabeleireiro", nome="Miguel Viana Cabeleireiros", telefone="+351226109945",
         instagram="", site="https://www.miguelviana.com/en/oporto/", nota_maps=4.9, num_reviews=None),
    dict(nicho="cabeleireiro", nome="Creative Porto", telefone="",
         instagram="@creativeporto", site="", nota_maps=4.9, num_reviews=None),
    # restaurante
    dict(nicho="restaurante", nome="The Door", telefone="+351910573099",
         instagram="@thedoor.porto", site="", nota_maps=4.8, num_reviews=None),
    dict(nicho="restaurante", nome="MUU Steakhouse", telefone="+351914784032",
         instagram="@muu_steakhouse", site="https://www.muusteakhouse.com/", nota_maps=4.8, num_reviews=None),
    dict(nicho="restaurante", nome="Bota & Bira", telefone="+351960244918",
         instagram="", site="", nota_maps=4.8, num_reviews=None),
    dict(nicho="restaurante", nome="Flow Restaurant & Bar", telefone="+351222054016",
         instagram="@flowrestaurant", site="https://flowrestaurant.pt", nota_maps=4.8, num_reviews=None),
    dict(nicho="restaurante", nome="Bulha Porto - Cozinha Tradicional Portuguesa", telefone="+351220980150",
         instagram="@bulhaporto", site="https://bulhaporto.localo.site/", nota_maps=4.8, num_reviews=None),
    dict(nicho="restaurante", nome="Casa Viúva", telefone="+351222000672",
         instagram="@winebarcasadaviuva", site="https://casa-viuva.weeblyte.com/", nota_maps=4.8, num_reviews=None),
    # alojamento local / guest house
    dict(nicho="alojamento local", nome="GuestHouse Marquês (Charming House Marquês)", telefone="+351225098076",
         instagram="", site="https://www.charminghousemarques.com/", nota_maps=3.9, num_reviews=None),
    dict(nicho="alojamento local", nome="Mo House Alojamento Local", telefone="+351222032194",
         instagram="", site="https://www.mohouse.pt/", nota_maps=3.9, num_reviews=None),
    dict(nicho="alojamento local", nome="Residencial Porto Novo", telefone="+351222055739",
         instagram="", site="http://www.residencialportonovo.com/", nota_maps=3.9, num_reviews=None),
]


def carregar_porto():
    out = []
    for r in PORTO_LEADS:
        out.append({
            "cidade": "Porto",
            "pais": "Portugal",
            "nicho": r["nicho"],
            "nome": r["nome"],
            "telefone": r["telefone"],
            "instagram": r["instagram"],
            "site": r["site"],
            "nota_maps": r["nota_maps"],
            "num_reviews": r["num_reviews"],
        })
    return out


def carregar_todos():
    todos = carregar_ubatuba() + carregar_porto()
    # dedup por (cidade, nome)
    vistos = set()
    out = []
    for l in todos:
        k = (l["cidade"], l["nome"].lower())
        if k in vistos:
            continue
        vistos.add(k)
        # filtro de qualidade: precisa ter telefone OU instagram
        if not l["telefone"] and not l["instagram"]:
            continue
        out.append(l)
    return out


if __name__ == "__main__":
    import json
    todos = carregar_todos()
    print(f"Total leads consolidados: {len(todos)}")
    from collections import Counter
    print(Counter((l["cidade"], l["nicho"]) for l in todos))
