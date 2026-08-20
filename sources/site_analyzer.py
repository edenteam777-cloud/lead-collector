"""Análise técnica do site — tecnologia, WhatsApp, formulário, ERP/agenda robusto."""
import re
import httpx
from config import HEADERS, SCRAPING_TIMEOUT

_TECNOLOGIAS = {
    "wix": ["wix.com", "wixstatic.com", "wix-code"],
    "wordpress": ["wp-content", "wp-includes", "wordpress"],
    "shopify": ["cdn.shopify.com", "shopify.com"],
    "blogger": ["blogspot.com", "blogger.com"],
    "squarespace": ["squarespace.com"],
}

# Sinal de que a empresa já usa um sistema robusto de agenda/ERP —
# usado pelo gate "usa_erp_robusto" do score local.
_ERP_ROBUSTO = [
    "trinks.com", "boulevard.io", "zenoti.com", "salesforce.com",
    "totvs.com", "sap.com", "senior.com.br",
]


async def analisar_site(url: str) -> dict:
    """Retorna {'tecnologia', 'tem_ssl', 'tem_whatsapp', 'tem_formulario', 'usa_erp_robusto'}."""
    result = {
        "tecnologia": "",
        "tem_ssl": False,
        "tem_whatsapp": False,
        "tem_formulario": False,
        "usa_erp_robusto": False,
    }
    if not url:
        return result
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=SCRAPING_TIMEOUT,
            verify=False, follow_redirects=True,
        ) as client:
            r = await client.get(url)
            html = r.text
            html_l = html.lower()

            result["tem_ssl"] = str(r.url).startswith("https://")

            for tech, sinais in _TECNOLOGIAS.items():
                if any(s in html_l for s in sinais):
                    result["tecnologia"] = tech
                    break

            result["tem_whatsapp"] = bool(re.search(r"wa\.me/|api\.whatsapp\.com", html_l))
            result["tem_formulario"] = "<form" in html_l
            result["usa_erp_robusto"] = any(s in html_l for s in _ERP_ROBUSTO)

    except Exception:
        pass
    return result
