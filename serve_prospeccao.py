"""Servidor da Central de Prospecção Eden — lê leads do SQLite e serve a interface."""
import json
import os
import sqlite3

from flask import Flask, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "leads.db")

app = Flask(__name__)


def _parse(val, default):
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def _map_lead(row: dict) -> dict:
    dores        = _parse(row.get("dores"), [])
    abordagem    = _parse(row.get("abordagem"), {})
    qualificacao = _parse(row.get("qualificacao_completa"), {})

    ai_data = None
    if qualificacao and not qualificacao.get("erro"):
        ai_data = {
            "tier":         qualificacao.get("tier") or row.get("tier", "FRIO"),
            "score":        qualificacao.get("score_final") or row.get("score_final") or 0,
            "diagnostico":  qualificacao.get("resumo") or row.get("resumo") or "",
            "dores":        qualificacao.get("dores_identificadas") or dores,
            "oportunidade": qualificacao.get("oportunidade_eden") or row.get("oportunidade") or "",
            "solucoes":     [],
            "mensagem_wa1": abordagem.get("abertura") or "",
            "mensagem_wa2": "",
            "mensagem_dm":  "",
        }

    return {
        "id":          row["id"],
        "nome":        row.get("nome")        or "",
        "nicho":       row.get("nicho")       or "",
        "telefone":    row.get("telefone")    or "",
        "email":       row.get("email")       or "",
        "instagram":   row.get("instagram")   or "",
        "site":        row.get("site")        or "",
        "cidade":      row.get("cidade")      or "",
        "estado":      row.get("estado")      or "",
        "cnpj":        row.get("cnpj")        or "",
        "porte":       row.get("porte")       or "",
        "nota_maps":   row.get("nota_maps")   or 0,
        "num_reviews": row.get("num_reviews") or 0,
        "score_local": row.get("score_local") or 0,
        "score_final": row.get("score_final") or 0,
        "tier":        row.get("tier")        or "FRIO",
        "urgencia":    row.get("urgencia")    or "",
        "fonte":       row.get("fonte")       or "google_maps",
        "_aiData":     ai_data,
        "_aiScore":    ai_data["score"] if ai_data else None,
    }


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "eden_prospeccao.html")


@app.route("/api/leads")
def api_leads():
    if not os.path.exists(DB_PATH):
        return jsonify([])
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM leads ORDER BY score_final DESC").fetchall()
    conn.close()
    return jsonify([_map_lead(dict(r)) for r in rows])


if __name__ == "__main__":
    print("\n🎯  Central de Prospecção Eden")
    print(f"   Banco: {DB_PATH}")
    print("   → http://localhost:5500\n")
    app.run(host="0.0.0.0", port=5500, debug=False)
