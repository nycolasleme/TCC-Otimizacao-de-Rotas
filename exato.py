"""Métodos exatos de referência: força bruta e Held-Karp (programação dinâmica)."""
import itertools
import time
import numpy as np


def forca_bruta(D):
    t0 = time.perf_counter()
    n = len(D)
    melhor, rota = np.inf, None
    for perm in itertools.permutations(range(1, n)):
        r = (0,) + perm
        c = sum(D[r[k], r[k + 1]] for k in range(n - 1)) + D[r[-1], 0]
        if c < melhor:
            melhor, rota = c, list(r)
    return {"rota": rota, "custo": melhor, "tempo": time.perf_counter() - t0}


def held_karp(D):
    """Ótimo exato do TSP assimétrico em O(2^n n^2)."""
    t0 = time.perf_counter()
    n = len(D)
    m = n - 1
    INF = np.inf
    dp = np.full((1 << m, m), INF)
    pai = np.full((1 << m, m), -1, dtype=int)
    for j in range(m):
        dp[1 << j, j] = D[0, j + 1]
    for mask in range(1, 1 << m):
        for j in range(m):
            if not (mask >> j) & 1 or dp[mask, j] == INF:
                continue
            for k in range(m):
                if (mask >> k) & 1:
                    continue
                nm = mask | (1 << k)
                c = dp[mask, j] + D[j + 1, k + 1]
                if c < dp[nm, k]:
                    dp[nm, k], pai[nm, k] = c, j
    full = (1 << m) - 1
    fim = [dp[full, j] + D[j + 1, 0] for j in range(m)]
    j = int(np.argmin(fim))
    custo = fim[j]
    rota, mask = [], full
    while j != -1:
        rota.append(j + 1)
        pj = pai[mask, j]
        mask ^= (1 << j)
        j = pj
    return {"rota": [0] + rota[::-1], "custo": custo, "tempo": time.perf_counter() - t0}
