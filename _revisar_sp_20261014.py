"""Revisão manual do lote SP 2026-10-14 (sessão principal, após auditoria automática).

Corrige falsos positivos da auditoria de site antes de gerar as abordagens:
- "FORA DO AR" reverificado com user-agent de navegador: páginas "em breve/em construção" estavam no ar
  (falso positivo do detector), 403 = bloqueio anti-robô (não dá para afirmar), DNS morto = fora do ar real,
  404/410/523 = link da ficha do Google quebrado.
- Link do Maps que é Instagram/WhatsApp/Linktree/Facebook = SEM SITE (não "SITE FRACO").
- Redes nacionais/globais, franquias, shopping e páginas de empreendimento = DESCARTE (não são ICP).
Idempotente: guarda a categoria original em `categoria_auditoria` e só aplica uma vez.
"""
import json
import re
import sys
from pathlib import Path

OUT = Path(r"D:/Projetos/EdenOs/eden-os/eden-os/comercial/leads/2026-10-14-leads-sites-sp")

for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace")

# Fragmentos de nome (minúsculo) → motivo de descarte
DESCARTE = {
    "canopy by hilton": "rede hoteleira global",
    "bottega veneta": "marca global de luxo",
    "le pain quotidien": "rede global",
    "cipórestô": "restaurante de hotel Accor",
    "altto vila madalena": "página de empreendimento (Even), não é empresa",
    "ária higienópolis": "página de empreendimento, não é empresa",
    "pandora": "rede global",
    "hstern": "rede nacional",
    "onodera": "franquia nacional",
    "shopping vila olímpia": "shopping center",
    "remax": "franquia nacional",
    "spa saúde e estética": "franquia (página de unidade)",
    "royal face": "franquia (página de unidade)",
    "paulo roberto leardi": "rede imobiliária (unidade)",
    "apartamentos de alto padrão em pinheiros": "anúncio de imóvel, não é empresa",
    "zimmermann imóveis | alto padrão em perdizes": "duplicado — Zimmermann tem site no ar (zimoveis.com.br)",
}

SOCIAL = re.compile(r"instagram\.com|wa\.me|api\.whatsapp\.com|linktr\.ee|facebook\.com", re.I)

# Reverificação de 2026-10-14 com UA de navegador (urllib, timeout 20s)
DNS_MORTO = ("studioesteticamoema.shop", "emporiumdabelezapinheiros.com", "estacaopinheiros.com.br",
             "jbestetica.com", "uniquebem.com.br", "emporiodoouro.com.br", "leticiadenobrega.com")
LINK_QUEBRADO = ("shapeclinic.com.br", "vonbeauty.com.br", "liegenegociosimobiliarios.com.br",
                 "artigianojoias.com.br")


def revisar(l: dict) -> None:
    if "categoria_auditoria" in l:
        return
    l["categoria_auditoria"] = l["categoria"]
    nome = l["nome"].lower()
    site = (l.get("site") or "").lower()

    for frag, motivo in DESCARTE.items():
        if frag in nome:
            l["categoria"], l["tier"], l["revisao"] = "DESCARTE", "Descarte", motivo
            return

    if SOCIAL.search(site):
        rede = "Instagram" if "instagram" in site else "Linktree" if "linktr" in site else \
            "Facebook" if "facebook" in site else "WhatsApp"
        l["categoria"] = "SEM SITE"
        l["problema"] = f"Não tem site — o link da ficha do Google leva ao {rede}"
        l["revisao"] = "link do Maps é rede social/WhatsApp, não site"
        return

    if l["categoria"] != "FORA DO AR":
        return
    if any(d in site for d in DNS_MORTO):
        l["problema"] = "Domínio não responde (DNS)"
        l["revisao"] = "fora do ar confirmado (DNS)"
    elif any(d in site for d in LINK_QUEBRADO):
        l["problema"] = "Link do site na ficha do Google abre página de erro"
        l["revisao"] = "link quebrado confirmado (404/410/523)"
    elif "manuten" in (l.get("problema") or "").lower():
        l["categoria"] = "SITE OK"
        l["revisao"] = "falso positivo: site no ar (detector de 'em breve' errou)"
    else:  # 403, timeout, conexão encerrada: não dá para afirmar que está fora
        l["categoria"] = "VERIFICAR"
        l["revisao"] = "não confirmado (bloqueio anti-robô ou timeout) — checar no navegador"


def main():
    p = OUT / "leads-sites.json"
    leads = json.loads(p.read_text(encoding="utf-8"))
    for l in leads:
        revisar(l)
    p.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter
    print(Counter(l["categoria"] for l in leads))


if __name__ == "__main__":
    main()
