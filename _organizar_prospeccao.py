"""Organiza a prospecção de sites em D:/Projetos/sites/prospeccao/<cidade>/[<bairro>/]<cliente>/.

- porto/<lead>/comercial.md: cópia dos trechos de qualificação e abordagem de cada lead
  (originais continuam em eden-os/comercial/abordagens/).
- sao-paulo/<bairro>/<lead>/ficha.md: dados, problema do site e mensagem de primeiro contato
  dos 132 leads-alvo do lote 2026-10-14.
- README.md com índice em cada nível.
Pode rodar de novo: reescreve só comercial.md, ficha.md e READMEs.
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gerar_abordagens_sp_20261014 import OUT as SP_LOTE, celular, msg_toque1, nome_curto  # noqa: E402

ROOT = Path(r"D:/Projetos/sites/prospeccao")
ABORD = Path(r"D:/Projetos/EdenOs/eden-os/eden-os/comercial/abordagens")

# 1.º lote de demos SP (escolhido em 2026-10-14: WhatsApp, sem site/fora do ar, volume no Maps, 2 por nicho)
TOP10 = ("JB Estética", "Mef", "Leticia de Nóbrega",
         "Studio ELLO", "Vértiza Imóveis", "Artigiano Oficina", "ALOHA jóias")  # Kauffmann, Salomão, EAP descartados 15/10

PORTO_FONTES = [
    (ABORD / "2026-09-29-porto-pt/abordagens-porto.md", r"^## \d\. ", "Abordagem lote 1 (29/09, rev. 02/10)"),
    (ABORD / "2026-10-07-porto-pt-lote2/qualificacao-lote2.md", r"^### 4\.\d ", "Qualificação lote 2 (07/10)"),
    (ABORD / "2026-10-09-porto-pt-manual/abordagens.md", r"^## ", "Abordagem envio manual (09/10)"),
]

# Palavras do título da seção que identificam cada pasta do Porto
PORTO_CHAVE = {
    "the-door": "door", "bota-e-bira": "bota", "creative-porto": "creative", "magikhair": "magikhair",
    "foz-concept": "foz", "gomes-cortes-e-cores": "gomes", "bulha-porto": "bulha", "miguel-viana": "miguel",
    "residencial-porto-novo": "residencial", "mo-house": "mo-house", "muu-steakhouse": "muu",
    "casa-viuva": "viuva", "guesthouse-marques": "marques", "flow": "flow",
}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50]


def secoes(path, padrao):
    """Divide o markdown em {título: texto} a partir dos cabeçalhos que casam com o padrão."""
    out, atual, buf = {}, None, []
    nivel = padrao.count("#")
    for linha in path.read_text(encoding="utf-8").splitlines():
        if re.match(padrao, linha):
            if atual:
                out[atual] = "\n".join(buf).strip()
            atual, buf = linha, [linha]
        elif atual and re.match(r"^#{1,%d} " % nivel, linha):
            out[atual] = "\n".join(buf).strip()
            atual, buf = None, []
        elif atual:
            buf.append(linha)
    if atual:
        out[atual] = "\n".join(buf).strip()
    return out


def porto():
    base = ROOT / "porto"
    leads = sorted(p.name for p in base.iterdir() if p.is_dir() and p.name in PORTO_CHAVE)
    linhas = ["# Prospecção Porto (PT)", "",
              "Uma pasta por lead: `antes/` (diagnóstico do site atual), `refs/`, `site/` (demo), `entrega/` (vídeos), "
              "`comercial.md` (qualificação + abordagem).",
              "O caminho antigo `D:/Projetos/sites/porto-pt` é um atalho (junction) para esta pasta — o pipeline de vídeo continua funcionando.",
              "", "| Lead | Demo | Vídeo | Comercial |", "|---|---|---|---|"]
    for lead in leads:
        partes = []
        for path, padrao, rotulo in PORTO_FONTES:
            for titulo, texto in secoes(path, padrao).items():
                if PORTO_CHAVE[lead] in slug(titulo):
                    partes.append(f"> **{rotulo}** — fonte: `{path}`\n\n{texto}")
        d = base / lead
        if partes:
            (d / "comercial.md").write_text(
                f"# {lead} — comercial\n\nCópia dos trechos sobre este lead; o original continua na fonte indicada.\n\n"
                + "\n\n---\n\n".join(partes) + "\n", encoding="utf-8")
        demo = "sim" if (d / "site").exists() else "—"
        video = "sim" if any((d / "entrega").glob("*.mp4")) else "—"
        com = f"[comercial.md]({lead}/comercial.md)" if partes else "—"
        linhas.append(f"| [{lead}]({lead}/) | {demo} | {video} | {com} |")
    (base / "README.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return len(leads)


def sao_paulo():
    base = ROOT / "sao-paulo"
    leads = json.loads((SP_LOTE / "leads-sites.json").read_text(encoding="utf-8"))
    alvo = [l for l in leads if l["categoria"] in ("SEM SITE", "FORA DO AR", "SITE FRACO")]
    por_bairro, usados = defaultdict(list), set()
    for l in alvo:
        b = (l.get("bairro") or "sem-bairro").split(",")[0]
        s = slug(nome_curto(l["nome"]))
        while (b, s) in usados:
            s += "-2"
        usados.add((b, s))
        top = any(l["nome"].startswith(t) for t in TOP10)
        d = base / slug(b) / s
        d.mkdir(parents=True, exist_ok=True)
        tel = l.get("telefone") or ""
        ig = (l.get("instagram") or "").lstrip("@")
        # Linha "Demo" é atualizada à mão/pelos agentes: preserva se a ficha já existe
        demo = f"- **Demo:** {'lote 1 (em produção)' if top else 'ainda não'}"
        if (d / "ficha.md").exists():
            demo = next((x for x in (d / "ficha.md").read_text(encoding="utf-8").splitlines()
                         if x.startswith("- **Demo:**")), demo)
        ficha = [
            f"# {nome_curto(l['nome'])}", "",
            f"- **Nome no Google Maps:** {l['nome']}",
            f"- **Nicho:** {l.get('nicho')} · **Bairro:** {b}",
            f"- **Situação do site:** {l['categoria']} — {l.get('problema') or ''}",
            f"- **Site na ficha:** {l.get('site') or '—'}",
            f"- **Telefone:** {tel or '—'} ({'celular / WhatsApp' if celular(tel) else 'fixo ou ausente: ligar e pedir o WhatsApp'})",
            f"- **Instagram:** {'@' + ig if ig else '— (não confirmado)'}",
            f"- **CNPJ:** {l.get('cnpj') or '—'}",
            f"- **Google Maps:** nota {l.get('nota_maps') or '—'} · {l.get('num_reviews') or 0} avaliações",
            f"- **Score ICP:** {l.get('score')} ({l.get('tier')}, sem qualificação por IA)",
            demo,
            "", "## Mensagem de primeiro contato", "", "```", msg_toque1(l), "```", "",
            "## Acompanhamento", "", "- [ ] Mensagem enviada em: ", "- [ ] Follow-up (3 dias depois) em: ",
            "- [ ] Respondeu: ", "- [ ] Demo enviado: ", "",
            f"<!-- gerado de {SP_LOTE / 'leads-sites.json'} -->",
        ]
        (d / "ficha.md").write_text("\n".join(ficha) + "\n", encoding="utf-8")
        por_bairro[b].append((l, d, top))

    linhas = ["# Prospecção São Paulo — bairros nobres (lote 14/10/2026)", "",
              f"{len(alvo)} leads-alvo, uma pasta por cliente dentro do bairro. Cada pasta tem `ficha.md` "
              "(dados, problema do site, mensagem pronta, acompanhamento). Leads do lote 1 de demos marcados com ★.",
              f"Lista completa e página de envio: `{SP_LOTE}`.", ""]
    for b in sorted(por_bairro):
        linhas += [f"## {b} ({len(por_bairro[b])})", "", "| Cliente | Nicho | Site | WhatsApp |", "|---|---|---|---|"]
        for l, d, top in sorted(por_bairro[b], key=lambda x: (not x[2], x[0]["nicho"], x[1].name)):
            rel = d.relative_to(base).as_posix()
            linhas.append(f"| {'★ ' if top else ''}[{nome_curto(l['nome'])}]({rel}/ficha.md) | {l['nicho']} | "
                          f"{l['categoria'].lower()} | {'sim' if celular(l.get('telefone')) else '—'} |")
        linhas.append("")
    (base / "README.md").write_text("\n".join(linhas), encoding="utf-8")
    return len(alvo), sum(1 for v in por_bairro.values() for x in v if x[2])


def main():
    n_porto = porto()
    n_sp, n_top = sao_paulo()
    (ROOT / "README.md").write_text(
        "# Prospecção de sites — Eden Technology\n\nUma pasta por cidade, uma pasta por cliente.\n\n"
        f"- [porto/](porto/README.md) — {n_porto} leads (Porto, PT)\n"
        f"- [sao-paulo/](sao-paulo/README.md) — {n_sp} leads em bairros nobres, por bairro ({n_top} no lote 1 de demos)\n",
        encoding="utf-8")
    print(f"porto={n_porto} sp={n_sp} top10={n_top}")


if __name__ == "__main__":
    main()
