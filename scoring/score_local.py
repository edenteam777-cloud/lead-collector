"""Score local por regras — alinhado ao ICP oficial da Eden (skill analise-leads-eden).

5 dimensões (25/20/20/20/15 = 100), gates duros antes de pontuar,
cortes de tier configuráveis via config.py (SCORE_THRESHOLD_*).
"""
from config import SCORE_THRESHOLD_MORNO, SCORE_THRESHOLD_QUENTE

NICHOS_ALTA_AFINIDADE = [
    "salao", "salão", "barbearia", "estetica", "estética",
    "clinica", "clínica", "odonto",
    "pousada", "hotel", "hostel",
    "academia", "fitness", "pilates", "yoga",
    "restaurante", "lanchonete", "pizzaria",
    "pet", "veterinari",
    "escola", "colegio", "colégio",
]

NICHOS_MEDIA_AFINIDADE = [
    "loja", "varejo", "comercio", "comércio",
    "oficina", "mecanica", "mecânica", "autopeças",
    "contabil", "contábil", "escritorio", "escritório",
    "advocacia", "advocac",
    "farmacia", "farmácia",
    "padaria", "curso", "ensino", "médic", "medic",
]

_METROPOLES = {
    "sao paulo", "são paulo", "rio de janeiro", "belo horizonte", "brasilia",
    "brasília", "salvador", "fortaleza", "curitiba", "porto alegre",
    "recife", "manaus", "belem", "belém", "goiania", "goiânia", "campinas",
}


def _safe(val, default):
    return val if val is not None else default


def _score_segmento(nicho: str) -> int:
    n = nicho.lower()
    if any(k in n for k in NICHOS_ALTA_AFINIDADE):
        return 25
    if any(k in n for k in NICHOS_MEDIA_AFINIDADE):
        return 15
    return 8 if n.strip() else 0


def _score_tempo(tempo_anos) -> int:
    if not isinstance(tempo_anos, (int, float)):
        return 8  # neutro — dado não informado
    if tempo_anos >= 3:
        return 20
    if tempo_anos >= 1:
        return 14
    if tempo_anos >= 0.5:
        return 8
    return 0


def _score_porte(porte: str, ticket_medio) -> int:
    porte = (porte or "").upper()
    base = {"ME": 15, "EPP": 15, "MEI": 8}.get(porte, 8)  # 8 = neutro se não informado
    if isinstance(ticket_medio, str) and ticket_medio.strip():
        # Nível de preço do Maps (ex.: "$$$", "R$$$"): quanto mais símbolos, maior o ticket
        nivel = ticket_medio.count("$")
        if nivel >= 3:
            base += 5
        elif nivel == 2:
            base += 2
    return min(base, 20)


def _score_presenca_dor(lead: dict) -> int:
    pontos = 0
    if not lead.get("tem_site"):
        pontos += 12
    nota = lead.get("nota_maps")
    if isinstance(nota, (int, float)):
        if nota < 3.5:
            pontos += 8
        elif nota < 4.0:
            pontos += 4
    num_reviews = lead.get("num_reviews")
    if isinstance(num_reviews, int) and num_reviews > 50:
        pontos += 4
    return min(pontos, 20)


def _score_localizacao(cidade: str) -> int:
    c = (cidade or "").strip().lower()
    if not c:
        return 8  # neutro — não informado
    if c in _METROPOLES:
        return 7
    return 15  # interior/cidade turística/cidade média — tratamos como oportunidade


def calcular_score(lead: dict) -> tuple[int, str]:
    # ── GATES DUROS (Passo 0 do ICP — barram antes de pontuar) ─────────────────
    if _safe(lead.get("funcionarios"), 0) > 50:
        return 0, "FORA_ICP"
    if lead.get("usa_erp_robusto"):
        return 0, "FORA_ICP"
    if lead.get("cnpj_ativo") is False:
        return 0, "CNPJ_INATIVO"
    if (lead.get("porte") or "").upper() == "MEDIO":
        # BrasilAPI classifica como "DEMAIS" (mapeado para MEDIO) empresas fora
        # da faixa MEI/ME/EPP — proxy real de "muito grande" que temos disponível,
        # já que o Maps não entrega número de funcionários.
        return 0, "FORA_ICP"
    tempo = lead.get("tempo_empresa_anos")
    if isinstance(tempo, (int, float)) and tempo < 0.5:
        return 0, "FORA_ICP"

    # ── PONTUAÇÃO — 5 dimensões (25/20/20/20/15) ────────────────────────────────
    score = 0
    score += _score_segmento(lead.get("nicho") or "")
    score += _score_tempo(tempo)
    score += _score_porte(lead.get("porte") or "", lead.get("ticket_medio"))
    score += _score_presenca_dor(lead)
    score += _score_localizacao(lead.get("cidade") or "")

    # ── TIER FINAL ────────────────────────────────────────────────────────────
    if score >= SCORE_THRESHOLD_QUENTE:
        tier = "QUENTE"
    elif score >= SCORE_THRESHOLD_MORNO:
        tier = "MORNO"
    else:
        tier = "FRIO"

    return score, tier
