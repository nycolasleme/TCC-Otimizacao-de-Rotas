"""Gera as figuras do capítulo de Resultados a partir de resultados/*.csv."""
import os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from grafo import carregar_grafo
from caminho_minimo import busca

OUT = "figuras"; os.makedirs(OUT, exist_ok=True)
R = "resultados"
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GRAY, INK, INK2 = "#9a9a96", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#bdbdb8",
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#ececea", "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "legend.frameon": False, "savefig.dpi": 220, "savefig.bbox": "tight"})


def fig_malha_e_busca(G):
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.7))
    # (a) malha
    ax = axs[0]
    for u, v, d in G.edges(data=True):
        x = [G.nodes[u]["x"], G.nodes[v]["x"]]; y = [G.nodes[u]["y"], G.nodes[v]["y"]]
        if d["speed_kph"] >= 60:
            ax.plot(x, y, color=C1, lw=1.4, zorder=2)
        elif G.has_edge(v, u):
            ax.plot(x, y, color="#6b6b66", lw=0.7, zorder=1)
        else:
            ax.plot(x, y, color="#c9c9c4", lw=0.6, zorder=1)
    ax.plot([], [], color=C1, lw=1.4, label="Avenida (60 km/h, mão dupla)")
    ax.plot([], [], color="#6b6b66", lw=0.8, label="Rua de mão dupla")
    ax.plot([], [], color="#c9c9c4", lw=0.8, label="Rua de mão única")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), fontsize=7, ncol=1)
    ax.set_title("(a) Malha viária modelada", fontsize=9, color=INK)
    # (b,c) nós expandidos Dijkstra x A*
    nos = sorted(G.nodes, key=lambda n: (G.nodes[n]["y"], G.nodes[n]["x"]))
    s, t = nos[len(nos) // 2 - 12], nos[int(len(nos) * 0.83) + 25]
    for ax, (nome, h) in zip(axs[1:], (("Dijkstra", False), ("A*", True))):
        # reexecuta registrando expandidos
        import heapq, math
        from grafo import haversine
        vmax = G.graph["vmax"]; yt, xt = G.nodes[t]["y"], G.nodes[t]["x"]
        hf = (lambda u: haversine(G.nodes[u]["y"], G.nodes[u]["x"], yt, xt) / vmax) if h else (lambda u: 0)
        g, fila, fech = {s: 0}, [(hf(s), s)], []
        vist = set()
        while fila:
            _, u = heapq.heappop(fila)
            if u in vist: continue
            vist.add(u); fech.append(u)
            if u == t: break
            for v, d in G[u].items():
                if g[u] + d["custo"] < g.get(v, math.inf):
                    g[v] = g[u] + d["custo"]; heapq.heappush(fila, (g[v] + hf(v), v))
        cam, c, ex = busca(G, s, t, usar_heuristica=h)
        for u, v in G.edges():
            ax.plot([G.nodes[u]["x"], G.nodes[v]["x"]], [G.nodes[u]["y"], G.nodes[v]["y"]], color="#e6e6e2", lw=0.5, zorder=1)
        ax.scatter([G.nodes[n]["x"] for n in fech], [G.nodes[n]["y"] for n in fech], s=4, color=C4, zorder=2)
        ax.plot([G.nodes[n]["x"] for n in cam], [G.nodes[n]["y"] for n in cam], color=C1, lw=2, zorder=3)
        ax.scatter([G.nodes[s]["x"], G.nodes[t]["x"]], [G.nodes[s]["y"], G.nodes[t]["y"]], s=40, color=INK, zorder=4, marker="s")
        ax.set_title(f"({'b' if not h else 'c'}) {nome}: {ex} nós expandidos", fontsize=9, color=INK)
    for ax in axs:
        ax.set_aspect(1.09); ax.axis("off")
    axs[1].scatter([], [], s=10, color=C4, label="Nós expandidos"); axs[1].plot([], [], color=C1, lw=2, label="Caminho mínimo")
    axs[1].legend(loc="upper center", bbox_to_anchor=(1.1, -0.02), ncol=2, fontsize=7)
    fig.savefig(f"{OUT}/fig_malha_busca.png"); plt.close(fig)


def fig_estatico():
    e2 = pd.read_csv(f"{R}/e2_estatico.csv")
    best = e2.groupby("n").custo_s.min()
    e2["ref"] = e2.otimo_s.fillna(e2.n.map(best)); e2["gap"] = (e2.custo_s / e2.ref - 1) * 100
    aco_h = np.load(f"{R}/e3_conv_aco.npy") / 60; ag_h = np.load(f"{R}/e3_conv_ag.npy") / 60
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
    ax = axs[0]
    xa = np.arange(1, aco_h.shape[1] + 1) * 20; xg = np.arange(1, ag_h.shape[1] + 1) * 50
    for h, x, c, nome in ((aco_h, xa, C1, "ACO"), (ag_h, xg, C2, "AG")):
        m, sd = h.mean(0), h.std(0)
        ax.fill_between(x, m - sd, m + sd, color=c, alpha=0.15, lw=0)
        ax.plot(x, m, color=c, lw=2, label=nome)
        ax.annotate(f"{nome}: {m[-1]:.1f} min", (x[-1], m[-1]), xytext=(4, 0), textcoords="offset points", fontsize=8, color=INK, va="center")
    ax.set_xlabel("Rotas avaliadas"); ax.set_ylabel("Melhor custo (min)")
    ax.set_title("(a) Convergência média – 30 paradas (30 execuções)", fontsize=9, color=INK, loc="left")
    ax.legend(loc="upper right"); ax.set_xlim(0, 4600)
    ax = axs[1]
    ns = [5, 10, 15, 20, 30, 50]
    for alg, c, mk in (("ACO", C1, "o"), ("AG", C2, "s")):
        d = e2[e2.algoritmo == alg].groupby("n").gap
        m, sd = d.mean().loc[ns], d.std().loc[ns]
        ax.errorbar(ns, m, yerr=sd, color=c, lw=2, marker=mk, ms=5, capsize=3, label=alg)
        ax.annotate(f"{m.iloc[-1]:.1f}%", (ns[-1], m.iloc[-1]), xytext=(6, 0), textcoords="offset points", fontsize=8, color=INK, va="center")
    ax.set_xlabel("Número de paradas"); ax.set_ylabel("Gap médio para a referência (%)")
    ax.set_xticks(ns); ax.set_xlim(3, 56)
    ax.set_title("(b) Gap médio ± desvio-padrão (30 execuções)", fontsize=9, color=INK, loc="left"); ax.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(f"{OUT}/fig_estatico.png"); plt.close(fig)


def fig_escalabilidade():
    e = pd.read_csv(f"{R}/e2b_escalabilidade.csv")
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for m, c, mk in (("Força bruta", C2, "o"), ("Held-Karp", C4, "s"), ("ACO", C1, "^")):
        d = e[e.metodo == m]
        ax.plot(d.n, d.tempo_s * 1000, color=c, lw=2, marker=mk, ms=5, label=m)
    ax.set_yscale("log"); ax.set_xlabel("Número de paradas (n)"); ax.set_ylabel("Tempo de execução (ms, escala log)")
    ax.legend(); fig.savefig(f"{OUT}/fig_escalabilidade.png"); plt.close(fig)


def fig_dinamico():
    e4 = pd.read_csv(f"{R}/e4_dinamico.csv")
    e4["sistema_s"] = e4[["so_caminhos_s", "cold_s", "warm_s"]].min(axis=1)
    hB = np.load(f"{R}/e4_hist_cold.npy"); hC = np.load(f"{R}/e4_hist_warm.npy")
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.3), gridspec_kw=dict(width_ratios=[1.1, 1]))
    ax = axs[0]
    nomes = ["Planejado\n(sem trânsito)", "Rota original\nsob trânsito", "Mesma ordem,\nnovos caminhos (A*)", "ACO\nreiniciado", "ACO\nreaproveitado"]
    cols = ["previsto_s", "sem_sistema_s", "so_caminhos_s", "cold_s", "warm_s"]
    vals = [e4[c].mean() / 60 for c in cols]; sds = [e4[c].std() / 60 for c in cols]
    cores = [GRAY, C2, C4, C1, C3]
    b = ax.bar(range(5), vals, color=cores, width=0.62, yerr=sds, error_kw=dict(ecolor="#6b6b66", lw=1, capsize=3))
    for k, v in enumerate(vals):
        ax.text(k, v - 1.2, f"{v:.1f}", ha="center", va="top", fontsize=8.5, color="white", fontweight="bold")
    ax.set_xticks(range(5)); ax.set_xticklabels(nomes, fontsize=7); ax.set_ylabel("Tempo restante de rota (min)")
    ax.set_title("(a) Custo médio do trecho restante (30 cenários)", fontsize=9, color=INK, loc="left")
    ax = axs[1]
    x = np.arange(1, hB.shape[1] + 1)
    for h, c, nome in ((hB / hB[:, -1:], C1, "Feromônio reiniciado"), (hC / hB[:, -1:], C3, "Feromônio reaproveitado")):
        m = (h.mean(0) - 1) * 100
        ax.plot(x, m, color=c, lw=2, label=nome)
    ax.set_xlabel("Iteração da reotimização"); ax.set_ylabel("Excesso sobre o custo final (%)")
    ax.set_xlim(1, 60); ax.set_title("(b) Velocidade de readaptação (média)", fontsize=9, color=INK, loc="left"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{OUT}/fig_dinamico.png"); plt.close(fig)


if __name__ == "__main__":
    G = carregar_grafo("sintetico")
    fig_malha_e_busca(G); fig_estatico(); fig_escalabilidade(); fig_dinamico()
    print("ok")
