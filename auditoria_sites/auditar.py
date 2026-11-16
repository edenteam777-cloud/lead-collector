# -*- coding: utf-8 -*-
"""Auditoria de site para leads de venda de sites (Eden Technology).

Não mexe em nada do pipeline de produção (D:\\Projetos\\lead\\cli.py, sources/,
worker.py, storage/). Script isolado, lê os leads via leads_input.py e escreve
o JSON/MD final direto em comercial/leads/2026-09-24-leads-sites/ do Eden OS.

Uso:
    python auditar.py
"""
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from leads_input import carregar_todos  # noqa: E402

OUT_DIR = Path(r"D:\Projetos\EdenOs\eden-os\eden-os\comercial\leads\2026-09-24-leads-sites")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# domínios que NÃO contam como site institucional próprio (rule 1 do briefing)
NONSITE_HOSTS = (
    "instagram.com", "facebook.com", "fb.com", "linktr.ee", "beacons.ai",
    "wa.me", "api.whatsapp.com", "chat.whatsapp.com", "ifood.com.br",
    "booking.com", "airbnb.com", "airbnb.com.br", "sites.google.com",
    "business.site", "canva.site", "bluepillow.com", "spothosts.com",
    "instadelivery.com.br", "sandwiche.me", "linktree.com",
)
NONSITE_SUSPECT_TLD = (".cfd",)  # domínios de shortlink suspeitos tipo restvipsbr.cfd

BUILDER_SIGNATURES = {
    "wix.com": "Wix (construtor de site grátis)",
    "webnode": "Webnode (construtor de site grátis)",
    "blogspot": "Blogger (blog, não site institucional)",
    "weebly": "Weebly (construtor de site grátis)",
    "weeblyte.com": "Weebly (construtor de site grátis)",
    "localo.site": "Localo (mini-site/link-in-bio, não site institucional completo)",
    "canva.site": "Canva Site (página simples feita no Canva)",
    "wordpress.com": "WordPress.com grátis (não é domínio/hospedagem próprios)",
}


def classificar_dominio(site: str) -> str:
    """Retorna 'SEM_SITE' se o link não é um site institucional de verdade."""
    if not site:
        return "SEM_SITE"
    try:
        host = urlparse(site if "://" in site else "http://" + site).netloc.lower()
        host = host.replace("www.", "")
    except Exception:
        return "SEM_SITE"
    if not host:
        return "SEM_SITE"
    for h in NONSITE_HOSTS:
        if h in host:
            return "SEM_SITE"
    for tld in NONSITE_SUSPECT_TLD:
        if host.endswith(tld):
            return "SEM_SITE"
    return "TEM_LINK"


def _get(client, url, **kw):
    try:
        return client.get(url, **kw)
    except Exception as e:
        return e


