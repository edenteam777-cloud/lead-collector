"""Instagram — leitura best-effort do perfil público, sem login.

Instagram bloqueia boa parte do scraping deslogado; quando isso acontece
retornamos apenas 'disponivel': False em vez de lançar exceção, para que o
Claude Agent simplesmente siga sem esse dado (mesmo padrão das outras tools).
"""
import re
import httpx
from bs4 import BeautifulSoup
from config import HEADERS, SCRAPING_TIMEOUT


def _extrair_username(username_ou_nome: str) -> str:
    v = username_ou_nome.strip().lstrip("@")
    m = re.search(r"instagram\.com/([A-Za-z0-9._]{2,30})", v)
    if m:
        return m.group(1)
    return re.sub(r"\s+", "", v)


async def buscar_instagram(username_ou_nome: str) -> dict:
    """Retorna {'disponivel', 'username', 'bio', 'seguidores', 'posts'}."""
    username = _extrair_username(username_ou_nome)
    result = {"disponivel": False, "username": username, "bio": "", "seguidores": None, "posts": None}
    if not username:
        return result

    url = f"https://www.instagram.com/{username}/"
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=SCRAPING_TIMEOUT,
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return result
            soup = BeautifulSoup(r.text, "html.parser")

            meta = soup.find("meta", attrs={"property": "og:description"})
            desc = (meta.get("content", "") if meta else "").strip()
            if not desc:
                return result

            # Formato típico: "1.234 Followers, 56 Following, 78 Posts - ..."
            m = re.search(
                r"([\d.,mMkK]+)\s*(?:Followers|seguidores).*?([\d.,mMkK]+)\s*(?:Following|seguindo).*?([\d.,mMkK]+)\s*(?:Posts|publicações)",
                desc, re.I,
            )
            if m:
                result["seguidores"] = m.group(1)
                result["posts"] = m.group(3)
                result["disponivel"] = True

            bio_m = re.search(r"-\s*(.+)$", desc)
            if bio_m:
                result["bio"] = bio_m.group(1).strip()[:300]
                result["disponivel"] = True

    except Exception:
        pass
    return result
