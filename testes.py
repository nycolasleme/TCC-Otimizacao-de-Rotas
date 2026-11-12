"""Testes de validação do sistema RotaFormiga.

Executar:  python testes.py      (ou pela aba "Experimentos e validação" da interface)
Cada teste devolve (nome, aprovado, detalhe)."""
import math
import numpy as np

from grafo import carregar_sintetico, estatisticas
from caminho_minimo import busca, matriz_custos, custo_rota
from aco import aco, tau_inicial, tau_reaproveitado
from ag import ag
from exato import forca_bruta, held_karp
from transito import aplicar_evento, limpar_transito, pares_afetados
from dinamico import simular


def _instancia(G, n, seed):
    rng = np.random.default_rng(seed)
    p = [int(x) for x in rng.choice(list(G.nodes), n + 1, replace=False)]
    D, cam = matriz_custos(G, p)
    return p, D, cam


def t_grafo(G):
    e = estatisticas(G)
    import networkx as nx
    ok = nx.is_strongly_connected(G) and e["vertices"] > 1000
    return "Malha é um dígrafo fortemente conexo", ok, f"{e['vertices']} vértices, {e['arcos']} arcos"


def t_astar_igual_dijkstra(G):
    rng = np.random.default_rng(1); nos = list(G.nodes); dif = 0; menos = 0
    for _ in range(30):
        s, t = [int(x) for x in rng.choice(nos, 2, replace=False)]
        _, c1, e1 = busca(G, s, t, usar_heuristica=False)
        _, c2, e2 = busca(G, s, t, usar_heuristica=True)
        dif += abs(c1 - c2) > 1e-6; menos += e2 <= e1
    return "A* encontra o mesmo custo ótimo do Dijkstra", dif == 0 and menos == 30, \
        f"30 pares: {30 - dif} custos iguais; A* expandiu ≤ nós em {menos}/30"


def t_heuristica_admissivel(G):
    rng = np.random.default_rng(2); nos = list(G.nodes); viol = 0
    from grafo import haversine
    for _ in range(30):
        s, t = [int(x) for x in rng.choice(nos, 2, replace=False)]
        _, c, _ = busca(G, s, t, usar_heuristica=False)
        h = haversine(G.nodes[s]["y"], G.nodes[s]["x"], G.nodes[t]["y"], G.nodes[t]["x"]) / G.graph["vmax"]
        viol += h > c + 1e-9
    return "Heurística nunca superestima o custo real (admissível)", viol == 0, f"{viol} violações em 30 pares"


