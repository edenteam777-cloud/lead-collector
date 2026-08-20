"""Scraping do site da empresa — extrai CNPJ e descrição para o Claude Agent."""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from config import HEADERS, SCRAPING_TIMEOUT
from sources.brasil_api import extrair_cnpj


async def scrape_site(url: str) -> dict:
    """Retorna {'cnpj': str, 'info': str}. Nunca lança exceção."""
    result = {"cnpj": "", "info": ""}
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
            soup = BeautifulSoup(html, "html.parser")

            # Descrição para o Claude Agent
            meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
            if meta and meta.get("content", "").strip():
                result["info"] = meta["content"].strip()[:300]
            if not result["info"]:
                for tag in soup.find_all(["p", "h2", "h3"]):
                    txt = tag.get_text(" ", strip=True)
                    if len(txt) > 40:
                        result["info"] = txt[:300]
                        break

            # CNPJ — homepage primeiro
            cnpj = extrair_cnpj(html)

            # Páginas internas se ainda não achou
            if not cnpj:
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                for slug in ["/contato", "/contact", "/sobre", "/about", "/fale-conosco"]:
                    try:
                        r2 = await client.get(base + slug)
                        cnpj = extrair_cnpj(r2.text)
                        if cnpj:
                            break
                    except Exception:
                        pass

            result["cnpj"] = cnpj

    except Exception:
        pass
    return result
