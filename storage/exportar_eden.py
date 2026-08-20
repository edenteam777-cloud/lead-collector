"""Exporta leads capturados para o Eden OS (marketing + comercial) e notifica o cérebro."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

EDEN_OS = Path(os.environ.get(
    "EDEN_OS_PATH",
    r"C:\Users\brasi\Desktop\EdenOs\eden-os\eden-os"
))
RELATAR          = EDEN_OS / "_comum" / "skills" / "relatar" / "scripts" / "relatar.py"
MARKETING_LEADS  = EDEN_OS / "marketing" / "leads"
COMERCIAL_LEADS  = EDEN_OS / "comercial" / "leads"

_TIER_ICON = {"QUENTE": "🔥", "MORNO": "🌡", "FRIO": "❄️", "FORA_ICP": "⛔"}


def _fmt_lead(lead: dict) -> str:
    tier     = lead.get("tier", "FRIO")
    score    = lead.get("score_final") or lead.get("score_local") or 0
    urgencia = lead.get("urgencia", "NUTRIR")

    dores = lead.get("dores", "[]")
    if isinstance(dores, str):
        try:
            dores = json.loads(dores)
        except Exception:
            dores = [dores] if dores else []
    dores_txt = "\n".join(f"  - {d}" for d in dores) if dores else "  —"

    abordagem = lead.get("abordagem", "{}")
    if isinstance(abordagem, str):
        try:
            abordagem = json.loads(abordagem)
        except Exception:
            abordagem = {}
    abertura = abordagem.get("abertura", "") if isinstance(abordagem, dict) else ""

    contatos = " | ".join(filter(None, [
        lead.get("telefone", ""),
        lead.get("email", ""),
        f"@{lead.get('instagram','').lstrip('@')}" if lead.get("instagram") else "",
        lead.get("site", ""),
    ]))

    icon = _TIER_ICON.get(tier, "")
    lines = [
        f"### {icon} {lead.get('nome', '?')} — {lead.get('cidade', '')}",
        f"- **Score:** {score} | **Urgência:** {urgencia}",
        f"- **CNPJ:** {lead.get('cnpj') or '—'} | **Porte:** {lead.get('porte') or '—'}",
        f"- **Contato:** {contatos or '—'}",
        f"- **Dores identificadas:**\n{dores_txt}",
        f"- **Oportunidade Eden:** {lead.get('oportunidade') or '—'}",
        f"- **Resumo:** {lead.get('resumo') or '—'}",
    ]
    if abertura:
        lines.append(f"- **Abertura sugerida:** {abertura}")
    lines.append("")
    return "\n".join(lines)


def exportar(leads: list, nicho: str, local: str) -> None:
    if not leads:
        return

    ts       = datetime.now()
    ts_str   = ts.strftime("%Y-%m-%d-%H%M")
    data_str = ts.strftime("%Y-%m-%dT%H:%M")

    quentes   = [l for l in leads if l.get("tier") == "QUENTE"]
    mornos    = [l for l in leads if l.get("tier") == "MORNO"]
    frios     = [l for l in leads if l.get("tier") not in ("QUENTE", "MORNO")]
    imediatos = [l for l in leads if l.get("urgencia") == "IMEDIATO"]

    partes = [
        "---",
        f"data: {data_str}",
        f"nicho: {nicho}",
        f"local: {local}",
        f"total: {len(leads)}",
        f"quentes: {len(quentes)}",
        f"mornos: {len(mornos)}",
        f"imediatos: {len(imediatos)}",
        "---",
        "",
        f"# Leads capturados — {nicho} · {local}",
        f"> Gerado pelo Eden Leads em {data_str}",
        "",
    ]

    if imediatos:
        partes += [f"⚡ **{len(imediatos)} lead(s) IMEDIATO(S)** — prioridade máxima!", ""]

    for titulo, grupo in [
        (f"🔥 QUENTE ({len(quentes)} leads)", quentes),
        (f"🌡 MORNO ({len(mornos)} leads)", mornos),
        (f"❄️ FRIO / FORA ICP ({len(frios)} leads)", frios),
    ]:
        if grupo:
            partes += [f"## {titulo}", ""]
            partes += [_fmt_lead(l) for l in grupo]

    conteudo      = "\n".join(partes)
    nome_arquivo  = f"{ts_str}-{nicho.replace(' ', '-').lower()}.md"

    for pasta in (MARKETING_LEADS, COMERCIAL_LEADS):
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / nome_arquivo).write_text(conteudo, encoding="utf-8")

    _notificar_cerebro(leads, quentes, mornos, imediatos, nicho, local, nome_arquivo)


def _notificar_cerebro(leads, quentes, mornos, imediatos, nicho, local, nome_arquivo):
    if not RELATAR.exists():
        return

    atividade = (
        f"{len(leads)} leads capturados para '{nicho}' em {local}: "
        f"{len(quentes)} quentes, {len(mornos)} mornos"
        + (f", {len(imediatos)} imediatos" if imediatos else "")
        + f". Arquivo: marketing/leads/{nome_arquivo}"
    )
    if quentes:
        resultado = (
            "Leads exportados para marketing/leads/ e comercial/leads/. "
            "Top quentes: " + ", ".join(l.get("nome", "?") for l in quentes[:3])
        )
    else:
        resultado = "Leads exportados. Nenhum QUENTE nesta rodada."

    proximo = (
        "Acionar agente-comercial para leads QUENTE/IMEDIATO. "
        "Agente-marketing pode usar para criação de conteúdo segmentado."
    )

    subprocess.run(
        [sys.executable, str(RELATAR),
         "--agente",    "captacao-leads",
         "--atividade", atividade,
         "--area",      "comercial",
         "--status",    "ok",
         "--resultado", resultado,
         "--proximo",   proximo],
        capture_output=True,
    )
