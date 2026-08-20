"""Definição e execução das tools do Claude Agent."""
import asyncio
from sources.duckduckgo   import buscar_duckduckgo
from sources.site_scraper import scrape_site
from sources.brasil_api   import consultar_brasil_api
from sources.instagram_scraper import buscar_instagram
from sources.site_analyzer import analisar_site


TOOLS = [
    {
        "name": "buscar_web",
        "description": (
            "Busca informações sobre a empresa na web via DuckDuckGo. "
            "Use para encontrar: email, Instagram, notícias recentes, "
            "menções, expansões, contratações, problemas relatados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Busca específica. Ex: 'Clínica X Ubatuba reclamações'"
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "scrape_url",
        "description": (
            "Extrai conteúdo de uma URL específica. "
            "Use para ler o site da empresa, página do Instagram ou Reclame Aqui."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL completa com https://"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "consultar_cnpj",
        "description": "Busca dados oficiais da Receita Federal pelo CNPJ via BrasilAPI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cnpj": {"type": "string", "description": "CNPJ apenas números, 14 dígitos"}
            },
            "required": ["cnpj"],
        },
    },
    {
        "name": "buscar_instagram",
        "description": (
            "Busca e analisa perfil do Instagram da empresa. "
            "Retorna: seguidores, posts, último post, bio, ativo?"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username_ou_nome": {"type": "string"}
            },
            "required": ["username_ou_nome"],
        },
    },
    {
        "name": "checar_site_tecnico",
        "description": (
            "Analisa tecnicamente o site da empresa. "
            "Retorna: tecnologia (WordPress/Wix/Shopify/HTML), "
            "tem SSL, tem formulário de contato, tem WhatsApp button."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"}
            },
            "required": ["url"],
        },
    },
]


async def executar_tool(nome: str, params: dict) -> str:
    import json
    try:
        if nome == "buscar_web":
            resultado = await buscar_duckduckgo(params["query"])
            return json.dumps(resultado, ensure_ascii=False)
        elif nome == "scrape_url":
            resultado = await scrape_site(params["url"])
            return json.dumps(resultado, ensure_ascii=False)
        elif nome == "consultar_cnpj":
            resultado = await consultar_brasil_api(params["cnpj"])
            return json.dumps(resultado, ensure_ascii=False)
        elif nome == "buscar_instagram":
            resultado = await buscar_instagram(params["username_ou_nome"])
            return json.dumps(resultado, ensure_ascii=False)
        elif nome == "checar_site_tecnico":
            resultado = await analisar_site(params["url"])
            return json.dumps(resultado, ensure_ascii=False)
        else:
            return f"Tool '{nome}' não encontrada"
    except Exception as e:
        return f"Erro ao executar {nome}: {str(e)}"
