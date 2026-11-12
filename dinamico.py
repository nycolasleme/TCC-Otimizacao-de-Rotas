"""Roteamento dinâmico: veículo em rota + evento de trânsito + reotimização ACO."""
import time
import numpy as np
from aco import aco, tau_inicial, tau_reaproveitado
from caminho_minimo import matriz_custos, custo_rota
from transito import aplicar_evento, pares_afetados


def escolher_centro_evento(G, rota, caminhos, k_atual, rng):
    """Escolhe o centro do evento sobre um trecho ainda NÃO percorrido da rota."""
    trechos = [(rota[a], rota[a + 1]) for a in range(k_atual + 1, len(rota) - 1)]
    i, j = trechos[rng.integers(len(trechos))]
    cam = caminhos[(i, j)]
    return cam[len(cam) // 2]


def custo_por_caminhos(G, rota, caminhos):
    """Custo da rota percorrendo os MESMOS trechos de rua planejados antes do evento."""
    total = 0.0
    for a in range(len(rota) - 1):
        cam = caminhos[(rota[a], rota[a + 1])]
        total += sum(G[cam[k]][cam[k + 1]]["custo"] for k in range(len(cam) - 1))
    return total


def simular(G, paradas, D, caminhos, resultado_inicial, k_atual=5, fator=5.0,
            raio=500, gamma=0.3, n_iter=100, n_formigas=20, alpha=1.0, beta=3.0,
            rho=0.5, seed=0, centro=None):
    """Executa o cenário dinâmico completo. Retorna métricas das rotas A, B e C.
    Sem sistema = mesma ordem e mesmas ruas, sob o novo trânsito;
    A = mesma ordem, mas trechos recalculados pelo caminho mínimo atualizado;
    B = reotimização ACO com feromônio reiniciado (cold start);
    C = reotimização ACO reaproveitando o feromônio (warm start)."""
    rng = np.random.default_rng(seed)
    rota = resultado_inicial["rota"]                 # rota fechada iniciando no depósito 0
    atual = rota[k_atual]                           # posição do veículo (índice na matriz)
    restantes = rota[k_atual + 1:]
    if centro is None:
        centro = escolher_centro_evento(G, rota + [0], caminhos, k_atual, rng)

    afetados = aplicar_evento(G, centro, raio, fator)
    idx = [atual] + restantes + [0]
    custo_sem_sistema = custo_por_caminhos(G, idx, caminhos)   # mesma ordem e mesmas ruas

    # Atualização seletiva da matriz: só linhas com algum par afetado
    t0 = time.perf_counter()
    pares = pares_afetados(caminhos, afetados)
    linhas = sorted({i for i, _ in pares})
    D_novo, cam_novo = matriz_custos(G, paradas, linhas=linhas, D=D.copy(), caminhos=dict(caminhos))
    t_seletivo = time.perf_counter() - t0

    # Subproblema: [atual] + restantes + [depósito]
    Ds = D_novo[np.ix_(idx, idx)]
    fim = len(idx) - 1
    rota_A = list(range(len(idx)))                  # mesma ordem planejada
    custo_A = custo_rota(Ds, rota_A, ciclo=False)
    custo_A_previsto = custo_rota(D[np.ix_(idx, idx)], rota_A, ciclo=False)

    kw = dict(inicio=0, fim=fim, n_iter=n_iter, n_formigas=n_formigas,
              alpha=alpha, beta=beta, rho=rho, seed=seed)
    B = aco(Ds, **kw)
    t0n = tau_inicial(Ds, 0, fim)
    tau_w = tau_reaproveitado(resultado_inicial["tau"], idx, t0n, gamma)
    C = aco(Ds, tau=tau_w, **kw)

    return {
        "centro": centro, "afetados": afetados, "pares_afetados": len(pares),
        "linhas_recalculadas": len(linhas), "t_seletivo": t_seletivo,
        "idx": idx, "D_novo": D_novo, "caminhos_novos": cam_novo,
        "custo_A_previsto": custo_A_previsto, "custo_sem_sistema": custo_sem_sistema,
        "custo_A": custo_A,
        "B": B, "C": C,
    }


def iteracoes_para_convergir(historico, tol=0.01):
    final = historico[-1]
    for k, c in enumerate(historico):
        if c <= final * (1 + tol):
            return k + 1
    return len(historico)
