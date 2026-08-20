"""SQLite — persistência e deduplicação."""
import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def _conn():
    c = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE,
            nome TEXT,
            nicho TEXT,
            telefone TEXT,
            email TEXT,
            instagram TEXT,
            site TEXT,
            cidade TEXT,
            estado TEXT,
            cnpj TEXT,
            porte TEXT,
            data_abertura TEXT,
            tempo_empresa_anos REAL,
            nota_maps REAL,
            num_reviews INTEGER,
            score_local INTEGER,
            score_final INTEGER,
            tier TEXT,
            urgencia TEXT,
            resumo TEXT,
            dores TEXT,
            oportunidade TEXT,
            abordagem TEXT,
            qualificacao_completa TEXT,
            fonte TEXT,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            exportado INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_tier     ON leads(tier);
        CREATE INDEX IF NOT EXISTS idx_score    ON leads(score_final DESC);
        CREATE INDEX IF NOT EXISTS idx_urgencia ON leads(urgencia);
        """)


def ja_existe(chave: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT id FROM leads WHERE chave=?", (chave,)).fetchone()
        return row is not None


def salvar_lead(lead: dict):
    chave = lead.get("chave") or lead.get("cnpj") or f"{lead.get('nome','')}|{lead.get('cidade','')}"
    qualif = lead.get("qualificacao_ia") or {}
    abord  = qualif.get("abordagem") or lead.get("abordagem") or {}

    with _conn() as c:
        c.execute("""
        INSERT OR REPLACE INTO leads
          (chave,nome,nicho,telefone,email,instagram,site,cidade,estado,
           cnpj,porte,data_abertura,tempo_empresa_anos,nota_maps,num_reviews,
           score_local,score_final,tier,urgencia,resumo,dores,oportunidade,
           abordagem,qualificacao_completa,fonte)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            chave,
            lead.get("nome",""),
            lead.get("nicho",""),
            lead.get("telefone",""),
            lead.get("email",""),
            lead.get("instagram",""),
            lead.get("site",""),
            lead.get("cidade",""),
            lead.get("estado",""),
            lead.get("cnpj",""),
            lead.get("porte",""),
            lead.get("data_abertura",""),
            lead.get("tempo_empresa_anos"),
            lead.get("nota_maps"),
            lead.get("num_reviews"),
            lead.get("score_local"),
            lead.get("score_final") or lead.get("score_local") or 0,
            lead.get("tier_final") or lead.get("tier_local") or "FRIO",
            lead.get("urgencia","NUTRIR"),
            qualif.get("resumo") or lead.get("resumo",""),
            json.dumps(qualif.get("dores_identificadas", []), ensure_ascii=False),
            qualif.get("oportunidade_eden",""),
            json.dumps(abord, ensure_ascii=False),
            json.dumps(lead.get("qualificacao_ia") or {}, ensure_ascii=False),
            lead.get("fonte","google_maps"),
        ))


def carregar_todos(filtro_tier: str = None) -> list[dict]:
    with _conn() as c:
        if filtro_tier:
            rows = c.execute(
                "SELECT * FROM leads WHERE tier=? ORDER BY score_final DESC", (filtro_tier,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM leads ORDER BY score_final DESC").fetchall()
    return [dict(r) for r in rows]


def limpar_banco():
    with _conn() as c:
        c.execute("DELETE FROM leads")
        c.execute("DELETE FROM sqlite_sequence WHERE name='leads'")


def total_leads() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


init_db()