def checar_html(url: str):
    """Retorna dict com sinais on-page ou None se site fora do ar."""
    problemas = []
    sinais = {}
    try:
        with httpx.Client(follow_redirects=True, timeout=12.0,
                           headers={"User-Agent": "Mozilla/5.0 (EdenAuditoria/1.0)"}) as client:
            t0 = time.time()
            try:
                resp = client.get(url)
            except httpx.ConnectError:
                return {"fora_do_ar": True, "motivo": "Erro de DNS/conexão — domínio não resolve"}
            except httpx.TimeoutException:
                return {"fora_do_ar": True, "motivo": "Timeout — site não respondeu"}
            except Exception as e:
                return {"fora_do_ar": True, "motivo": f"Erro ao acessar: {type(e).__name__}"}
            dt = time.time() - t0

            if resp.status_code >= 400:
                return {"fora_do_ar": True, "motivo": f"HTTP {resp.status_code}"}

            html = resp.text or ""
            sinais["https"] = str(resp.url).startswith("https")
            sinais["tempo_resposta_s"] = round(dt, 2)
            sinais["tamanho_html_kb"] = round(len(html) / 1024, 1)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            title = soup.title.get_text(strip=True) if soup.title else ""
            sinais["title"] = title
            if not title:
                problemas.append("Site não tem título (<title>) definido")

            meta_desc = soup.find("meta", attrs={"name": "description"})
            sinais["meta_description"] = bool(meta_desc and meta_desc.get("content"))
            if not sinais["meta_description"]:
                problemas.append("Sem descrição para o Google (meta description)")

            h1s = soup.find_all("h1")
            sinais["num_h1"] = len(h1s)
            if len(h1s) == 0:
                problemas.append("Página sem H1 (título principal de SEO)")

            viewport = soup.find("meta", attrs={"name": "viewport"})
            sinais["mobile_viewport"] = bool(viewport)
            if not viewport:
                problemas.append("Sem meta viewport — site pode não ser responsivo no celular")

            og = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
            sinais["og_tags"] = len(og) > 0
            if not og:
                problemas.append("Sem tags Open Graph — link do site fica feio quando compartilhado no WhatsApp/Instagram")

            ldjson = soup.find_all("script", attrs={"type": "application/ld+json"})
            has_localbusiness = False
            for tag in ldjson:
                if tag.string and ("LocalBusiness" in tag.string or "Restaurant" in tag.string
                                    or "Hotel" in tag.string or "BeautySalon" in tag.string
                                    or "HairSalon" in tag.string):
                    has_localbusiness = True
            sinais["schema_localbusiness"] = has_localbusiness
            if not has_localbusiness:
                problemas.append("Sem dados estruturados (schema.org) — pior chance de aparecer bem no Google")

            imgs = soup.find_all("img")
            sem_alt = [i for i in imgs if not (i.get("alt") or "").strip()]
            pct_sem_alt = round(100 * len(sem_alt) / len(imgs), 0) if imgs else 0
            sinais["imagens_sem_alt_pct"] = pct_sem_alt
            if imgs and pct_sem_alt >= 50:
                problemas.append(f"{int(pct_sem_alt)}% das imagens sem texto alternativo (alt) — ruim para SEO e acessibilidade")

            noindex = False
            robots_meta = soup.find("meta", attrs={"name": "robots"})
            if robots_meta and "noindex" in (robots_meta.get("content") or "").lower():
                noindex = True
            sinais["noindex"] = noindex
            if noindex:
                problemas.append("Site está bloqueado para o Google (noindex) — não aparece em nenhuma busca")

            # sinais de site antigo/simples
            copyright_match = re.search(r"(?:©|\(c\)|copyright)\s*(\d{4})", html, re.I)
            if copyright_match:
                ano = int(copyright_match.group(1))
                sinais["copyright_ano"] = ano
                if ano <= 2021:
                    problemas.append(f"Rodapé com copyright de {ano} — site não é atualizado há anos")

            builder = None
            html_lower = html.lower()
            url_lower = str(resp.url).lower()
            for sig, label in BUILDER_SIGNATURES.items():
                if sig in html_lower or sig in url_lower:
                    builder = label
                    break
            sinais["builder"] = builder
            if builder:
                problemas.append(f"Site feito em {builder}")

            tem_whatsapp_cta = bool(re.search(r"wa\.me|whatsapp", html_lower))
            sinais["whatsapp_cta"] = tem_whatsapp_cta
            if not tem_whatsapp_cta:
                problemas.append("Sem botão/link de WhatsApp — visitante não converte em contato direto")

            tem_form = bool(soup.find("form"))
            sinais["tem_formulario"] = tem_form

            # robots.txt / sitemap.xml
            base = f"{resp.url.scheme}://{resp.url.host}"
            try:
                r_robots = client.get(base + "/robots.txt", timeout=6.0)
                sinais["robots_txt"] = r_robots.status_code == 200
            except Exception:
                sinais["robots_txt"] = False
            try:
                r_sitemap = client.get(base + "/sitemap.xml", timeout=6.0)
                sinais["sitemap_xml"] = r_sitemap.status_code == 200
            except Exception:
                sinais["sitemap_xml"] = False
            if not sinais["sitemap_xml"]:
                problemas.append("Sem sitemap.xml — dificulta o Google indexar o site")

            if not sinais["https"]:
                problemas.append("Site não é seguro (sem HTTPS/cadeado)")

            if dt > 3.0:
                problemas.append(f"Site demorou {dt:.1f}s para responder (sem contar carregamento completo no celular)")

            sinais["problemas"] = problemas
            return sinais
    except Exception as e:
        return {"fora_do_ar": True, "motivo": f"Erro inesperado: {type(e).__name__}: {e}"}