def t_matriz_assimetrica(G):
    _, D, cam = _instancia(G, 10, 3)
    ok_diag = np.allclose(np.diag(D), 0)
    ok_cam = all(cam[(i, j)][0] != cam[(i, j)][-1] for (i, j) in cam)
    assim = int((np.abs(D - D.T) > 1e-6).sum() // 2)
    return "Matriz de custos válida e assimétrica (mão única)", ok_diag and ok_cam and assim > 0, \
        f"{assim} de 55 pares com D[i][j] ≠ D[j][i]"


def t_held_karp(G):
    _, D, _ = _instancia(G, 7, 4)
    fb, hk = forca_bruta(D), held_karp(D)
    ok = abs(fb["custo"] - hk["custo"]) < 1e-6 and abs(custo_rota(D, hk["rota"]) - hk["custo"]) < 1e-6
    return "Held-Karp coincide com a força bruta", ok, f"ótimo = {hk['custo'] / 60:.2f} min"


def t_aco_valido(G):
    _, D, _ = _instancia(G, 15, 5)
    r = aco(D, seed=0, n_iter=60)
    perm = sorted(r["rota"]) == list(range(len(D))) and r["rota"][0] == 0
    coerente = abs(custo_rota(D, r["rota"]) - r["custo"]) < 1e-6
    mono = all(r["historico"][k] >= r["historico"][k + 1] for k in range(len(r["historico"]) - 1))
    return "ACO gera rota válida e convergência monotônica", perm and coerente and mono, \
        f"rota com {len(r['rota'])} pontos, custo {r['custo'] / 60:.2f} min"


def t_aco_otimo(G):
    _, D, _ = _instancia(G, 8, 6)
    hk = held_karp(D)["custo"]
    acertos = sum(abs(aco(D, seed=s, n_iter=150)["custo"] - hk) < 1e-6 for s in range(5))
    return "ACO alcança o ótimo exato em cenário pequeno (8 paradas)", acertos >= 4, f"{acertos}/5 execuções no ótimo"


def t_aco_reprodutivel(G):
    _, D, _ = _instancia(G, 12, 7)
    a, b = aco(D, seed=3, n_iter=50), aco(D, seed=3, n_iter=50)
    return "ACO é reprodutível com a mesma semente", a["rota"] == b["rota"], "mesma rota nas duas execuções"


def t_ag_valido(G):
    _, D, _ = _instancia(G, 15, 8)
    r = ag(D, seed=0)
    ok = sorted(r["rota"]) == list(range(len(D))) and abs(custo_rota(D, r["rota"]) - r["custo"]) < 1e-6
    return "AG gera permutação válida", ok, f"custo {r['custo'] / 60:.2f} min"


def t_transito(G):
    limpar_transito(G)
    p, D, cam = _instancia(G, 10, 9)
    i, j = 0, 1
    meio = cam[(i, j)][len(cam[(i, j)]) // 2]
    afet = aplicar_evento(G, meio, 400, 5.0)
    D2, _ = matriz_custos(G, p)
    pares = pares_afetados(cam, afet)
    so_aumenta = bool(np.all(D2 >= D - 1e-9))
    intactos = all(abs(D2[a, b] - D[a, b]) < 1e-6 for (a, b) in cam if (a, b) not in pares)
    limpar_transito(G)
    D3, _ = matriz_custos(G, p)
    return "Evento só aumenta custos e pares não afetados permanecem ótimos", \
        so_aumenta and intactos and np.allclose(D3, D), f"{len(afet)} vias afetadas, {len(pares)} pares afetados"


def t_dinamico(G):
    limpar_transito(G)
    p, D, cam = _instancia(G, 15, 10)
    a = aco(D, seed=0, n_iter=100)
    r = simular(G, p, D, cam, a, k_atual=4, seed=0, n_iter=50)
    limpar_transito(G)
    restantes = set(a["rota"][5:]) | {a["rota"][4], 0}
    rotaC = [r["idx"][k] for k in r["C"]["rota"]]
    ok = set(rotaC) == restantes and rotaC[0] == a["rota"][4] and rotaC[-1] == 0
    ok = ok and r["custo_A"] <= r["custo_sem_sistema"] + 1e-6
    return "Reotimização dinâmica cobre todas as paradas restantes", ok, \
        f"sem sistema {r['custo_sem_sistema'] / 60:.1f} min → reotimizada {min(r['B']['custo'], r['C']['custo'], r['custo_A']) / 60:.1f} min"


def t_feromonio(G):
    tau = np.random.default_rng(0).random((6, 6)) + 0.1
    t = tau_reaproveitado(tau, [0, 2, 4], 0.01, gamma=0.3)
    ok = t.shape == (3, 3) and np.all(t > 0) and abs(t.mean() - 0.01) < 1e-9
    return "Reaproveitamento de feromônio preserva escala τ₀", ok, "submatriz 3×3 normalizada"


TESTES = [t_grafo, t_astar_igual_dijkstra, t_heuristica_admissivel, t_matriz_assimetrica, t_held_karp,
          t_aco_valido, t_aco_otimo, t_aco_reprodutivel, t_ag_valido, t_transito, t_dinamico, t_feromonio]


def executar(G=None, callback=None):
    G = G if G is not None else carregar_sintetico()
    res = []
    for k, t in enumerate(TESTES):
        try:
            res.append(t(G))
        except Exception as e:  # um erro conta como reprovação
            res.append((t.__name__, False, f"erro: {e}"))
        if callback:
            callback(k + 1, len(TESTES))
    limpar_transito(G)
    return res


if __name__ == "__main__":
    r = executar()
    for nome, ok, det in r:
        print(("✅" if ok else "❌"), nome, "—", det)
    print(f"\n{sum(ok for _, ok, _ in r)}/{len(r)} testes aprovados")
