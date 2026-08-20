import streamlit as st
import threading
import queue
import asyncio
import time
import re

from output.excel import gerar_excel
from storage.db   import total_leads, carregar_todos

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Eden — Captação de Leads", page_icon="🎯", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{ font-family:'Inter',sans-serif; }
.hero{
    background:linear-gradient(135deg,#1F4E79 0%,#2E86C1 100%);
    border-radius:16px;padding:2rem 2rem 1.5rem;text-align:center;
    margin-bottom:1.5rem;box-shadow:0 4px 24px rgba(31,78,121,.18);
}
.hero h1{color:#fff;font-size:2.2rem;font-weight:700;margin:0;}
.hero p{color:#D6EAF8;font-size:.95rem;margin-top:.4rem;}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
      border-radius:12px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;}
.stat-box{background:#1F4E79;color:#fff;border-radius:10px;padding:.9rem;text-align:center;}
.stat-box .num{font-size:1.8rem;font-weight:700;}
.stat-box .lbl{font-size:.75rem;opacity:.8;}
.log-box{background:#0d1117;color:#58a6ff;border-radius:10px;padding:1rem 1.2rem;
         font-family:monospace;font-size:.82rem;max-height:280px;overflow-y:auto;
         white-space:pre-wrap;line-height:1.6;}
.tier-q{background:#E8F5E9;color:#1E8449;font-weight:700;padding:2px 8px;border-radius:4px;}
.tier-m{background:#FFF9C4;color:#8a6d00;font-weight:700;padding:2px 8px;border-radius:4px;}
.tier-f{background:#F5F5F5;color:#555;font-weight:700;padding:2px 8px;border-radius:4px;}
div[data-testid="stButton"]>button{
    width:100%;background:linear-gradient(90deg,#1F4E79,#2E86C1);color:white;
    border:none;border-radius:8px;padding:.7rem 1.4rem;font-size:.95rem;
    font-weight:600;cursor:pointer;transition:opacity .2s;
}
div[data-testid="stButton"]>button:hover{opacity:.88;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🎯 Eden Technology — Captação de Leads</h1>
    <p>Pipeline inteligente: coleta massiva + score local + Claude Agent para qualificação profunda</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "running": False, "leads": [], "logs": [],
    "done": False, "excel_bytes": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Memória persistente
_total = total_leads()
if _total > 0:
    col_h1, col_h2 = st.columns([3,1])
    with col_h1:
        st.info(f"💾 **Banco de dados:** {_total} empresa(s) já qualificadas — duplicatas ignoradas automaticamente.")
    with col_h2:
        if st.button("🗑️ Limpar banco"):
            from storage.db import limpar_banco
            limpar_banco()
            st.success("Banco apagado!")
            st.rerun()

# ── Tabela de resultados ───────────────────────────────────────────────────────
TIER_BADGE = {
    "QUENTE":   '<span class="tier-q">🔥 QUENTE</span>',
    "MORNO":    '<span class="tier-m">🌡 MORNO</span>',
    "FRIO":     '<span class="tier-f">❄️ FRIO</span>',
    "FORA_ICP": '<span class="tier-f">⛔ FORA ICP</span>',
}

def _tabela(leads):
    rows = []
    for i, l in enumerate(leads, 1):
        tier  = l.get("tier", "FRIO")
        score = l.get("score_final") or l.get("score_local") or ""
        badge = TIER_BADGE.get(tier, tier)
        rows.append(
            f"<tr>"
            f"<td style='padding:5px 8px;border:1px solid #ddd;color:#888'>{i}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('nome','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{badge}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd;text-align:center'><b>{score}</b></td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('urgencia','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('telefone','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('email','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('instagram','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd'>{l.get('cidade','')}</td>"
            f"<td style='padding:5px 10px;border:1px solid #ddd;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{l.get('resumo','')[:80]}</td>"
            f"</tr>"
        )
    header = "".join(
        f"<th style='padding:6px 10px;background:#1F4E79;color:white;border:1px solid #1a4268;white-space:nowrap'>{h}</th>"
        for h in ["#","Nome","Tier","Score","Urgência","Telefone","E-mail","Instagram","Cidade","Resumo"]
    )
    return (
        "<div style='overflow-x:auto;max-height:440px;overflow-y:auto'>"
        f"<table style='border-collapse:collapse;font-size:12.5px;width:100%'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )

# ── Formulário ─────────────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### ⚙️ Configurar busca")

col1, col2 = st.columns(2)
with col1:
    nicho = st.text_input("Nicho / Segmento", placeholder="Ex: clínica odontológica")
with col2:
    local = st.text_input("Cidade / Região", value="São Paulo", placeholder="Ex: Ubatuba - SP")

num_leads = st.slider("Quantidade máxima de leads", 5, 200, 30, 5)

iniciar = st.button("🚀 Iniciar captação", disabled=st.session_state.running)
st.markdown('</div>', unsafe_allow_html=True)

# ── Worker thread ──────────────────────────────────────────────────────────────
def _worker_thread(nicho, local, max_leads, log_q, result_q):
    try:
        from sources.google_maps import coletar_google_maps
        from worker import processar_lote

        def log(msg): log_q.put(msg)

        log("🗺️  Coletando empresas no Google Maps...")
        leads_brutos = coletar_google_maps(nicho, local, max_leads, log)

        log(f"\n⚙️  Enriquecendo {len(leads_brutos)} empresas (BrasilAPI + CNPJ)...\n")

        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)

        leads_finais = []

        def _on_result(lead):
            leads_finais.append(lead)
            result_q.put(("lead", lead))

        loop2.run_until_complete(
            processar_lote(
                [{**l, "nicho": nicho, "local": local} for l in leads_brutos],
                log_fn=log,
                result_fn=_on_result,
            )
        )
        loop2.close()

        result_q.put(("done", leads_finais))

    except Exception as e:
        import traceback
        log_q.put(f"❌ Erro fatal: {e}\n{traceback.format_exc()[:600]}")
        result_q.put(("done", []))

# ── Execução ───────────────────────────────────────────────────────────────────
if iniciar:
    if not nicho.strip():
        st.error("Informe o nicho antes de iniciar.")
    else:
        st.session_state.update(
            running=True, leads=[], logs=[], done=False,
            excel_bytes=None, pdf_bytes=None,
        )
        log_q    = queue.Queue()
        result_q = queue.Queue()
        worker_t = threading.Thread(
            target=_worker_thread,
            args=(nicho.strip(), local.strip(), num_leads, log_q, result_q),
            daemon=True,
        )
        worker_t.start()

        prog_bar  = st.progress(0, text="Iniciando…")
        log_ph    = st.empty()
        leads_ph  = st.empty()
        MAX_WAIT  = 1800  # 30 min timeout máximo
        elapsed   = 0

        while elapsed < MAX_WAIT:
            while not log_q.empty():
                st.session_state.logs.append(log_q.get())
            while not result_q.empty():
                kind, data = result_q.get()
                if kind == "lead":
                    st.session_state.leads.append(data)
                elif kind == "done":
                    st.session_state.done = True

            n   = len(st.session_state.leads)
            pct = min(int(n / max(num_leads, 1) * 100), 99)
            prog_bar.progress(pct, text=f"{n} lead(s) qualificado(s)…")
            log_ph.markdown(
                f'<div class="log-box">{"<br>".join(st.session_state.logs[-70:])}</div>',
                unsafe_allow_html=True,
            )
            if st.session_state.leads:
                leads_ph.markdown(_tabela(st.session_state.leads), unsafe_allow_html=True)
            if st.session_state.done:
                break
            if not worker_t.is_alive() and result_q.empty():
                st.session_state.done = True
                break
            time.sleep(1)
            elapsed += 1

        prog_bar.progress(100, text="Concluído!")
        st.session_state.running = False
        if st.session_state.leads:
            st.session_state.excel_bytes = gerar_excel(
                st.session_state.leads, nicho.strip(), local.strip()
            )
            try:
                from storage.exportar_eden import exportar as _exportar_eden
                _exportar_eden(st.session_state.leads, nicho.strip(), local.strip())
            except Exception:
                pass  # nunca bloqueia a UI por falha no export

# ── Resultados ─────────────────────────────────────────────────────────────────
if st.session_state.leads:
    leads  = st.session_state.leads
    n_q    = sum(1 for l in leads if l.get("tier") == "QUENTE")
    n_m    = sum(1 for l in leads if l.get("tier") == "MORNO")
    n_tel  = sum(1 for l in leads if l.get("telefone"))
    n_email= sum(1 for l in leads if l.get("email"))
    n_imdt = sum(1 for l in leads if l.get("urgencia") == "IMEDIATO")

    st.markdown("---")
    st.markdown("### 📊 Resultado da captação")

    cols = st.columns(5)
    for col, num, lbl in zip(
        cols,
        [len(leads), n_q, n_m, n_tel, n_email],
        ["Total", "🔥 Quente", "🌡 Morno", "Com telefone", "Com e-mail"],
    ):
        col.markdown(
            f'<div class="stat-box"><div class="num">{num}</div>'
            f'<div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    if n_imdt:
        st.warning(f"⚡ {n_imdt} lead(s) classificado(s) como **IMEDIATO** — contate hoje!")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(_tabela(leads), unsafe_allow_html=True)

    if not st.session_state.excel_bytes:
        st.session_state.excel_bytes = gerar_excel(leads, nicho, local)

    st.download_button(
        "⬇️  Baixar Excel",
        data=st.session_state.excel_bytes,
        file_name=f"leads_eden_{nicho.replace(' ','_')}_{local.replace(' ','_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

elif st.session_state.done and not st.session_state.leads:
    st.warning("Nenhum lead encontrado. Tente outro nicho ou localidade.")
