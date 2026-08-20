"""Claude Agent — qualificação inteligente de leads MORNO e QUENTE."""
import json
import re
from pathlib import Path
from agent.tools import TOOLS, executar_tool


def _load_system_prompt() -> str:
    p = Path(__file__).parent / "system_prompt.txt"
    return p.read_text(encoding="utf-8")


async def qualificar_lead(lead: dict, modo: str = "leve", api_key: str = "") -> dict:
    """
    modo='leve'   → leads MORNO (score 40-69) → máx 3 tool calls
    modo='agente' → leads QUENTE (score 70+)  → máx 5 tool calls
    """
    if not api_key:
        from config import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY
    if not api_key:
        return {"erro": "ANTHROPIC_API_KEY não configurada"}

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    max_tokens = 1500 if modo == "leve" else 2500
    max_calls  = 3    if modo == "leve" else 5

    instrucao = (
        "Modo LEVE: confirme dados críticos faltantes com no máximo 3 buscas."
        if modo == "leve"
        else "Modo AGENTE: pesquise profundamente os gaps. Seja cirúrgico e eficiente."
    )

    messages = [{
        "role": "user",
        "content": (
            f"{instrucao}\n\n"
            f"Qualifique este lead para a Eden Technology:\n\n"
            f"{json.dumps(lead, ensure_ascii=False, indent=2)}"
        ),
    }]

    system_prompt    = _load_system_prompt()
    tool_calls_count = 0
    max_rounds       = max_calls + 3

    for _ in range(max_rounds):
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=max_tokens,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            texto = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            # Remove blocos markdown ```json ... ``` se presentes
            texto_limpo = re.sub(r"```(?:json)?\s*", "", texto).strip().rstrip("`").strip()
            try:
                return json.loads(texto_limpo)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", texto_limpo, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group())
                    except Exception:
                        pass
                return {"erro": "JSON inválido", "resposta_raw": texto[:500]}

        # Tool use
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if tool_calls_count >= max_calls:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "LIMITE DE BUSCAS ATINGIDO. Conclua com os dados disponíveis.",
                    })
                else:
                    resultado = await executar_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": resultado,
                    })
                    tool_calls_count += 1

        if not tool_results:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})

    return {"erro": "limite de rodadas atingido"}
