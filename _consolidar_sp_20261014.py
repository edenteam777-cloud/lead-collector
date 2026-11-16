"""Consolida o lote SP (2026-10-14) a partir do _batch_sp_20261014.jsonl + leads.db:

1. Lê leads novos do lote (com bairro = local da busca).
2. Remove duplicados de lotes anteriores (dedupe por chave o pipeline já faz;
   aqui dedupamos por telefone/nome dentro do lote e conferimos contra
   comercial/leads/ dos lotes anteriores).
3. Auditoria de site por lead: SEM SITE / FORA DO AR / SITE FRACO / SITE OK
   (HTTP status + heurísticas leves de HTML; honesto: psi = null por fora).
4. Score/tier: usa score_local do pipeline (cortes 75/55 já alinhados ao ICP)
   → Hot=QUENTE, Warm=MORNO, Cold=FRIO, Descarte=FORA_ICP/CNPJ_INATIVO.
5. Gera leads-sites.json + leads-sites.md no padrão do lote 2026-09-24 e
   abordagens.html (cards por bairro, Copiar + wa.me) em
   D:/Projetos/EdenOs/eden-os/eden-os/comercial/leads/2026-10-14-leads-sites-sp/.
"""
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import urllib.request
import ssl as _ssl

BASE = Path(__file__).parent
STATE = BASE / "_batch_sp_20261014.jsonl"
DB = BASE / "leads.db"
OUT = Path(r"D:/Projetos/EdenOs/eden-os/eden-os/comercial/leads/2026-10-14-leads-sites-sp")
OLDER_LEADS_DIR = Path(r"D:/Projetos/EdenOs/eden-os/eden-os/comercial/leads")

for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace")


# ---------- auditoria de site ----------
def auditar_site(url: str):
    """Retorna (status_label, problema). Nunca lança."""
    if not url:
        return "SEM SITE", "Não tem site — só aparece no Google Maps/Instagram"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
            code = r.getcode()
            html = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return "FORA DO AR", f"HTTP {e.code}"
    except Exception as e:
        return "FORA DO AR", f"Site não carrega ({type(e).__name__})"
    if code >= 400:
        return "FORA DO AR", f"HTTP {code}"
    low = html.lower()
    for manut in ("página em manutenção", "em manutenção", "maintenance mode",
                  "under construction", "em construção", "coming soon", "em breve"):
        if manut in low:
            return "FORA DO AR", f"Página de manutenção/construção ('{manut}')"
    problemas = []
    if not re.search(r"<h1[\s>]", low):
        problemas.append("Página sem H1 (título principal de SEO)")
    if not re.search(r'<meta[^>]+name=["\']description["\']', low):
        problemas.append("Sem descrição para o Google (meta description)")
    alts_total = len(re.findall(r"<img\b", low))
    alts_sem = len(re.findall(r"<img(?![^>]*\balt=)[^>]*>", low))
    if alts_total >= 5 and alts_sem / alts_total > 0.7:
        problemas.append(f"{alts_sem * 100 // alts_total}% das imagens sem texto alternativo (alt)")
    if "schema.org" not in low:
        problemas.append("Sem dados estruturados (schema.org) — pior chance de aparecer bem no Google")
    if len(problemas) >= 2:
        return "SITE FRACO", problemas[0]
    if problemas:
        return "SITE FRACO", problemas[0]
    return "SITE OK", ""


def _tel_digits(t: str) -> str:
    d = re.sub(r"\D", "", t or "")
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    if len(d) in (11, 12) and d.startswith("0"):
        d = d[1:]
    return d


def celular_valido(tel: str) -> bool:
    d = _tel_digits(tel)
    return len(d) == 11 and d[2] == "9"


def wa_link(tel: str, msg: str) -> str:
    d = _tel_digits(tel)
    return f"https://wa.me/55{d}?text={quote(msg)}"


def fmt_tel(tel: str) -> str:
    d = _tel_digits(tel)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel or "—"


def tier_eden(l: dict) -> str:
    t = l.get("tier") or "FRIO"
    return {"QUENTE": "Hot", "MORNO": "Warm", "FRIO": "Cold"}.get(t, "Descarte")