def rodar_psi(url: str, max_retries=2):
    """Chama PageSpeed Insights (mobile, performance+seo). Retorna dict ou None."""
    for tentativa in range(max_retries + 1):
        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.get(PSI_ENDPOINT, params={
                    "url": url,
                    "strategy": "mobile",
                    "category": ["performance", "seo"],
                })
            if resp.status_code == 429:
                time.sleep(8)
                continue
            if resp.status_code != 200:
                return None
            data = resp.json()
            lr = data.get("lighthouseResult", {})
            cats = lr.get("categories", {})
            perf = cats.get("performance", {}).get("score")
            seo = cats.get("seo", {}).get("score")
            audits = lr.get("audits", {})
            lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
            return {
                "psi_performance": round(perf * 100) if perf is not None else None,
                "psi_seo": round(seo * 100) if seo is not None else None,
                "lcp_s": round(lcp / 1000, 1) if lcp else None,
            }
        except Exception:
            time.sleep(3)
    return None


def montar_problemas_semsite(lead):
    canais = []
    if lead.get("instagram"):
        canais.append("Instagram")
    if lead.get("site") and classificar_dominio(lead["site"]) == "SEM_SITE":
        host = urlparse(lead["site"] if "://" in lead["site"] else "http://" + lead["site"]).netloc
        for h in NONSITE_HOSTS:
            if h in host:
                if "instagram" in h:
                    pass
                elif "facebook" in h or h == "fb.com":
                    canais.append("Facebook")
                elif "booking" in h:
                    canais.append("Booking")
                elif "airbnb" in h:
                    canais.append("Airbnb")
                elif "ifood" in h:
                    canais.append("iFood")
                elif "whatsapp" in h or h == "wa.me":
                    canais.append("WhatsApp")
    canais = list(dict.fromkeys(canais)) or ["nenhum canal próprio"]
    problemas = [f"Não tem site — só aparece em {', '.join(canais)}"]
    problemas.append("Cliente que pesquisa no Google não encontra um site — só rede social ou nada")
    return problemas


def angulo_abordagem(lead, categoria, problemas):
    nome = lead["nome"]
    nicho = lead["nicho"]
    if categoria == "SEM SITE":
        if nicho in ("pousada", "alojamento local"):
            return (f"{nome} não tem site próprio — depende 100% de Instagram/indicação e "
                    f"provavelmente perde reserva direta para quem paga comissão de OTA.")
        if nicho in ("salão de beleza", "cabeleireiro"):
            return (f"{nome} não tem site — quem pesquisa 'salão perto de mim' no Google "
                    f"não encontra, só quem já segue no Instagram.")
        if nicho == "restaurante":
            return (f"{nome} não tem site — turista/cliente que pesquisa 'restaurante em "
                    f"{lead['cidade']}' no Google antes de decidir não encontra vocês.")
        return f"{nome} não tem site institucional — só está em redes sociais/diretórios de terceiros."
    if categoria == "FORA DO AR":
        return f"O site de {nome} está fora do ar agora — quem pesquisa o nome no Google cai em erro."
    if categoria == "SITE FRACO":
        top = problemas[0] if problemas else "site desatualizado"
        return f"{nome} até tem site, mas {top[0].lower() + top[1:]} — está perdendo cliente por isso."
    return f"{nome} tem site em condição razoável — não é alvo prioritário agora."


