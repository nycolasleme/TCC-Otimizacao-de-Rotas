"""Algoritmo Genético para roteamento com múltiplas paradas.
Cromossomo = permutação das paradas; seleção por torneio; Order Crossover (OX);
mutação por inversão; elitismo."""
import time
import numpy as np
from caminho_minimo import custo_rota


def _ox(p1, p2, rng):
    n = len(p1)
    a, b = sorted(rng.choice(n, 2, replace=False))
    filho = [None] * n
    filho[a:b + 1] = p1[a:b + 1]
    usados = set(filho[a:b + 1])
    resto = [g for g in p2[b + 1:] + p2[:b + 1] if g not in usados]
    pos = [k for k in list(range(b + 1, n)) + list(range(0, a))]
    for k, g in zip(pos, resto):
        filho[k] = g
    return filho


def ag(D, inicio=0, fim=None, pop=50, geracoes=80, pc=0.9, pm=0.05,
       torneio=3, elite=2, seed=None):
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    ciclo = fim is None
    genes = [k for k in range(len(D)) if k != inicio and k != fim]

    def custo(ind):
        return custo_rota(D, [inicio] + ind + ([fim] if not ciclo else []), ciclo)

    popul = [list(rng.permutation(genes)) for _ in range(pop)]
    custos = [custo(i) for i in popul]
    historico = []
    for _ in range(geracoes):
        ordem = np.argsort(custos)
        nova = [popul[k][:] for k in ordem[:elite]]
        while len(nova) < pop:
            def sel():
                c = rng.choice(pop, torneio, replace=False)
                return popul[min(c, key=lambda k: custos[k])]
            p1, p2 = sel(), sel()
            f = _ox(p1, p2, rng) if rng.random() < pc and len(genes) > 2 else p1[:]
            if rng.random() < pm * len(genes) / 5 and len(genes) > 2:  # inversão
                a, b = sorted(rng.choice(len(f), 2, replace=False))
                f[a:b + 1] = f[a:b + 1][::-1]
            nova.append(f)
        popul = nova
        custos = [custo(i) for i in popul]
        historico.append(min(custos))
    k = int(np.argmin(custos))
    rota = [inicio] + popul[k] + ([fim] if not ciclo else [])
    return {"rota": rota, "custo": custos[k], "historico": historico,
            "tempo": time.perf_counter() - t0, "avaliacoes": pop * (geracoes + 1)}
