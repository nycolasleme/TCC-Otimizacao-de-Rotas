"""Executa todos os experimentos do capítulo de Resultados e salva CSV/JSON em resultados/."""
import json, os, time, platform
import numpy as np, pandas as pd
from grafo import carregar_grafo, estatisticas
from caminho_minimo import busca, matriz_custos
from aco import aco
from ag import ag
from exato import held_karp, forca_bruta
from dinamico import simular, iteracoes_para_convergir
from transito import limpar_transito

OUT = "resultados"; os.makedirs(OUT, exist_ok=True)
RUNS = 30
ACO_KW = dict(n_formigas=20, n_iter=200, alpha=1.0, beta=3.0, rho=0.5)
AG_KW = dict(pop=50, geracoes=80, pc=0.9, pm=0.05)

def instancia(G, n_paradas, seed):
    rng = np.random.default_rng(seed)
    p = [int(x) for x in rng.choice(list(G.nodes), n_paradas + 1, replace=False)]
    D, cam = matriz_custos(G, p)
    return p, D, cam

def main(fonte="auto"):
    G = carregar_grafo(fonte)
    info = {"fonte": G.graph["fonte"], **estatisticas(G),
            "grau_medio_nao_direcionado": float(np.mean([len(set(G.successors(n)) | set(G.predecessors(n))) for n in G])),
            "cpu": platform.processor() or platform.machine(), "python": platform.python_version()}
    print(info)

    # E1 - Dijkstra x A*
    rng = np.random.default_rng(7); nos = list(G.nodes); linhas = []
    for k in range(100):
        s, t = [int(x) for x in rng.choice(nos, 2, replace=False)]
        for nome, h in (("Dijkstra", False), ("A*", True)):
            t0 = time.perf_counter(); cam, c, exp = busca(G, s, t, usar_heuristica=h)
            linhas.append({"par": k, "algoritmo": nome, "tempo_ms": 1000 * (time.perf_counter() - t0),
                           "expandidos": exp, "custo_s": c, "arestas": len(cam) - 1})
    pd.DataFrame(linhas).to_csv(f"{OUT}/e1_dijkstra_astar.csv", index=False); print("E1 ok")

    # E2 - estático ACO x AG x exato
    linhas, conv = [], {}
    for n in [5, 10, 15, 20, 30, 50]:
        p, D, _ = instancia(G, n, 1000 + n)
        ot = held_karp(D) if n <= 10 else None
        for r in range(RUNS):
            a = aco(D, seed=r, **ACO_KW); g = ag(D, seed=r, **AG_KW)
            for nome, res in (("ACO", a), ("AG", g)):
                linhas.append({"n": n, "run": r, "algoritmo": nome, "custo_s": res["custo"],
                               "tempo_s": res["tempo"], "otimo_s": ot["custo"] if ot else np.nan})
            if n == 30:
                conv.setdefault("ACO", []).append(a["historico"]); conv.setdefault("AG", []).append(g["historico"])
        if ot:
            linhas.append({"n": n, "run": 0, "algoritmo": "Held-Karp", "custo_s": ot["custo"], "tempo_s": ot["tempo"], "otimo_s": ot["custo"]})
        print("E2 n", n)
    df = pd.DataFrame(linhas); df.to_csv(f"{OUT}/e2_estatico.csv", index=False)
    np.save(f"{OUT}/e3_conv_aco.npy", np.array(conv["ACO"])); np.save(f"{OUT}/e3_conv_ag.npy", np.array(conv["AG"]))

    # E2b - escalabilidade do exato
    linhas = []
    for n in range(4, 15):
        _, D, _ = instancia(G, n, 2000 + n)
        if n <= 9:
            linhas.append({"n": n, "metodo": "Força bruta", "tempo_s": forca_bruta(D)["tempo"]})
        if n <= 13:
            linhas.append({"n": n, "metodo": "Held-Karp", "tempo_s": held_karp(D)["tempo"]})
        linhas.append({"n": n, "metodo": "ACO", "tempo_s": aco(D, seed=0, **ACO_KW)["tempo"]})
        print("E2b n", n)
    pd.DataFrame(linhas).to_csv(f"{OUT}/e2b_escalabilidade.csv", index=False)

    # E4 - dinâmico
    linhas, hB, hC = [], [], []
    for r in range(RUNS):
        p, D, cam = instancia(G, 20, 5000 + r)
        a = aco(D, seed=r, **ACO_KW)
        t0 = time.perf_counter(); matriz_custos(G, p); t_full_base = time.perf_counter() - t0
        res = simular(G, p, D, cam, a, k_atual=5, fator=5.0, raio=500, n_iter=100, seed=r)
        t0 = time.perf_counter(); matriz_custos(G, p); t_full = time.perf_counter() - t0
        limpar_transito(G)
        linhas.append({"run": r, "previsto_s": res["custo_A_previsto"], "sem_sistema_s": res["custo_sem_sistema"],
                       "so_caminhos_s": res["custo_A"], "cold_s": res["B"]["custo"], "warm_s": res["C"]["custo"],
                       "it_cold": iteracoes_para_convergir(res["B"]["historico"]),
                       "it_warm": iteracoes_para_convergir(res["C"]["historico"]),
                       "cold_10it_s": res["B"]["historico"][9], "warm_10it_s": res["C"]["historico"][9],
                       "tempo_cold_s": res["B"]["tempo"], "tempo_warm_s": res["C"]["tempo"],
                       "arcos_afetados": len(res["afetados"]), "pares_afetados": res["pares_afetados"],
                       "linhas_recalc": res["linhas_recalculadas"], "t_seletivo_s": res["t_seletivo"], "t_completo_s": t_full})
        hB.append(res["B"]["historico"]); hC.append(res["C"]["historico"])
    pd.DataFrame(linhas).to_csv(f"{OUT}/e4_dinamico.csv", index=False)
    np.save(f"{OUT}/e4_hist_cold.npy", np.array(hB)); np.save(f"{OUT}/e4_hist_warm.npy", np.array(hC)); print("E4 ok")

    # E5 - sensibilidade
    p, D, _ = instancia(G, 20, 1020); linhas = []
    for par, vals in (("alpha", [0.5, 1, 2]), ("beta", [1, 3, 5]), ("rho", [0.1, 0.5, 0.9])):
        for v in vals:
            kw = dict(ACO_KW); kw[par] = v
            for r in range(10):
                a = aco(D, seed=r, **kw)
                linhas.append({"parametro": par, "valor": v, "run": r, "custo_s": a["custo"],
                               "it_conv": iteracoes_para_convergir(a["historico"])})
    pd.DataFrame(linhas).to_csv(f"{OUT}/e5_sensibilidade.csv", index=False); print("E5 ok")
    json.dump(info, open(f"{OUT}/info.json", "w"), indent=2, ensure_ascii=False)

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "auto")
