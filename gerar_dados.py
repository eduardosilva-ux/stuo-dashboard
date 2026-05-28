#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 GERADOR DE DADOS — DASHBOARD OPERACIONAL STUO MOBILIDADE (v2 - drill-down full)
================================================================================

NOVIDADES DESTA VERSÃO
----------------------
O JSON gerado contém pré-agregações COMPLETAS por empresa e por
empresa+mês, permitindo que TODOS os elementos do dashboard (KPIs, série
diária, dia da semana, mapa de calor por UF e os 4 rankings) respondam
ao filtro de empresa.

COMO USAR
---------
1. Tenha Python 3 instalado.
2. Primeira vez: `pip install pandas openpyxl`
3. Rode: `python gerar_dados.py Base.xlsx`
4. Suba o `dados.json` gerado no GitHub (substituindo o antigo).
================================================================================
"""

import sys, re, json
import pandas as pd

COL = {
    "data":     "Datacorrida", "mes":     "Mês",
    "empresa":  "Nomeempresa", "taxista": "Nometaxista",
    "bruto":    "Valorbruto",  "receita": "Receitaliquida",
    "origem":   "Enderecoorigem",
    "id_tax":   "Idtaxista",   "id_emp":  "Idempresa",
    "id_trans": "Idtransacao", "estorno": "Estorno",
}
ORDEM_DIAS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
MAP_DOW = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta",
           4: "Sexta", 5: "Sábado", 6: "Domingo"}


def parse_endereco(s):
    s = str(s)
    m = re.search(r"([^,]+),\s*([^,]+)\s*-\s*([A-Z]{2}),", s)
    if m:
        return pd.Series([m.group(1).strip(), m.group(2).strip(), m.group(3)])
    return pd.Series([None, None, None])


def bloco(d, VB, RL):
    return {
        "corridas":    int(len(d)),
        "faturamento": round(float(d[VB].sum()), 2),
        "receita":     round(float(d[RL].sum()), 2),
        "ticket":      round(float(d[VB].mean()), 2) if len(d) else 0,
        "taxistas":    int(d[COL["id_tax"]].nunique()),
        "empresas":    int(d[COL["id_emp"]].nunique()),
    }


def serie_diaria(d, VB):
    s = (d.groupby(d[COL["data"]].dt.strftime("%Y-%m-%d"))
           .agg(c=(COL["id_trans"], "count"), f=(VB, "sum")).reset_index())
    return [{"data": r[COL["data"]], "corridas": int(r["c"]),
             "fat": round(float(r["f"]), 2)} for _, r in s.iterrows()]


def dia_semana(d, VB):
    dw = d.groupby("DiaSemana").agg(c=(COL["id_trans"], "count"), f=(VB, "sum"))
    return [{"dia": x,
             "corridas": int(dw.loc[x, "c"]) if x in dw.index else 0,
             "fat": round(float(dw.loc[x, "f"]), 2) if x in dw.index else 0}
            for x in ORDEM_DIAS]


def rank(d, col, VB, RL, n=15):
    g = (d.groupby(col)
           .agg(c=(COL["id_trans"], "count"), f=(VB, "sum"), r=(RL, "sum"))
           .sort_values("c", ascending=False).head(n))
    return [{"nome": str(i), "corridas": int(row["c"]),
             "fat": round(float(row["f"]), 2),
             "receita": round(float(row["r"]), 2)} for i, row in g.iterrows()]


def por_uf_func(d, VB):
    u = (d.groupby("UF").agg(c=(COL["id_trans"], "count"), f=(VB, "sum"))
           .sort_values("c", ascending=False))
    return [{"uf": str(i), "corridas": int(r["c"]),
             "fat": round(float(r["f"]), 2)} for i, r in u.iterrows() if i]


def kpis_estr(d, b, VB, RL):
    top5 = sum(e["corridas"] for e in rank(d, COL["empresa"], VB, RL, 5))
    tx = d.groupby(COL["id_tax"])[COL["id_trans"]].count().sort_values(ascending=False)
    n10 = max(1, int(len(tx) * 0.10))
    top10 = int(tx.head(n10).sum())
    return {
        "corridas_por_taxista": round(b["corridas"] / b["taxistas"], 1) if b["taxistas"] else 0,
        "fat_por_empresa":      round(b["faturamento"] / b["empresas"], 2) if b["empresas"] else 0,
        "margem_liquida":       round(100 * b["receita"] / b["faturamento"], 1) if b["faturamento"] else 0,
        "concentracao_top5":    round(100 * top5 / b["corridas"], 1) if b["corridas"] else 0,
        "top10pct_taxistas":    round(100 * top10 / b["corridas"], 1) if b["corridas"] else 0,
    }


def pacote_completo(d, VB, RL, com_top_empresas=True):
    b = bloco(d, VB, RL)
    pkg = {
        "bloco": b,
        "serie_dia": serie_diaria(d, VB),
        "dia_semana": dia_semana(d, VB),
        "top_taxistas": rank(d, COL["taxista"], VB, RL),
        "top_cidades":  rank(d, "Cidade", VB, RL),
        "top_bairros":  rank(d, "Bairro", VB, RL),
        "por_uf":       por_uf_func(d, VB),
        "kpis_estrategicos": kpis_estr(d, b, VB, RL),
    }
    if com_top_empresas:
        pkg["top_empresas"] = rank(d, COL["empresa"], VB, RL)
    return pkg


def main():
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "Base.xlsx"
    print(f"Lendo: {arquivo} ...")
    df = pd.read_excel(arquivo)

    if COL["estorno"] in df.columns:
        df = df[df[COL["estorno"]].astype(str).str.lower()
                  .isin(["nao", "não", "false", "no"])].copy()

    df[COL["data"]] = pd.to_datetime(df[COL["data"]])
    df[COL["mes"]]  = pd.to_datetime(df[COL["mes"]])
    df[["Bairro", "Cidade", "UF"]] = df[COL["origem"]].apply(parse_endereco)
    df["MesLabel"]  = df[COL["mes"]].dt.strftime("%Y-%m")
    df["DiaSemana"] = df[COL["data"]].dt.dayofweek.map(MAP_DOW)

    VB, RL = COL["bruto"], COL["receita"]
    out = {
        "periodo": {
            "min": df[COL["data"]].min().strftime("%d/%m/%Y"),
            "max": df[COL["data"]].max().strftime("%d/%m/%Y"),
        },
        "empresas_list": sorted(df[COL["empresa"]].dropna().unique().tolist()),
        "meses_list":    sorted(df["MesLabel"].unique().tolist()),
    }

    print("  Agregando: geral...")
    out["geral"] = pacote_completo(df, VB, RL)

    print("  Agregando: por mês...")
    out["por_mes"] = {m: pacote_completo(d, VB, RL)
                     for m, d in df.groupby("MesLabel")}

    print(f"  Agregando: {df[COL['empresa']].nunique()} empresas (com cruzamento por mês)...")
    out["por_empresa"] = {}
    for emp, d in df.groupby(COL["empresa"]):
        pkg = pacote_completo(d, VB, RL, com_top_empresas=False)
        pkg["por_mes"] = {m: pacote_completo(x, VB, RL, com_top_empresas=False)
                         for m, x in d.groupby("MesLabel")}
        out["por_empresa"][emp] = pkg

    dados_str = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    with open("dados.json", "w", encoding="utf-8") as f:
        f.write(dados_str)

    # Se existir o dashboard_stuo.html na mesma pasta, gera também a versão
    # standalone (dados.json embutido) para teste local com duplo clique.
    import os
    if os.path.exists("dashboard_stuo.html"):
        html = open("dashboard_stuo.html", encoding="utf-8").read()
        marcador = "fetch('dados.json?v='+Date.now())"
        if marcador in html:
            # Substitui todo o bloco de fetch por DATA inline
            inicio = html.find("// Carrega dados.json")
            fim = html.find("});", inicio) + 3
            if inicio != -1 and fim != 2:
                inline = ("// Dados embutidos (standalone)\n  DATA = "
                          + dados_str + ";\n  boot();")
                html_std = html[:inicio] + inline + html[fim:]
                with open("dashboard_standalone.html", "w", encoding="utf-8") as f:
                    f.write(html_std)
                ts = os.path.getsize("dashboard_standalone.html") / 1024
                print(f"  Também gerado: dashboard_standalone.html ({ts:.0f} KB)")

    g = out["geral"]["bloco"]
    tam = os.path.getsize("dados.json") / 1024
    print(f"\nOK! 'dados.json' gerado ({tam:.0f} KB).")
    print(f"   Corridas: {g['corridas']:,}".replace(",", "."))
    print(f"   Faturamento: R$ {g['faturamento']:,.2f}")
    print(f"   Período: {out['periodo']['min']} a {out['periodo']['max']}")
    print(f"   Empresas: {len(out['empresas_list'])} | Meses: {out['meses_list']}")


if __name__ == "__main__":
    main()
