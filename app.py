import streamlit as st
import threading
import queue
import io
import time
import sys
import re
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Histórico persistente ──────────────────────────────────────────────────────
_HIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico.json")

def _chave_lead(lead: dict) -> str:
    nome = re.sub(r"\s+", " ", lead.get("nome", "")).lower().strip()
    tel  = re.sub(r"\D", "", lead.get("telefone", ""))
    if tel:
        return f"{nome}|{tel}"
    site = re.sub(r"^https?://(www\.)?", "", lead.get("site", "").lower().rstrip("/"))
    return f"{nome}|{site}"

def carregar_historico() -> dict:
    if os.path.exists(_HIST_PATH):
        try:
            with open(_HIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"chaves": [], "total": 0}

def salvar_historico(hist: dict):
    with open(_HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

# ── Table helper (no pandas) ────────────────────────────────────────────────────
_KEYS  = ["nome", "telefone", "email", "instagram", "site"]
_HEADS = ["#", "Empresa", "Telefone", "E-mail", "Instagram", "Site"]

def _leads_html_table(leads: list) -> str:
    rows = []
    for i, lead in enumerate(leads, 1):
        cells = "".join(
            f"<td style='padding:4px 10px;border:1px solid #ddd;white-space:nowrap'>{lead.get(k, '') or ''}</td>"
            for k in _KEYS
        )
        bg = "#f5f8ff" if i % 2 == 0 else "white"
        rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:4px 8px;border:1px solid #ddd;color:#888;text-align:right'>{i}</td>"
            f"{cells}</tr>"
        )
    header = "".join(
        f"<th style='padding:6px 10px;background:#1F4E79;color:white;border:1px solid #1a4268'>{h}</th>"
        for h in _HEADS
    )
    return (
        "<div style='overflow-x:auto;max-height:420px;overflow-y:auto'>"
        f"<table style='border-collapse:collapse;font-size:13px;width:100%'>"
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Coletor de Leads",
    page_icon="🎯",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .hero {
        background: linear-gradient(135deg, #1F4E79 0%, #2E86C1 100%);
        border-radius: 16px;
        padding: 2.5rem 2rem 2rem 2rem;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 24px rgba(31,78,121,0.18);
    }
    .hero h1 { color: #fff; font-size: 2.4rem; font-weight: 700; margin: 0; }
    .hero p  { color: #D6EAF8; font-size: 1rem; margin-top: .5rem; }

    .card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 1.5rem 1.8rem;
        margin-bottom: 1.4rem;
    }

    .stat-box {
        background: #1F4E79;
        color: #fff;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stat-box .num  { font-size: 2rem; font-weight: 700; }
    .stat-box .lbl  { font-size: .8rem; opacity: .8; }

    .log-box {
        background: #0d1117;
        color: #58a6ff;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        font-family: monospace;
        font-size: .85rem;
        max-height: 260px;
        overflow-y: auto;
        white-space: pre-wrap;
        line-height: 1.6;
    }

    div[data-testid="stButton"] > button {
        width: 100%;
        background: linear-gradient(90deg, #1F4E79, #2E86C1);
        color: white;
        border: none;
        border-radius: 8px;
        padding: .75rem 1.5rem;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: opacity .2s;
    }
    div[data-testid="stButton"] > button:hover { opacity: .88; }

    .tag-ok  { color: #27ae60; font-weight: 600; }
    .tag-err { color: #e74c3c; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🎯 Coletor de Leads</h1>
    <p>Extrai empresas do Google Maps com telefone e e-mail — exporta para Excel em segundos.</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for key, val in {
    "running": False,
    "leads": [],
    "logs": [],
    "done": False,
    "excel_bytes": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Painel de histórico ────────────────────────────────────────────────────────
_hist_info = carregar_historico()
_total_hist = _hist_info.get("total", len(_hist_info.get("chaves", [])))
if _total_hist > 0:
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.info(f"💾 **Memória ativa:** {_total_hist} empresa(s) já coletadas em buscas anteriores — duplicatas serão ignoradas automaticamente.")
    with col_h2:
        if st.button("🗑️ Limpar memória", help="Apaga o histórico e permite coletar as mesmas empresas novamente"):
            salvar_historico({"chaves": [], "total": 0})
            st.success("Histórico apagado!")
            st.rerun()

# ── Helpers ────────────────────────────────────────────────────────────────────

def gerar_excel(leads, nicho, local) -> bytes:
    COR_CAB = "1F4E79"
    COR_PAR = "D9E1F2"

    def borda():
        lado = Side(style="thin", color="AAAAAA")
        return Border(left=lado, right=lado, top=lado, bottom=lado)

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    cols   = ["#", "Nome da Empresa", "Telefone", "Email", "Instagram", "Site"]
    widths = [5, 40, 20, 38, 28, 45]

    for c, (t, w) in enumerate(zip(cols, widths), 1):
        cel = ws.cell(row=1, column=c, value=t)
        cel.font      = Font(bold=True, color="FFFFFF", size=11)
        cel.fill      = PatternFill("solid", fgColor=COR_CAB)
        cel.alignment = Alignment(horizontal="center", vertical="center")
        cel.border    = borda()
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[1].height = 22

    for idx, lead in enumerate(leads, 1):
        row  = idx + 1
        vals = [idx, lead.get("nome",""), lead.get("telefone",""),
                lead.get("email",""), lead.get("instagram",""), lead.get("site","")]
        fill = PatternFill("solid", fgColor=COR_PAR) if idx % 2 == 0 else None
        for c, v in enumerate(vals, 1):
            cel = ws.cell(row=row, column=c, value=v)
            cel.alignment = Alignment(vertical="center")
            cel.border    = borda()
            if fill: cel.fill = fill

    ws.freeze_panes = "A2"
    ws.insert_rows(1)
    ws.merge_cells("A1:F1")
    m = ws["A1"]
    m.value     = f"Leads — {nicho.title()} em {local.title()} | {len(leads)} empresas"
    m.font      = Font(bold=True, size=13, color="1F4E79")
    m.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def worker(nicho, local, max_leads, log_q, result_q):
    """Roda o scraping em thread separada e envia logs/resultados via queues."""
    try:
        # Importações pesadas ficam aqui para não travar o carregamento da UI
        import requests
        from bs4 import BeautifulSoup
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from urllib.parse import urlparse
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        HEADERS = {"User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )}
        EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
        IGNORE   = {"exemplo.com","example.com","seudominio.com","wixpress.com","sentry.io"}
        INSTA_RE = re.compile(r'instagram\.com/([A-Za-z0-9._]{2,30})/?(?:["\s?#]|$)')
        INSTA_SKIP = {"p","reel","reels","explore","accounts","tv","stories","direct","share","about","legal","privacy","security","blog","press","api","developer","_n","sharedfiles"}

        def log(msg):
            log_q.put(msg)

        def limpar_tel(t):
            return re.sub(r"[^\d+()\s\-]", "", t).strip()

        def fmt_url(u):
            if not u: return ""
            return u if u.startswith(("http://","https://")) else "https://"+u

        def extrair_instagram(html):
            for m in INSTA_RE.finditer(html):
                handle = m.group(1).lower()
                if handle not in INSTA_SKIP and not handle.startswith("_"):
                    return "@" + handle
            return ""

        def buscar_contato(url):
            """Retorna (email, instagram) buscando no site da empresa."""
            emails = set()
            instagram = ""
            url = fmt_url(url)
            if not url: return "", ""
            try:
                r = requests.get(url, headers=HEADERS, timeout=8, verify=False, allow_redirects=True)
                soup = BeautifulSoup(r.text, "html.parser")
                # Instagram direto nas âncoras
                for tag in soup.find_all("a", href=True):
                    h = tag["href"]
                    if "instagram.com/" in h and not instagram:
                        instagram = extrair_instagram(h + '"')
                    if h.startswith("mailto:"):
                        e = h.replace("mailto:","").split("?")[0].strip().lower()
                        d = e.split("@")[-1]
                        if "@" in e and d not in IGNORE:
                            emails.add(e)
                # Instagram no HTML geral
                if not instagram:
                    instagram = extrair_instagram(r.text)
                # Emails no texto
                if not emails:
                    for m in EMAIL_RE.findall(r.text):
                        d = m.split("@")[-1].lower()
                        if d not in IGNORE:
                            emails.add(m.lower())
                            break
                # Páginas de contato se ainda falta info
                if not emails or not instagram:
                    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    for slug in ["/contato","/contact","/fale-conosco","/sobre"]:
                        try:
                            r2 = requests.get(base+slug, headers=HEADERS, timeout=8, verify=False)
                            if not emails:
                                for m in EMAIL_RE.findall(r2.text):
                                    d = m.split("@")[-1].lower()
                                    if d not in IGNORE: emails.add(m.lower())
                            if not instagram:
                                instagram = extrair_instagram(r2.text)
                            if emails and instagram: break
                        except: pass
            except: pass
            email = list(emails)[0] if emails else ""
            return email, instagram

        # Driver
        log("🚀 Iniciando navegador...")

        def _chrome_version():
            """Detecta a versão major do Chrome via registro do Windows ou binário."""
            import subprocess
            import re as _re

            # 1) Registro do Windows (mais confiável)
            try:
                import winreg
                for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    for sub in (
                        r"SOFTWARE\Google\Chrome\BLBeacon",
                        r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon",
                    ):
                        try:
                            key = winreg.OpenKey(root, sub)
                            val, _ = winreg.QueryValueEx(key, "version")
                            winreg.CloseKey(key)
                            m = _re.match(r"(\d+)", str(val))
                            if m:
                                return int(m.group(1))
                        except OSError:
                            pass
            except ImportError:
                pass

            # 2) Executável direto
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
            ]
            for p in paths:
                try:
                    out = subprocess.check_output(
                        [p, "--version"], stderr=subprocess.DEVNULL, text=True, timeout=5
                    )
                    m = _re.search(r"(\d+)\.", out)
                    if m:
                        return int(m.group(1))
                except Exception:
                    pass

            return None

        def _build_opts():
            o = uc.ChromeOptions()
            o.add_argument("--no-sandbox")
            o.add_argument("--disable-dev-shm-usage")
            o.add_argument("--disable-blink-features=AutomationControlled")
            o.add_argument("--lang=pt-BR")
            o.add_argument("--headless=new")
            return o

        ver = _chrome_version()
        log(f"   Versão do Chrome detectada: {ver or 'desconhecida'}")

        driver = None
        # Tenta com versão exata primeiro, depois versões vizinhas como fallback
        versions_to_try = []
        if ver:
            versions_to_try = [ver, ver - 1, ver + 1]
        else:
            versions_to_try = [None]  # deixa o uc tentar auto-detectar

        for v in versions_to_try:
            kw = {"version_main": v} if v is not None else {}
            try:
                driver = uc.Chrome(options=_build_opts(), **kw)
                log(f"   Chrome iniciado com version_main={v or 'auto'}")
                break
            except Exception:
                log(f"   version_main={v} falhou, tentando próxima...")
                driver = None

        if driver is None:
            raise RuntimeError(
                f"Não foi possível iniciar o Chrome (versão {ver}). "
                "Atualize o undetected-chromedriver: pip install -U undetected-chromedriver"
            )

        driver.set_window_size(1400, 900)

        query = f"{nicho} em {local}"
        url   = f"https://www.google.com/maps/search/{query.replace(' ','+')}"
        log(f"🗺️  Buscando: {query}")
        driver.get(url)
        time.sleep(3)

        wait      = WebDriverWait(driver, 12)
        n_scrolls = max(10, (max_leads // 5) + 5)
        log(f"⏬ Carregando resultados...")

        # Scroll
        try:
            painel = driver.find_element(
                By.XPATH,
                '//div[contains(@aria-label,"Resultados") or '
                'contains(@aria-label,"Results")][@role="feed"]'
            )
        except: painel = None

        for _ in range(n_scrolls):
            try:
                if painel:
                    driver.execute_script("arguments[0].scrollBy(0, 800);", painel)
                else:
                    driver.find_element(By.TAG_NAME,"body").send_keys(Keys.END)
                time.sleep(2)
            except: break

        # Cards
        cards = []
        for sel in ['a[href*="/maps/place/"]', 'div[role="article"] a[href*="maps"]']:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards: break

        log(f"📋 {len(cards)} empresas encontradas. Coletando detalhes...")

        hist       = carregar_historico()
        chaves_set = set(hist.get("chaves", []))
        leads      = []
        pulados    = 0
        visitados  = set()

        wait_short = WebDriverWait(driver, 5)

        for i, card in enumerate(cards):
            if len(leads) >= max_leads:
                break
            try:
                href = card.get_attribute("href") or ""
                if href in visitados: continue
                visitados.add(href)

                log(f"🔍 [{i+1}/{len(cards)}] Abrindo empresa...")
                driver.execute_script("arguments[0].click();", card)
                time.sleep(3)

                lead = {"nome":"","telefone":"","site":"","email":"","instagram":""}

                for sel in [
                    'h1[class*="fontHeadlineLarge"]',
                    'h1[class*="DUwDvf"]',
                    'h1.DUwDvf',
                    'div[role="main"] h1',
                    'h1',
                ]:
                    try:
                        el = wait_short.until(EC.presence_of_element_located(
                            (By.CSS_SELECTOR, sel)))
                        nome = el.text.strip()
                        if nome:
                            lead["nome"] = nome
                            break
                    except: pass

                if not lead["nome"]: continue

                try:
                    spans = driver.find_elements(By.XPATH,
                        '//button[@data-tooltip="Copiar número de telefone"]'
                        '//div[contains(@class,"fontBodyMedium")]')
                    if not spans:
                        spans = driver.find_elements(By.XPATH,
                            '//*[contains(@aria-label,"Ligue") or contains(@aria-label,"Phone")]')
                    for el in spans:
                        t = limpar_tel(el.get_attribute("aria-label") or el.text)
                        if re.search(r"\d{4,}", t):
                            lead["telefone"] = t; break
                except: pass

                if not lead["telefone"]:
                    try:
                        for btn in driver.find_elements(By.XPATH,'//button[@aria-label]'):
                            lbl = btn.get_attribute("aria-label") or ""
                            if re.search(r"\(\d{2}\)|\+\d{2}|\d{8,}", lbl):
                                lead["telefone"] = limpar_tel(lbl); break
                    except: pass

                try:
                    sb = driver.find_element(By.XPATH,
                        '//a[@data-tooltip="Abrir site" or @data-item-id="authority"]')
                    lead["site"] = sb.get_attribute("href") or ""
                except: pass

                if lead["site"]:
                    log(f"   [{len(leads)+1}] {lead['nome'][:40]} — buscando contato...")
                    email, instagram = buscar_contato(lead["site"])
                    lead["email"]     = email
                    lead["instagram"] = instagram
                else:
                    log(f"   [{len(leads)+1}] {lead['nome'][:40]} — sem site")

                chave = _chave_lead(lead)
                if chave in chaves_set:
                    pulados += 1
                    log(f"   ⏭️  [{i+1}] {lead['nome'][:40]} — já coletado antes, pulando")
                    continue

                chaves_set.add(chave)
                leads.append(lead)
                log(f"       ✓ Tel: {lead['telefone'] or '—'} | Email: {lead['email'] or '—'} | Insta: {lead['instagram'] or '—'}")
                result_q.put(("lead", lead))

            except Exception as e:
                log(f"   [!] Erro no card {i+1}: {e}")

        driver.quit()

        # Persiste histórico com os novos leads
        hist["chaves"] = list(chaves_set)
        hist["total"]  = len(chaves_set)
        salvar_historico(hist)
        if pulados:
            log(f"💾 {pulados} empresa(s) já conhecida(s) foram ignoradas.")
        log(f"💾 Histórico salvo: {len(chaves_set)} empresas únicas no total.")

        result_q.put(("done", leads))

    except Exception as e:
        log_q.put(f"❌ Erro fatal: {e}")
        result_q.put(("done", []))


# ── Form ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### Configurar busca")

col1, col2 = st.columns(2)
with col1:
    nicho = st.text_input("Nicho / Segmento", placeholder='Ex: clínica odontológica')
with col2:
    local = st.text_input("Cidade / Região", value="São Paulo", placeholder='Ex: Curitiba, PR')

num_leads = st.slider("Quantidade máxima de leads", min_value=5, max_value=200, value=30, step=5)

iniciar = st.button("🚀 Iniciar coleta", disabled=st.session_state.running)
st.markdown('</div>', unsafe_allow_html=True)

# ── Run ────────────────────────────────────────────────────────────────────────
if iniciar:
    if not nicho.strip():
        st.error("Informe o nicho antes de iniciar.")
    else:
        st.session_state.running    = True
        st.session_state.leads      = []
        st.session_state.logs       = []
        st.session_state.done       = False
        st.session_state.excel_bytes = None

        log_q    = queue.Queue()
        result_q = queue.Queue()

        t = threading.Thread(
            target=worker,
            args=(nicho.strip(), local.strip(), num_leads, log_q, result_q),
            daemon=True,
        )
        t.start()

        # ── Live feedback ──────────────────────────────────────────────────────
        prog_bar  = st.progress(0, text="Iniciando…")
        log_ph    = st.empty()
        leads_ph  = st.empty()

        while True:
            # Drena logs
            while not log_q.empty():
                st.session_state.logs.append(log_q.get())

            # Drena resultados
            while not result_q.empty():
                kind, data = result_q.get()
                if kind == "lead":
                    st.session_state.leads.append(data)
                elif kind == "done":
                    st.session_state.done = True

            n = len(st.session_state.leads)
            pct = min(int(n / max(num_leads, 1) * 100), 99)
            prog_bar.progress(pct, text=f"{n} lead(s) coletado(s)…")

            log_text = "\n".join(st.session_state.logs[-60:])
            log_ph.markdown(f'<div class="log-box">{log_text}</div>', unsafe_allow_html=True)

            if st.session_state.leads:
                leads_ph.markdown(_leads_html_table(st.session_state.leads), unsafe_allow_html=True)

            if st.session_state.done:
                break
            time.sleep(1)

        prog_bar.progress(100, text="Concluído!")
        st.session_state.running = False

        if st.session_state.leads:
            st.session_state.excel_bytes = gerar_excel(
                st.session_state.leads, nicho.strip(), local.strip()
            )

# ── Results ────────────────────────────────────────────────────────────────────
if st.session_state.leads:
    leads = st.session_state.leads
    n_tel   = sum(1 for l in leads if l.get("telefone"))
    n_email = sum(1 for l in leads if l.get("email"))
    n_insta = sum(1 for l in leads if l.get("instagram"))
    n_site  = sum(1 for l in leads if l.get("site"))

    st.markdown("---")
    st.markdown("### Resultado")

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, num, lbl in zip(
        [c1, c2, c3, c4, c5],
        [len(leads), n_tel, n_email, n_insta, n_site],
        ["Empresas", "Com telefone", "Com e-mail", "Com Instagram", "Com site"],
    ):
        col.markdown(
            f'<div class="stat-box"><div class="num">{num}</div>'
            f'<div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabela
    st.markdown(_leads_html_table(leads), unsafe_allow_html=True)

    # Download
    if not st.session_state.excel_bytes and st.session_state.leads:
        st.session_state.excel_bytes = gerar_excel(
            st.session_state.leads, nicho.strip(), local.strip()
        )

    if st.session_state.excel_bytes:
        fname = f"leads_{nicho.replace(' ','_')}_{local.replace(' ','_')}.xlsx"
        st.download_button(
            label="⬇️  Baixar Excel",
            data=st.session_state.excel_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

elif st.session_state.done and not st.session_state.leads:
    st.warning("Nenhum lead encontrado. Tente outro nicho ou localidade.")
