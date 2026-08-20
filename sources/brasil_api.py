"""BrasilAPI — CNPJ, porte, data abertura, atividade."""
import re
import httpx
from datetime import datetime
from config import HEADERS, SCRAPING_TIMEOUT

CNPJ_RE = re.compile(r'\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\s\/]?\d{4}[\s\-]?\d{2}')


def _fmt(cnpj: str) -> str:
    d = re.sub(r"\D", "", cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else cnpj


async def consultar_brasil_api(cnpj: str) -> dict:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        return {}
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=SCRAPING_TIMEOUT) as client:
            r = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{digits}")
            if r.status_code != 200:
                return {}
            d = r.json()

        resultado = {"cnpj_fmt": _fmt(digits), "cnpj_ativo": True}

        abertura = d.get("data_abertura", "")
        if abertura:
            try:
                ano = int(abertura.split("-")[0]) if "-" in abertura else int(abertura.split("/")[-1])
                if 1900 <= ano <= datetime.now().year:
                    anos = datetime.now().year - ano
                    resultado["data_abertura"]      = abertura
                    resultado["tempo_empresa_anos"] = anos
                    resultado["tempo_empresa_txt"]  = f"{anos} ano{'s' if anos!=1 else ''} (desde {ano})"
            except Exception:
                pass

        porte_raw = (d.get("porte") or "").upper()
        porte_map = {"MEI": "MEI", "ME": "ME", "EPP": "EPP", "DEMAIS": "MEDIO"}
        resultado["porte"] = porte_map.get(porte_raw, porte_raw.title())

        atividades = d.get("descricao_atividade_principal") or []
        if isinstance(atividades, list) and atividades:
            resultado["atividade"] = atividades[0].get("text", "").strip()

        municipio = d.get("municipio", "")
        uf        = d.get("uf", "")
        if municipio:
            resultado["cidade"]  = municipio.title()
            resultado["estado"]  = uf

        situacao = (d.get("descricao_situacao_cadastral") or "").upper()
        resultado["cnpj_ativo"] = situacao in ("", "ATIVA", "ATIVO")

        return resultado
    except Exception:
        return {}


def extrair_cnpj(texto: str) -> str:
    m = CNPJ_RE.search(texto)
    if not m:
        return ""
    d = re.sub(r"\D", "", m.group())
    return d if len(d) == 14 else ""
