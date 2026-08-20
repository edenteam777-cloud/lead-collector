"""DuckDuckGo — busca focada em CNPJ para alimentar a BrasilAPI, e busca geral para o Claude Agent."""
import re
import httpx
from bs4 import BeautifulSoup
from config import HEADERS, SCRAPING_TIMEOUT
from sources.brasil_api import extrair_cnpj


async def buscar_duckduckgo(query: str, max_resultados: int = 5) -> dict:
    """Busca geral na web — usada pela tool 'buscar_web' do Claude Agent.
    Retorna {'resultados': [{'titulo','trecho','url'}, ...]}. Nunca lança exceção."""
    resultado = {"resultados": []}
    if not query.strip():
        return resultado
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=SCRAPING_TIMEOUT,
            follow_redirects=True,
        ) as client:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "br-pt"},
            )
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select("div.result")[:max_resultados]:
                link = item.select_one("a.result__a")
                trecho = item.select_one("a.result__snippet") or item.select_one(".result__snippet")
                if not link:
                    continue
                resultado["resultados"].append({
                    "titulo": link.get_text(" ", strip=True),
                    "url": link.get("href", ""),
                    "trecho": trecho.get_text(" ", strip=True) if trecho else "",
                })
    except Exception:
        pass
    return resultado


async def buscar_cnpj(nome: str, cidade: str) -> str:
    """Tenta encontrar o CNPJ da empresa via DuckDuckGo. Retorna string de 14 dígitos ou ''."""
    queries = [
        f'"{nome}" "{cidade}" CNPJ',
        f'"{nome}" {cidade} CNPJ site:casadosdados.com.br OR site:cnpj.biz OR site:cnpja.com.br',
    ]
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=SCRAPING_TIMEOUT,
            follow_redirects=True,
        ) as client:
            for query in queries:
                r = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query, "kl": "br-pt"},
                )
                cnpj = extrair_cnpj(BeautifulSoup(r.text, "html.parser").get_text(" "))
                if cnpj:
                    return cnpj
    except Exception:
        pass
    return ""