# ---------- mensagens (estilo André: auto-apresentação, provocativo, curto) ----------
def msg_primeiro_toque(lead: dict) -> str:
    nome = lead["nome"]
    nicho = (lead.get("nicho_rotulo") or "").lower()
    cat = lead["categoria"]
    problema = lead.get("problema", "")

    if cat == "SEM SITE":
        dor = "não tem site — quem procura no Google só acha o Instagram (quando acha)"
    elif cat == "FORA DO AR":
        dor = f"o site está fora do ar ({problema.split('—')[-1].strip() if '—' in problema else problema.lower()})"
    else:
        dor = f"o site tem problema técnico baásico ({problema.lower()})"

    base = (
        f"Oi, tudo bem? Sou o André, da Eden Technology — a gente faz sites e sistemas.\n"
        f"Estive olhando {('a' if nicho.startswith(('clínica','imob','joalh')) else 'o')} "
        f"{nome} no Google e reparei que {dor}.\n"
        f"Posso te mostrar em 2 minutos o que isso custa por mês em cliente que não fecha? "
        f"Se não fizer sentido, é só dizer que eu não escrevo mais."
    )
    return base


# ---------- coleta ----------
def main():
    recs = []
    for line in STATE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            recs.append(json.loads(line))

    bairro_por_chave = {}
    nchaves = []
    for r in recs:
        for l in r["leads"]:
            if l["chave"] not in bairro_por_chave:
                bairro_por_chave[l["chave"]] = (r["bairro"], r["nicho_rotulo"])
                nchaves.append(l["chave"])

    if not nchaves:
        print("Nenhum lead no lote.")
        return

    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        ph = ",".join("?" for _ in nchaves)
        rows = c.execute(f"SELECT * FROM leads WHERE chave IN ({ph})", nchaves).fetchall()
    leads = [dict(r) for r in rows]

    # dedupe dentro do lote por telefone (mesma empresa, cartões diferentes)
    vistos_tel = set()
    unicos = []
    for l in leads:
        d = _tel_digits(l.get("telefone", ""))
        key = (d if len(d) >= 10 else None) or l["chave"]
        if key in vistos_tel:
            continue
        vistos_tel.add(key)
        l["bairro"], l["nicho_rotulo"] = bairro_por_chave.get(l["chave"], ("", ""))
        unicos.append(l)

    # confere contra lotes anteriores em comercial/leads/
    nomes_antigos = set()
    for p in OLDER_LEADS_DIR.rglob("*.md"):
        if OUT.name in str(p.parent):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for nome in (l["nome"] for l in unicos):
            if nome and nome in txt:
                nomes_antigos.add(nome)

    # auditoria de site (paralela — timeouts de 12s seriais seriam lentos demais)
    from concurrent.futures import ThreadPoolExecutor

    def _audita(l):
        cat, prob = auditar_site(l.get("site", ""))
        if cat == "SEM SITE":
            refs = []
            if l.get("instagram"):
                refs.append("Instagram")
            prob = "Não tem site — só aparece em " + (", ".join(refs) if refs else "nenhum link digital encontrado além do Google Maps")
        l["categoria"] = cat
        l["problema"] = prob
        l["psi_performance"] = None
        l["tier_eden"] = tier_eden(l)
        return l

    with ThreadPoolExecutor(max_workers=12) as ex:
        unicos = list(ex.map(_audita, unicos))

    # score final para ordenação
    def sortkey(l):
        urg = 100 if l["categoria"] == "SEM SITE" else (92 if l["categoria"] == "FORA DO AR"
              else (88 if l["categoria"] == "SITE FRACO" else 0))
        return -(urg), -(l.get("score_final") or 0)

    unicos.sort(key=lambda l: (l.get("score_final") or 0) if l["categoria"] != "SITE OK" else -1, reverse=True)

    OUT.mkdir(parents=True, exist_ok=True)

    # ---------- leads-sites.json ----------
    saida = [
        {
            "nome": l["nome"], "nicho": l.get("nicho_rotulo") or l.get("nicho"),
            "bairro": l.get("bairro", ""), "cidade": l.get("cidade", "São Paulo"),
            "categoria": l["categoria"], "problema": l.get("problema", ""),
            "site": l.get("site", ""), "telefone": fmt_tel(l.get("telefone", "")),
            "whatsapp_valido": celular_valido(l.get("telefone", "")),
            "instagram": l.get("instagram", ""), "cnpj": l.get("cnpj", ""),
            "nota_maps": l.get("nota_maps"), "num_reviews": l.get("num_reviews"),
            "score": l.get("score_final") or l.get("score_local") or 0,
            "tier": l["tier_eden"], "psi_performance": None,
        }
        for l in unicos
    ]
    (OUT / "leads-sites.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- leads-sites.md ----------
    por_bairro = defaultdict(int)
    por_cat = defaultdict(int)
    por_nicho = defaultdict(int)
    for l in saida:
        por_bairro[l["bairro"]] += 1
        por_cat[l["categoria"]] += 1
        por_nicho[l["nicho"]] += 1

    md = ["# Leads para venda de sites — São Paulo (bairros nobres)", "",
          f"**Data:** 2026-10-14  ·  **Total de leads auditados:** {len(saida)}", "",
          "Fonte: pipeline de captação `D:\\Projetos\\lead` (Google Maps, 10 agrupamentos de bairros × 5 nichos).", "",
          "## Totais por categoria (geral)", "",
          "| Categoria | Leads |", "|---|---|"]
    for c in ("SEM SITE", "FORA DO AR", "SITE FRACO", "SITE OK"):
        if por_cat.get(c):
            md.append(f"| {c} | {por_cat[c]} |")
    md += ["", "## Totais por bairro", "", "| Bairro | Leads |", "|---|---|"]
    for b, n in sorted(por_bairro.items(), key=lambda x: -x[1]):
        md.append(f"| {b} | {n} |")
    md += ["", "## Totais por nicho", "", "| Nicho | Leads |", "|---|---|"]
    for n, c in sorted(por_nicho.items(), key=lambda x: -x[1]):
        md.append(f"| {n} | {c} |")

    alvo = [l for l in saida if l["categoria"] in ("SEM SITE", "FORA DO AR", "SITE FRACO")]
    md += ["", f"## Leads-alvo (sem site / fora do ar / fraco) — {len(alvo)}", "",
           "| # | Nome | Nicho | Bairro | Categoria | Score | Tier | Telefone | Principal problema |",
           "|---|---|---|---|---|---|---|---|---|"]
    for i, l in enumerate(alvo, 1):
        md.append(
            f"| {i} | {l['nome']} | {l['nicho']} | {l['bairro']} | {l['categoria']} "
            f"| {l['score']} | {l['tier']} | {l['telefone']} | {l['problema']} |"
        )
    ok = [l for l in saida if l["categoria"] == "SITE OK"]
    if ok:
        md += ["", "## Leads SITE OK (fora do alvo, não abordar por site)", "",
               "| Nome | Bairro | Nicho | Site |", "|---|---|---|---|"]
        for l in ok:
            md.append(f"| {l['nome']} | {l['bairro']} | {l['nicho']} | {l['site']} |")

    md += ["", "## Limitações e honestidade metodológica", "",
           "- Auditoria automática de HTML (status HTTP, H1, meta description, alt de imagens, schema.org);",
           "  sem PageSpeed Insights (sem chave de API) — `psi_performance: null` no JSON.",
           "- Score/tier vem do score local do pipeline (cortes 75/55 do ICP)",
           "  — sem qualificação por IA (ANTHROPIC_API_KEY não configurada no ambiente).",
           "- Deduplicação por CNPJ/nome/cidade (pipeline) + por telefone dentro do lote.",
           ]
    if nomes_antigos:
        md.append(f"- Já presentes em lotes anteriores (comercial/leads/): {', '.join(sorted(nomes_antigos))}.")
    (OUT / "leads-sites.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"\nTotal único: {len(unicos)} | por_categoria={dict(por_cat)}")
    print(f"Arquivos em: {OUT}")
    return saida


if __name__ == "__main__":
    main()
