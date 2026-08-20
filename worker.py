"""Orquestrador principal — Google Maps → BrasilAPI → Score → Claude Agent."""
import asyncio
import re
from scoring.score_local import calcular_score
from storage.db import ja_existe, salvar_lead
from sources.brasil_api import consultar_brasil_api
from sources.site_scraper import scrape_site
from sources.duckduckgo import buscar_cnpj
from agent.pesquisador import qualificar_lead
from config import MAX_CONCURRENT_LEADS, MAX_CONCURRENT_IA


def _chave(lead: dict) -> str:
    cnpj = re.sub(r"\D", "", lead.get("cnpj", ""))
    if cnpj:
        return cnpj
    nome  = re.sub(r"\s+", " ", lead.get("nome", "")).lower().strip()
    cidade = lead.get("cidade", "").lower().strip()
    return f"{nome}|{cidade}"


async def processar_lead(
    lead_bruto: dict,
    anthropic_key: str = "",
    log_fn=None,
    ia_semaphore: asyncio.Semaphore = None,
) -> dict:
    def log(msg):
        if log_fn:
            log_fn(msg)

    chave = _chave(lead_bruto)
    if ja_existe(chave):
        log(f"   ⏭️  {lead_bruto.get('nome','')[:40]} — duplicado, pulando")
        return {"status": "duplicado"}

    nome   = lead_bruto.get("nome", "")
    site   = lead_bruto.get("site", "")
    cidade = lead_bruto.get("cidade", "") or lead_bruto.get("local", "")
    cnpj_raw = re.sub(r"\D", "", lead_bruto.get("cnpj", ""))

    log(f"   ⚙️  Enriquecendo: {nome[:38]}")

    # Paralelo: site (CNPJ + info) e DDG (CNPJ)
    tasks = {}
    if site:
        tasks["site"] = scrape_site(site)
    tasks["ddg"] = buscar_cnpj(nome, cidade)

    resultados = await asyncio.gather(*tasks.values(), return_exceptions=True)
    dados = {
        k: (v if not isinstance(v, Exception) else ({} if k == "site" else ""))
        for k, v in zip(tasks.keys(), resultados)
    }

    site_d = dados.get("site") or {}
    ddg_cnpj = dados.get("ddg") or ""

    # Resolve CNPJ: Maps > site > DDG
    cnpj = cnpj_raw or site_d.get("cnpj", "") or ddg_cnpj

    # BrasilAPI
    brasil = {}
    if cnpj:
        log(f"   🏛️  BrasilAPI: {cnpj}")
        try:
            brasil = await consultar_brasil_api(cnpj)
        except Exception as e:
            log(f"   [!] BrasilAPI erro: {e}")

    # Monta lead
    lead = dict(lead_bruto)
    lead["tem_site"] = bool(site)
    lead["info_empresa"] = site_d.get("info", "")

    if brasil:
        lead["cnpj"]               = brasil.get("cnpj_fmt", cnpj)
        lead["porte"]              = brasil.get("porte", "")
        lead["tempo_empresa_anos"] = brasil.get("tempo_empresa_anos")
        lead["data_abertura"]      = brasil.get("data_abertura", "")
        lead["cnpj_ativo"]         = brasil.get("cnpj_ativo", True)
        if not lead.get("cidade"):
            lead["cidade"] = brasil.get("cidade", "")
        if not lead.get("estado"):
            lead["estado"] = brasil.get("estado", "")
    elif cnpj:
        lead["cnpj"] = cnpj

    lead["chave"] = _chave(lead)

    # Score local
    try:
        score, tier = calcular_score(lead)
    except Exception as e:
        log(f"   [!] Erro no score de {nome[:30]}: {e}")
        score, tier = 0, "FRIO"
    lead["score_local"] = score
    lead["tier_local"]  = tier
    lead["tier"]        = tier

    log(f"   📊 Score: {score} ({tier}) | CNPJ: {'✓' if brasil else '—'} | Site: {'✓' if site else '—'}")

    lead["qualificacao_ia"] = None
    lead["score_final"]     = score
    lead["urgencia"]        = "IMEDIATO" if tier == "QUENTE" else ("NUTRIR" if tier == "MORNO" else "DESCARTAR")

    # Qualificação por IA — só para leads com potencial real (score local decide, IA não recalcula do zero)
    if tier in ("MORNO", "QUENTE"):
        modo = "leve" if tier == "MORNO" else "agente"
        log(f"   🤖 Qualificando com IA ({modo}): {nome[:35]}")
        try:
            sem = ia_semaphore or asyncio.Semaphore(MAX_CONCURRENT_IA)
            async with sem:
                qualif = await qualificar_lead(lead, modo=modo, api_key=anthropic_key)

            if qualif.get("erro"):
                log(f"   [!] IA não qualificou {nome[:30]}: {qualif['erro']}")
            else:
                lead["qualificacao_ia"] = qualif
                if qualif.get("alertas"):
                    log(f"   ⚠️  Alertas da IA: {'; '.join(qualif['alertas'])}")
                # A IA só sobrepõe o tier local quando descobre um gate duro
                # que os dados brutos não permitem checar (ex.: já usa ERP robusto).
                override = qualif.get("override_tier")
                if override in ("QUENTE", "MORNO", "FRIO", "FORA_ICP") and override != tier:
                    log(f"   ⚠️  IA sobrepôs tier: {tier} → {override}")
                    lead["tier_final"] = override
                    lead["tier"]       = override
                    lead["urgencia"]   = (
                        "IMEDIATO" if override == "QUENTE"
                        else "NUTRIR" if override == "MORNO"
                        else "DESCARTAR"
                    )
        except Exception as e:
            log(f"   [!] Erro na qualificação IA de {nome[:30]}: {e}")

    try:
        salvar_lead(lead)
    except Exception as e:
        log(f"   [!] Erro ao salvar {nome[:30]}: {e}")
    log(f"   ✅ {lead['tier']} {score}/100 | {lead['urgencia']}")
    return lead


async def processar_lote(
    leads_brutos: list,
    anthropic_key: str = "",
    log_fn=None,
    result_fn=None,
) -> list:
    semaphore    = asyncio.Semaphore(MAX_CONCURRENT_LEADS)
    ia_semaphore = asyncio.Semaphore(MAX_CONCURRENT_IA)

    async def _processar(lead):
        async with semaphore:
            try:
                resultado = await processar_lead(
                    lead, anthropic_key=anthropic_key, log_fn=log_fn, ia_semaphore=ia_semaphore
                )
                if result_fn and resultado.get("status") != "duplicado":
                    result_fn(resultado)
                return resultado
            except Exception as exc:
                import traceback
                msg = f"   [!] Erro em {lead.get('nome','?')[:30]}: {exc}\n{traceback.format_exc()[-300:]}"
                if log_fn:
                    log_fn(msg)
                erro_lead = {
                    **lead,
                    "status": "erro",
                    "tier": "FRIO",
                    "score_local": 0,
                    "score_final": 0,
                    "urgencia": "NUTRIR",
                    "resumo": f"Erro: {exc}",
                }
                if result_fn:
                    result_fn(erro_lead)
                return erro_lead

    return await asyncio.gather(
        *[_processar(lead) for lead in leads_brutos],
        return_exceptions=True,
    )