def calcular_urgencia(categoria, sinais, nota_maps, num_reviews):
    if categoria == "SEM SITE":
        base = 92
    elif categoria == "FORA DO AR":
        base = 88
    elif categoria == "SITE FRACO":
        n_problemas = len(sinais.get("problemas", [])) if sinais else 0
        base = min(85, 35 + n_problemas * 7)
    else:
        base = 10

    bonus = 0
    if nota_maps and nota_maps >= 4.5:
        bonus += 4
    if num_reviews and num_reviews >= 100:
        bonus += 4
    elif num_reviews and num_reviews >= 30:
        bonus += 2

    return max(0, min(100, base + bonus))


def processar_lead(lead):
    site = lead.get("site", "")
    dominio_status = classificar_dominio(site)

    if dominio_status == "SEM_SITE":
        categoria = "SEM SITE"
        problemas = montar_problemas_semsite(lead)
        sinais = {}
        psi = {"psi_performance": None, "psi_seo": None, "lcp_s": None}
    else:
        url = site if site.startswith("http") else "https://" + site
        sinais = checar_html(url)
        if sinais.get("fora_do_ar"):
            categoria = "FORA DO AR"
            problemas = [sinais.get("motivo", "Site fora do ar")]
            psi = {"psi_performance": None, "psi_seo": None, "lcp_s": None}
        else:
            problemas = sinais.get("problemas", [])
            psi_result = rodar_psi(url)
            if psi_result:
                psi = psi_result
                if psi["psi_performance"] is not None and psi["psi_performance"] < 50:
                    problemas.insert(0, f"Nota de performance mobile no PageSpeed: {psi['psi_performance']}/100 (ruim)")
                if psi["lcp_s"] is not None and psi["lcp_s"] > 4:
                    problemas.insert(0, f"Site leva {psi['lcp_s']:.1f}s para carregar o conteúdo principal no celular (LCP)")
            else:
                psi = {"psi_performance": None, "psi_seo": None, "lcp_s": None}
                problemas.append("PSI indisponível (rate limit do Google) — auditoria só com checagem HTML")
            categoria = "SITE OK" if len(problemas) <= 2 and (psi.get("psi_performance") or 100) >= 70 else "SITE FRACO"

    urgencia = calcular_urgencia(categoria, sinais, lead.get("nota_maps"), lead.get("num_reviews"))
    angulo = angulo_abordagem(lead, categoria, problemas)

    return {
        "cidade": lead["cidade"],
        "pais": lead["pais"],
        "nicho": lead["nicho"],
        "nome": lead["nome"],
        "telefone": lead.get("telefone", ""),
        "instagram": lead.get("instagram", ""),
        "site": site,
        "nota_maps": lead.get("nota_maps"),
        "num_reviews": lead.get("num_reviews"),
        "categoria": categoria,
        "urgencia": urgencia,
        "psi_performance": psi.get("psi_performance"),
        "psi_seo": psi.get("psi_seo"),
        "lcp_s": psi.get("lcp_s"),
        "problemas": problemas,
        "angulo": angulo,
    }


def main():
    leads = carregar_todos()
    print(f"Auditando {len(leads)} leads...")
    resultados = []
    for i, lead in enumerate(leads, 1):
        print(f"[{i}/{len(leads)}] {lead['cidade']} | {lead['nicho']} | {lead['nome'][:50]}")
        r = processar_lead(lead)
        resultados.append(r)
        print(f"   -> {r['categoria']} | urgencia={r['urgencia']} | problemas={len(r['problemas'])}")

    out_json = OUT_DIR / "leads-sites.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\nJSON salvo em {out_json}")

    with open(OUT_DIR / "_raw_resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
