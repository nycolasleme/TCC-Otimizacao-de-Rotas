"""Otimização por Colônia de Formigas (ACO) — estática e dinâmica.

Implementa o Algoritmo 2 da Fundamentação (Ant System com reforço elitista).
- inicio: índice de partida; fim=None => rota fechada (retorna ao início);
  fim=k => caminho aberto que termina em k (usado na reotimização dinâmica).
"""
import time
import numpy as np
from caminho_minimo import custo_rota


def vizinho_mais_proximo(D, inicio=0, fim=None):
    n = len(D)
    rota, rest = [inicio], set(range(n)) - {inicio} - ({fim} if fim is not None else set())
    while rest:
        i = rota[-1]
        j = min(rest, key=lambda k: D[i, k])
        rota.append(j); rest.remove(j)
    if fim is not None:
        rota.append(fim)
    return rota, custo_rota(D, rota, ciclo=fim is None)


def tau_inicial(D, inicio=0, fim=None):
    _, cnn = vizinho_mais_proximo(D, inicio, fim)
    return 1.0 / (len(D) * cnn)


def aco(D, inicio=0, fim=None, n_formigas=20, n_iter=200, alpha=1.0, beta=3.0,
        rho=0.5, elitismo=1.0, tau=None, seed=None, callback=None, limites=True,
        registrar=False):
    """registrar=True guarda a evolução da melhor rota (para visualização), sem
    alterar o comportamento estocástico do algoritmo."""
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    n = len(D)
    ciclo = fim is None
    Dm = D.copy(); np.fill_diagonal(Dm, 1.0)
    eta_beta = (1.0 / Dm) ** beta                     # informação heurística ^ beta
    tau0 = tau_inicial(D, inicio, fim)
    tau = np.full((n, n), tau0) if tau is None else tau.copy()
    visitar = [k for k in range(n) if k != inicio and k != fim]
    melhor_rota, melhor_custo, historico = None, np.inf, []
    evolucao = []

    for it in range(n_iter):
        W = (tau ** alpha) * eta_beta                 # numerador da Equação (2)
        solucoes = []
        for _ in range(n_formigas):
            rota, rest = [inicio], list(visitar)
            while rest:
                w = W[rota[-1], rest]
                s = w.sum()
                p = w / s if s > 0 else None
                idx = rng.choice(len(rest), p=p)      # escolha estocástica do próximo nó
                rota.append(rest.pop(idx))
            if not ciclo:
                rota.append(fim)
            c = custo_rota(D, rota, ciclo)
            solucoes.append((rota, c))
            if c < melhor_custo:
                melhor_rota, melhor_custo = rota, c
                if registrar:
                    evolucao.append((it + 1, list(rota), c))
        tau *= (1.0 - rho)                            # evaporação
        for rota, c in solucoes + [(melhor_rota, melhor_custo / elitismo)] if elitismo else solucoes:
            arcos = list(zip(rota[:-1], rota[1:])) + ([(rota[-1], rota[0])] if ciclo else [])
            for i, j in arcos:                        # depósito de feromônio
                tau[i, j] += 1.0 / c
        if limites:                                   # limites Max-Min (Stützle; Hoos, 2000)
            tmax = 1.0 / (rho * melhor_custo)
            np.clip(tau, tmax / (2 * n), tmax, out=tau)
        historico.append(melhor_custo)
        if callback:
            callback(it, melhor_custo)
    return {"rota": melhor_rota, "custo": melhor_custo, "historico": historico,
            "tau": tau, "tau0": tau0, "tempo": time.perf_counter() - t0,
            "avaliacoes": n_formigas * n_iter, "evolucao": evolucao}


def tau_reaproveitado(tau_antigo, indices_antigos, tau0_novo, gamma=0.3):
    """Estratégia de modificação de feromônio para TSP dinâmico
    (Guntsch; Middendorf, 2001): recorta a matriz antiga para as paradas
    restantes e a suaviza em direção ao valor inicial."""
    sub = tau_antigo[np.ix_(indices_antigos, indices_antigos)]
    sub = sub / sub.mean() * tau0_novo                # normaliza a escala
    return (1.0 - gamma) * sub + gamma * tau0_novo
