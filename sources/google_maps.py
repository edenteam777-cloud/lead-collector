"""Google Maps — coleta via Chrome/Selenium."""
import re
import time
import asyncio
from config import SCRAPING_TIMEOUT


def _extrair_cidade(endereco: str) -> tuple[str, str]:
    """Retorna (cidade, estado)."""
    if not endereco:
        return "", ""
    e = re.sub(r'^Endereço:\s*|^Address:\s*', '', endereco, flags=re.I)
    m = re.search(
        r'[,\-]\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{2,30}?)\s*[-–]\s*([A-Z]{2})(?:\s*[,\d\s]|$)',
        e,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    partes = [p.strip() for p in re.split(r'[,\-]', e)]
    skip = re.compile(r'^\d|^(rua|av\b|avenida|r\.|al\.|alameda|praça|travessa|estrada|bairro|jardim|vila)', re.I)
    estado_re = re.compile(r'^[A-Z]{2}$')
    cep_re    = re.compile(r'\d{4,5}-?\d{3}')
    candidatos = [p for p in partes if p and len(p) >= 3
                  and not skip.match(p) and not estado_re.match(p) and not cep_re.search(p)]
    return (candidatos[-1] if candidatos else ""), ""


def _limpar_tel(t: str) -> str:
    return re.sub(r"[^\d+()\s\-]", "", t).strip()


def _formatar_tel(raw: str) -> str:
    """Formata para (DDD) 9XXXX-XXXX ou (DDD) XXXX-XXXX."""
    raw = re.sub(r"^tel:", "", raw.strip(), flags=re.I)
    digits = re.sub(r"\D", "", raw)
    # Remove prefixo internacional 55 ou zero à esquerda
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return raw.strip()


def _scroll_maps(driver, painel, n_scrolls: int, max_leads: int, log_fn):
    from selenium.webdriver.common.by import By

    prev_count = 0
    sem_novos  = 0

    for i in range(n_scrolls):
        try:
            if painel:
                try:
                    driver.execute_script("arguments[0].scrollTop += 800", painel)
                except Exception:
                    painel = None

            if not painel:
                todos = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
                if todos:
                    driver.execute_script("arguments[0].scrollIntoView({block:'end'})", todos[-1])
                else:
                    driver.execute_script("window.scrollBy(0,800)")

            time.sleep(2)

            if i % 3 == 2:
                cur = len(driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]'))
                log_fn(f"   scroll {i+1}: {cur} cards")
                if cur == prev_count:
                    sem_novos += 1
                    if sem_novos >= 3:
                        log_fn("   Sem novos resultados, parando scroll.")
                        break
                else:
                    sem_novos = 0
                prev_count = cur
                if cur >= max_leads * 2:
                    break
        except Exception:
            break
    return painel


def coletar_google_maps(nicho: str, local: str, max_leads: int, log_fn) -> list[dict]:
    """Roda em thread separada (sync). Retorna lista de leads brutos."""
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    _PANEL_XPATHS = [
        '//div[@role="feed"]',
        '//div[contains(@aria-label,"Resultados")]',
        '//div[contains(@aria-label,"Results")]',
        '//div[@aria-label and @role="main"]//div[@tabindex="-1"]',
        '//div[contains(@class,"m6QErb") and @tabindex]',
        '//div[contains(@class,"m6QErb")]',
    ]

    def _build_opts():
        o = uc.ChromeOptions()
        for arg in [
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-extensions", "--disable-background-networking",
            "--disable-sync", "--mute-audio", "--no-first-run",
            "--disable-blink-features=AutomationControlled", "--lang=pt-BR",
        ]:
            o.add_argument(arg)
        return o

    def _chrome_version():
        import subprocess
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for sub in (r"SOFTWARE\Google\Chrome\BLBeacon",
                            r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon"):
                    try:
                        key = winreg.OpenKey(root, sub)
                        val, _ = winreg.QueryValueEx(key, "version")
                        winreg.CloseKey(key)
                        m = re.match(r"(\d+)", str(val))
                        if m: return int(m.group(1))
                    except OSError:
                        pass
        except ImportError:
            pass
        return None

    log_fn("🚀 Iniciando Chrome...")
    ver = _chrome_version()
    driver = None
    for v in ([ver, ver-1, ver+1] if ver else [None]):
        kw = {"version_main": v} if v is not None else {}
        try:
            driver = uc.Chrome(options=_build_opts(), **kw)
            break
        except Exception:
            driver = None

    if not driver:
        raise RuntimeError("Não foi possível iniciar o Chrome.")

    driver.set_window_size(1400, 900)
    query = f"{nicho} em {local}"
    log_fn(f"🗺️  Buscando: {query}")
    driver.get(f"https://www.google.com/maps/search/{query.replace(' ', '+')}?hl=pt-BR&gl=BR")
    time.sleep(4)

    # Aceita diálogo de consentimento/cookies do Google (obrigatório em muitas regiões)
    for consent_xpath in [
        '//button[contains(.,"Aceitar tudo") or contains(.,"Accept all")]',
        '//button[contains(.,"Concordo") or contains(.,"I agree")]',
        '//button[contains(.,"Rejeitar tudo") or contains(.,"Reject all")]',
        '//div[@role="dialog"]//button[2]',
    ]:
        try:
            btn = driver.find_element(By.XPATH, consent_xpath)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                log_fn("   ✓ Diálogo de consentimento aceito")
                time.sleep(2)
                break
        except Exception:
            pass

    # Aguarda resultados carregarem (espera pelo menos 1 card ou feed)
    for _ in range(8):
        try:
            cards_test = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
            if len(cards_test) > 0:
                break
        except Exception:
            pass
        time.sleep(1.5)

    # Detecta painel
    painel = None
    for _ in range(5):
        for xpath in _PANEL_XPATHS:
            try:
                el = driver.find_element(By.XPATH, xpath)
                h = driver.execute_script("return arguments[0].scrollHeight", el)
                if el and h and h > 200:
                    painel = el; break
            except Exception:
                pass
        if painel: break
        time.sleep(2)

    log_fn(f"   Painel: {'encontrado ✓' if painel else 'não encontrado'}")
    n_scrolls = max(20, (max_leads // 2) + 10)
    _scroll_maps(driver, painel, n_scrolls, max_leads, log_fn)

    # Coleta cards únicos
    raw_cards = []
    for sel in [
        'div[role="feed"] a[href*="/maps/place/"]',
        'div[role="article"] a[href*="/maps/place/"]',
        'a[href*="/maps/place/"]',
    ]:
        raw_cards = driver.find_elements(By.CSS_SELECTOR, sel)
        if len(raw_cards) > 3:
            break

    seen = set()
    cards = []
    for c in raw_cards:
        href = (c.get_attribute("href") or "").split("?")[0]
        if href and href not in seen:
            seen.add(href); cards.append(c)

    log_fn(f"📋 {len(cards)} empresas encontradas.")
    wait = WebDriverWait(driver, 5)
    leads = []
    visitados = set()

    _NOMES_INVALIDOS_PREFIX = ("resultados", "results", "google", "pesquisar", "search")
    _NOMES_INVALIDOS_EXACT  = {"maps", "loading", "carregando", "voltar", "back", "fechar", "close"}

    def _nome_valido(t: str) -> bool:
        if not t or len(t) < 3:
            return False
        tl = t.lower().strip()
        if tl in _NOMES_INVALIDOS_EXACT:
            return False
        if any(tl.startswith(p) for p in _NOMES_INVALIDOS_PREFIX):
            return False
        return True

    for i, card in enumerate(cards):
        if len(leads) >= max_leads:
            break
        try:
            href = card.get_attribute("href") or ""
            if href in visitados: continue
            visitados.add(href)

            # Extrai nome do card ANTES de clicar (aria-label é mais confiável que h1 depois do click)
            nome_card = ""
            for attr in ["aria-label", "data-value"]:
                v = (card.get_attribute(attr) or "").strip()
                if _nome_valido(v):
                    nome_card = v; break
            if not nome_card:
                # Tenta texto de elementos filhos do card pai e avós
                try:
                    for ancestor_xpath in ["..", "../..", "../../.."]:
                        try:
                            parent = card.find_element(By.XPATH, ancestor_xpath)
                            for sel in [
                                '[class*="fontHeadlineSmall"]', '[class*="qBF1Pd"]',
                                '[class*="NrDZNb"]', 'div[class*="OSrXXb"]',
                                '[role="heading"]', 'span[class*="fontBody"]',
                            ]:
                                for el in parent.find_elements(By.CSS_SELECTOR, sel):
                                    t = el.text.strip()
                                    if _nome_valido(t):
                                        nome_card = t; break
                                if nome_card: break
                            if nome_card: break
                        except Exception:
                            pass
                except Exception:
                    pass
            # Último recurso: texto direto do elemento
            if not nome_card:
                try:
                    t = card.text.strip().split("\n")[0]
                    if _nome_valido(t):
                        nome_card = t
                except Exception:
                    pass

            log_fn(f"🔍 [{i+1}/{len(cards)}] {'→ ' + nome_card[:35] if nome_card else 'Abrindo...'}")
            driver.execute_script("arguments[0].click();", card)

            # Espera o painel de detalhes carregar (aguarda h1 ou qualquer dado aparecer)
            lead = {"fonte": "google_maps"}
            for _ in range(8):
                try:
                    if driver.find_elements(By.CSS_SELECTOR, 'h1, [data-item-id]'):
                        break
                except Exception:
                    pass
                time.sleep(0.8)
            time.sleep(1.5)

            # Nome
            if nome_card:
                lead["nome"] = nome_card
            else:
                for sel in ['h1[class*="fontHeadlineLarge"]', 'h1[class*="DUwDvf"]',
                            'div[role="main"] h1', '[role="main"] [role="heading"]', 'h1']:
                    try:
                        for _ in range(4):
                            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                                t = el.text.strip()
                                if _nome_valido(t):
                                    lead["nome"] = t; break
                            if lead.get("nome"): break
                            time.sleep(0.8)
                    except Exception:
                        pass
                    if lead.get("nome"): break

            if not lead.get("nome"):
                log_fn(f"   [!] Card {i+1}: nome não encontrado, pulando")
                continue

            # ── Extração via data-item-id (mais estável do Maps) ──────────────
            try:
                # Telefone: data-item-id="phone:+5573..." ou só "phone"
                for btn in driver.find_elements(By.CSS_SELECTOR, 'button[data-item-id]'):
                    did = btn.get_attribute("data-item-id") or ""
                    if did.startswith("phone"):
                        num_raw = did.replace("phone:", "").strip()
                        if re.search(r"\d{6,}", num_raw):
                            lead["telefone"] = _formatar_tel(num_raw); break
                        src = btn.get_attribute("aria-label") or btn.text or ""
                        m = re.search(r"[\(\d][\d\s\-\(\)]{7,}", src)
                        if m:
                            lead["telefone"] = _formatar_tel(m.group()); break
            except Exception:
                pass

            try:
                # Site: data-item-id="authority"
                for a in driver.find_elements(By.CSS_SELECTOR, 'a[data-item-id="authority"]'):
                    href = a.get_attribute("href") or ""
                    if href.startswith("http") and "google" not in href:
                        lead["site"] = href; break
            except Exception:
                pass

            try:
                # Endereço: data-item-id="address"
                for btn in driver.find_elements(By.CSS_SELECTOR, 'button[data-item-id="address"]'):
                    addr = (btn.get_attribute("aria-label") or btn.text or "").strip()
                    addr = re.sub(r"^Endereço:\s*|^Address:\s*", "", addr, flags=re.I)
                    if addr and len(addr) > 5:
                        c_val, e_val = _extrair_cidade(addr)
                        lead["endereco_completo"] = addr
                        if c_val:
                            lead["cidade"] = c_val
                            lead["estado"] = e_val
                        break
            except Exception:
                pass

            # ── Nota e reviews ────────────────────────────────────────────────
            try:
                for el in driver.find_elements(By.XPATH, '//span[@aria-hidden="true"]'):
                    txt = el.text.strip().replace(",", ".")
                    if re.match(r"^[1-5]\.\d$", txt):
                        lead["nota_maps"] = float(txt); break
            except Exception:
                pass

            try:
                for el in driver.find_elements(By.XPATH,
                    '//*[contains(@aria-label,"avaliações") or contains(@aria-label,"reviews") or contains(@aria-label,"opiniões")]'):
                    txt = re.sub(r"[^\d]", "", el.get_attribute("aria-label") or "")
                    if txt:
                        lead["num_reviews"] = int(txt); break
            except Exception:
                pass

            # ── Fallback: escaneia TODO o texto visível do painel ─────────────
            # Captura qualquer telefone que o Maps mostre, independente do seletor
            # ── Instagram direto do Maps (links sociais listados no perfil) ──────
            try:
                for a in driver.find_elements(By.CSS_SELECTOR, 'a[href*="instagram.com"]'):
                    href = a.get_attribute("href") or ""
                    ig_m = re.search(r'instagram\.com/([A-Za-z0-9._]{2,30})', href)
                    if ig_m and ig_m.group(1).lower() not in {"p","reel","explore","accounts","tv"}:
                        lead["instagram"] = "@" + ig_m.group(1); break
            except Exception:
                pass

            # ── Fallback texto completo ────────────────────────────────────────
            try:
                panel_text = driver.find_element(By.CSS_SELECTOR, 'div[role="main"]').text
            except Exception:
                panel_text = ""

            if not lead.get("telefone") and panel_text:
                for m in re.finditer(r'\(?\d{2}\)?\s*9?\d{4}[\s\-]?\d{4}', panel_text):
                    digits = re.sub(r"\D", "", m.group())
                    if len(digits) >= 10:
                        lead["telefone"] = _formatar_tel(digits); break

            if not lead.get("nota_maps") and panel_text:
                m = re.search(r'\b([1-5][,\.]\d)\b', panel_text)
                if m:
                    lead["nota_maps"] = float(m.group(1).replace(",", "."))

            if not lead.get("instagram") and panel_text:
                ig_m = re.search(r'@([A-Za-z0-9._]{3,30})', panel_text)
                if ig_m:
                    lead["instagram"] = "@" + ig_m.group(1)

            # Ticket médio
            try:
                for xpath in [
                    '//*[contains(@aria-label,"Nível de preço") or contains(@aria-label,"Price range")]',
                    '//span[contains(@aria-label,"€") or contains(@aria-label,"R$")]',
                ]:
                    for el in driver.find_elements(By.XPATH, xpath):
                        txt = (el.get_attribute("aria-label") or el.text or "").strip()
                        if txt:
                            lead["ticket_medio"] = txt; break
                    if lead.get("ticket_medio"): break
            except Exception:
                pass

            # Descrição
            for xpath in [
                '//div[contains(@class,"PYvSYb")]',
                '//div[contains(@class,"HlvSq")]',
                '//div[@aria-label="Sobre este lugar"]//span[not(contains(@class,"icon"))]',
                '//div[contains(@aria-label,"Sobre")]//span[not(contains(@class,"icon"))]',
                '//h2[contains(text(),"Sobre")]/following-sibling::div//span',
                '//div[contains(@class,"iP2t7d")]',
            ]:
                for el in driver.find_elements(By.XPATH, xpath):
                    txt = el.text.strip()
                    if txt and len(txt) > 20:
                        lead["info_empresa"] = txt[:400]; break
                if lead.get("info_empresa"): break

            # Tempo no Maps
            _EN = {"years at this location":"anos neste local","years in business":"anos no mercado",
                   "open since":"aberto desde","years on google":"anos no Google"}
            for xpath in [
                '//*[contains(text(),"anos no Google") or contains(text(),"anos neste negócio")]',
                '//*[contains(text(),"Aberto há") or contains(text(),"Estabelecido em")]',
                '//*[contains(text(),"years in business") or contains(text(),"years at this")]',
            ]:
                for el in driver.find_elements(By.XPATH, xpath):
                    txt = el.text.strip()
                    if txt and re.search(r'\d', txt):
                        for en, pt in _EN.items():
                            txt = re.sub(en, pt, txt, flags=re.I)
                        lead["tempo_empresa_txt"] = txt; break
                if lead.get("tempo_empresa_txt"): break

            leads.append(lead)
            log_fn(
                f"   ✓ {lead['nome'][:38]} | "
                f"Tel:{lead.get('telefone','—')} | "
                f"Nota:{lead.get('nota_maps','—')} | "
                f"Cidade:{lead.get('cidade','—')} | "
                f"Site:{'✓' if lead.get('site') else '—'}"
            )

        except Exception as e:
            log_fn(f"   [!] Erro card {i+1}: {e}")

    try:
        driver.quit()
    except Exception:
        pass
    return leads


async def coletar_google_maps_async(nicho: str, local: str, max_leads: int, log_fn) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: coletar_google_maps(nicho, local, max_leads, log_fn)
    )
