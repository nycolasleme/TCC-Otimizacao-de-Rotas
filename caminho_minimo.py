"""Algoritmos de caminho mínimo (Dijkstra e A*) e geração da Matriz de Custos."""
import heapq
import math
import numpy as np
from grafo import haversine


def busca(G, s, t, usar_heuristica=True, peso="custo", retornar_fechados=False):
    """A* com heurística admissível (linha reta / velocidade máxima).
    Com usar_heuristica=False, h(n)=0 e o algoritmo equivale ao Dijkstra.
    Retorna (caminho, custo, nós_expandidos); com retornar_fechados=True,
    acrescenta a lista de nós expandidos na ordem de expansão."""
    vmax = G.graph["vmax"]
    yt, xt = G.nodes[t]["y"], G.nodes[t]["x"]

    def h(u):
        if not usar_heuristica:
            return 0.0
        return haversine(G.nodes[u]["y"], G.nodes[u]["x"], yt, xt) / vmax

    g, pai = {s: 0.0}, {s: None}
    aberta, fechados, expandidos = [(h(s), s)], set(), 0
    ordem = []
    while aberta:
        _, u = heapq.heappop(aberta)
        if u in fechados:
            continue
        fechados.add(u)
        expandidos += 1
        if retornar_fechados:
            ordem.append(u)
        if u == t:
            break
        for v, d in G[u].items():
            ng = g[u] + d[peso]
            if ng < g.get(v, math.inf):
                g[v], pai[v] = ng, u
                heapq.heappush(aberta, (ng + h(v), v))
    if t not in g:
        return ([], math.inf, expandidos, ordem) if retornar_fechados else ([], math.inf, expandidos)
    caminho, n = [], t
    while n is not None:
        caminho.append(n)
        n = pai[n]
    if retornar_fechados:
        return caminho[::-1], g[t], expandidos, ordem
    return caminho[::-1], g[t], expandidos


def dijkstra_um_para_todos(G, s, alvos=None, peso="custo"):
    """Dijkstra de origem única; para quando todos os alvos forem fixados."""
    restantes = set(alvos) if alvos is not None else None
    g, pai, fila, fechados = {s: 0.0}, {s: None}, [(0.0, s)], set()
    while fila:
        du, u = heapq.heappop(fila)
        if u in fechados:
            continue
        fechados.add(u)
        if restantes is not None:
            restantes.discard(u)
            if not restantes:
                break
        for v, d in G[u].items():
            nd = du + d[peso]
            if nd < g.get(v, math.inf):
                g[v], pai[v] = nd, u
                heapq.heappush(fila, (nd, v))
    return g, pai


def _reconstruir(pai, t):
    c, n = [], t
    while n is not None:
        c.append(n)
        n = pai.get(n)
    return c[::-1]


def matriz_custos(G, paradas, linhas=None, D=None, caminhos=None):
    """Matriz n x n (assimétrica) de custos entre paradas + caminhos no grafo.
    Se 'linhas' for informado, recalcula apenas essas linhas (atualização seletiva)."""
    n = len(paradas)
    if D is None:
        D = np.zeros((n, n))
        caminhos = {}
    linhas = range(n) if linhas is None else linhas
    for i in linhas:
        g, pai = dijkstra_um_para_todos(G, paradas[i], alvos=paradas)
        for j in range(n):
            if i != j:
                D[i, j] = g.get(paradas[j], math.inf)
                caminhos[(i, j)] = _reconstruir(pai, paradas[j])
    return D, caminhos


def custo_rota(D, rota, ciclo=True):
    c = sum(D[rota[k], rota[k + 1]] for k in range(len(rota) - 1))
    return c + (D[rota[-1], rota[0]] if ciclo else 0.0)
