"""Interface gráfica do sistema RotaFormiga (Streamlit).

Execução: duplo clique em iniciar.bat (Windows) / iniciar.sh (Linux/Mac)
ou, manualmente:  python -m streamlit run app.py
"""
import io
import os
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from grafo import carregar_grafo, carregar_sintetico, estatisticas
from caminho_minimo import matriz_custos, busca, custo_rota
from aco import aco
from ag import ag
from exato import held_karp
from dinamico import simular
from transito import EVENTOS, limpar_transito

st.set_page_config(page_title="RotaFormiga – Otimização de Rotas", page_icon="🐜", layout="wide")

CORES = {"ACO": "#d1242f", "AG": "#8250df"}
PASTA = os.path.dirname(os.path.abspath(__file__))


# ======================================================================
# Utilidades
# ======================================================================
@st.cache_resource(show_spinner="Carregando a malha viária...")
def obter_grafo(fonte):
    """Carrega a malha. Se o OpenStreetMap não estiver acessível, usa a malha sintética."""
    if fonte == "osm":
        try:
            return carregar_grafo("osm"), None
        except Exception as e:  # sem internet, bloqueio, OSMnx ausente...
            return carregar_sintetico(), f"Não foi possível carregar o OpenStreetMap ({type(e).__name__}). " \
                                         "Usando a malha sintética de Jundiaí."
    return carregar_grafo("sintetico"), None


def linhas_xy(G, arcos):
    xs, ys = [], []
    for u, v in arcos:
        xs += [G.nodes[u]["x"], G.nodes[v]["x"], None]
        ys += [G.nodes[u]["y"], G.nodes[v]["y"], None]
    return xs, ys


def caminho_xy(G, caminhos, rota, idx=None):
    xs, ys = [], []
    for a in range(len(rota) - 1):
        i, j = rota[a], rota[a + 1]
        if idx is not None:
            i, j = idx[i], idx[j]
        for n in caminhos[(i, j)]:
            xs.append(G.nodes[n]["x"]); ys.append(G.nodes[n]["y"])
    return xs, ys


def nome_parada(k):
    return "Depósito" if k == 0 else f"Parada {k}"


def desenhar_mapa(G, paradas, camadas, altura=620):
    fig = go.Figure()
    xs, ys = linhas_xy(G, G.edges)
    fig.add_trace(go.Scattergl(x=xs, y=ys, mode="lines", line=dict(color="#cfd4da", width=1),
                               hoverinfo="skip", name="Malha viária"))
    for c in camadas:
        fig.add_trace(go.Scattergl(**c))
    if paradas:
        px = [G.nodes[p]["x"] for p in paradas]; py = [G.nodes[p]["y"] for p in paradas]
        fig.add_trace(go.Scatter(x=px[1:], y=py[1:], mode="markers+text", text=[str(k) for k in range(1, len(paradas))],
                                 textposition="top center", marker=dict(size=10, color="#1f6feb"), name="Paradas",
                                 hovertext=[f"Parada {k}" for k in range(1, len(paradas))], hoverinfo="text"))
        fig.add_trace(go.Scatter(x=px[:1], y=py[:1], mode="markers+text", text=["Depósito"], textposition="bottom center",
                                 marker=dict(size=16, color="#111", symbol="square"), name="Depósito", hoverinfo="text",
                                 hovertext=["Depósito"]))
    fig.update_layout(height=altura, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.02), xaxis=dict(visible=False),
                      yaxis=dict(visible=False, scaleanchor="x", scaleratio=1.09))
    return fig


def camadas_feromonio(G, paradas, tau, top=2):
    """Trilhas de feromônio: para cada parada, os `top` trechos de saída com mais feromônio.
    Espessura e opacidade proporcionais à quantidade relativa de τ."""
    n = len(tau)
    w = tau / tau.max()
    arestas = []
    for i in range(n):
        lin = w[i].copy(); lin[i] = -1
        for j in np.argsort(lin)[::-1][:top]:
            arestas.append((i, int(j), lin[j]))
    faixas = [(0.0, 0.4), (0.4, 0.7), (0.7, 0.9), (0.9, 1.01)]
    out = []
    for k, (lo, hi) in enumerate(faixas):
        xs, ys = [], []
        for i, j, v in arestas:
            if lo <= v < hi:
                xs += [G.nodes[paradas[i]]["x"], G.nodes[paradas[j]]["x"], None]
                ys += [G.nodes[paradas[i]]["y"], G.nodes[paradas[j]]["y"], None]
        if xs:
            out.append(dict(x=xs, y=ys, mode="lines", hoverinfo="skip",
                            line=dict(color=f"rgba(237,161,0,{0.25 + 0.18 * k})", width=1 + 1.6 * k),
                            name="Trilhas de feromônio", legendgroup="tau", showlegend=k == 0))
    return out


def itinerario(G, paradas, D, caminhos, rota, idx=None):
    """Tabela trecho a trecho: tempo, distância e horário acumulado."""
    linhas, acum, km_acum = [], 0.0, 0.0
    for a in range(len(rota) - 1):
        i, j = rota[a], rota[a + 1]
        gi, gj = (idx[i], idx[j]) if idx is not None else (i, j)
        cam = caminhos[(gi, gj)]
        km = sum(G[cam[k]][cam[k + 1]]["length"] for k in range(len(cam) - 1)) / 1000
        t = D[gi, gj] / 60
        acum += t; km_acum += km
        linhas.append({"Trecho": a + 1, "De": nome_parada(gi), "Para": nome_parada(gj),
                       "Tempo do trecho (min)": round(t, 2), "Distância (km)": round(km, 2),
                       "Chegada acumulada (min)": round(acum, 2), "Distância acumulada (km)": round(km_acum, 2)})
    return pd.DataFrame(linhas)


def baixar_csv(df, nome, rotulo="⬇️ Baixar itinerário (CSV)"):
    buf = io.StringIO(); df.to_csv(buf, index=False, sep=";", decimal=",")
    st.download_button(rotulo, buf.getvalue().encode("utf-8-sig"), file_name=nome, mime="text/csv")


# ======================================================================
# Barra lateral
# ======================================================================
st.sidebar.title("🐜 RotaFormiga")
st.sidebar.caption("Otimização de rotas urbanas com ACO dinâmico")
fonte = st.sidebar.selectbox("Malha viária", ["sintetico", "osm"],
                             format_func=lambda f: "Sintética (Jundiaí)" if f == "sintetico" else "OpenStreetMap (real)")
G, aviso_malha = obter_grafo(fonte)
modo_paradas = st.sidebar.radio("Definição das paradas", ["Aleatórias", "Escolher no mapa"], horizontal=True,
                                help="Aleatórias: sorteadas pela semente. Escolher no mapa: clique nas interseções.")
if modo_paradas == "Aleatórias":
    n_paradas = st.sidebar.slider("Número de paradas", 5, 50, 20)
    semente = st.sidebar.number_input("Semente do cenário", 0, 9999, 7)
else:
    semente = st.sidebar.number_input("Semente do cenário", 0, 9999, 7, help="Usada na simulação de trânsito.")
algoritmo = st.sidebar.radio("Algoritmo", ["ACO", "AG", "Comparar ACO × AG"])
with st.sidebar.expander("Parâmetros do ACO", expanded=True):
    formigas = st.slider("Formigas", 5, 50, 20)
    iteracoes = st.slider("Iterações", 20, 400, 200, step=20)
    alpha = st.slider("α (peso do feromônio)", 0.0, 3.0, 1.0, 0.5)
    beta = st.slider("β (peso da distância)", 0.0, 6.0, 3.0, 0.5)
    rho = st.slider("ρ (evaporação)", 0.05, 0.95, 0.5, 0.05)
with st.sidebar.expander("Parâmetros do AG"):
    pop = st.slider("População", 10, 100, 50)
    ger = st.slider("Gerações", 10, 300, 80)
    pm = st.slider("Taxa de mutação", 0.0, 0.2, 0.05, 0.01)
with st.sidebar.expander("ℹ️ Como o sistema funciona"):
    st.markdown(
        "1. A malha viária é um **dígrafo ponderado** (vias de mão única, peso = tempo de travessia).\n"
        "2. **Dijkstra/A\\*** calculam o caminho mínimo entre cada par de paradas → **matriz de custos**.\n"
        "3. O **ACO** constrói rotas com formigas virtuais:  \n"
        "   $p_{ij} = \\dfrac{\\tau_{ij}^{\\alpha}\\,\\eta_{ij}^{\\beta}}{\\sum_{l}\\tau_{il}^{\\alpha}\\,\\eta_{il}^{\\beta}}$, "
        "com $\\eta_{ij}=1/d_{ij}$.\n"
        "4. Um **evento de trânsito** aumenta os pesos das vias; a matriz é atualizada e o ACO reotimiza "
        "as paradas restantes, **reaproveitando o feromônio**.\n"
        "5. O **AG** e os métodos exatos servem de comparação.")

# ======================================================================
# Estado da sessão
# ======================================================================
S = st.session_state
S.setdefault("manuais", [])
S.setdefault("sel_ok", None)
S.setdefault("mapa_key", 0)

if modo_paradas == "Aleatórias":
    chave = (fonte, "aleatorio", n_paradas, semente)
else:
    chave = (fonte, "manual", tuple(S.manuais))

if S.get("chave") != chave:
    limpar_transito(G)
    if modo_paradas == "Aleatórias":
        rng = np.random.default_rng(int(semente))
        paradas = [int(x) for x in rng.choice(list(G.nodes), n_paradas + 1, replace=False)]
    else:
        paradas = [n for n in S.manuais if n in G]
    if len(paradas) >= 3:
        D, cam = matriz_custos(G, paradas)
    else:
        D, cam = None, None
    S.update(chave=chave, paradas=paradas, D=D, cam=cam, res=None, dyn=None, p2p=None, otimo=None, bench=None)

n_pontos = len(S.paradas)
pronto = n_pontos >= 3

st.subheader("Otimização de Rotas em Cenários de Mobilidade Urbana")
e = estatisticas(G)
st.caption(f"Malha: {G.graph['fonte']} — {e['vertices']} interseções, {e['arcos']} trechos de via, "
           f"{e['extensao_km']:.0f} km de vias")
if aviso_malha:
    st.warning(aviso_malha)
transito_ativo = any(d["fator"] > 1 for _, _, d in G.edges(data=True))

aba1, aba2, aba3, aba4 = st.tabs(["🗺️ Roteamento com múltiplas paradas", "🚦 Trânsito dinâmico",
                                  "📍 Ponto a ponto (Dijkstra × A*)", "📊 Experimentos e validação"])

# ======================================================================
# Aba 1 — Roteamento com múltiplas paradas
# ======================================================================
with aba1:
    # ---- escolha manual das paradas ----
    if modo_paradas == "Escolher no mapa":
        with st.expander("✏️ Escolher paradas no mapa", expanded=not S.res):
            st.caption("Clique em uma interseção (ponto cinza) para adicioná-la. "
                       "O **primeiro ponto é o depósito**; os demais são as paradas. Mínimo: depósito + 2 paradas.")
            nos = list(G.nodes)
            figm = desenhar_mapa(G, S.paradas, [], altura=520)
            figm.add_trace(go.Scattergl(x=[G.nodes[n]["x"] for n in nos], y=[G.nodes[n]["y"] for n in nos],
                                        mode="markers", marker=dict(size=6, color="rgba(110,119,129,0.35)"),
                                        customdata=nos, hovertemplate="Interseção %{customdata}<extra></extra>",
                                        name="Interseções (clique)"))
            figm.update_layout(clickmode="event+select", dragmode="pan")
            ev = st.plotly_chart(figm, width="stretch", on_select="rerun", selection_mode="points",
                                 key=f"mapa_sel_{S.mapa_key}")
            pts = (ev.get("selection", {}) or {}).get("points", []) if ev else []
            assinatura = tuple(sorted(str(p.get("customdata")) for p in pts))
            if pts and assinatura != S.sel_ok:
                S.sel_ok = assinatura
                novos = [p.get("customdata") for p in pts if p.get("customdata") is not None]
                for n in novos:
                    n = int(n[0] if isinstance(n, (list, tuple)) else n)
                    if n not in S.manuais:
                        S.manuais.append(n)
                S.mapa_key += 1
                st.rerun()
            b1, b2, b3 = st.columns(3)
            b1.write(f"**{max(0, len(S.manuais) - 1)} paradas** + {'depósito' if S.manuais else 'sem depósito'}")
            if b2.button("↩️ Desfazer último ponto", disabled=not S.manuais):
                S.manuais.pop(); S.sel_ok = None; S.mapa_key += 1; st.rerun()
            if b3.button("🗑️ Limpar pontos", disabled=not S.manuais):
                S.manuais = []; S.sel_ok = None; S.mapa_key += 1; st.rerun()

    if not pronto:
        st.info("Escolha no mapa o depósito e pelo menos 2 paradas para começar.")
    else:
        if st.button("▶ Otimizar rota", type="primary"):
            limpar_transito(G); S.dyn = None
            S.D, S.cam = matriz_custos(G, S.paradas)
            res = {}
            barra = st.progress(0.0, text="Otimizando...")
            if algoritmo in ("ACO", "Comparar ACO × AG"):
                res["ACO"] = aco(S.D, n_formigas=formigas, n_iter=iteracoes, alpha=alpha, beta=beta, rho=rho, seed=0,
                                 registrar=True,
                                 callback=lambda it, c: barra.progress((it + 1) / iteracoes,
                                                                       text=f"ACO – iteração {it + 1}/{iteracoes} · melhor {c / 60:.1f} min"))
            if algoritmo in ("AG", "Comparar ACO × AG"):
                barra.progress(1.0, text="Executando o Algoritmo Genético...")
                res["AG"] = ag(S.D, pop=pop, geracoes=ger, pm=pm, seed=0)
            S.otimo = held_karp(S.D) if len(S.D) <= 11 else None
            barra.empty()
            S.res = res

        camadas = []
        rota_exibida = None
        if S.res:
            o1, o2 = st.columns([1, 1])
            mostrar_tau = o1.toggle("🐜 Mostrar trilhas de feromônio", value=False, disabled="ACO" not in S.res,
                                    help="Espessura proporcional à quantidade de feromônio entre as paradas ao final da execução.")
            evol = S.res["ACO"].get("evolucao", []) if "ACO" in S.res else []
            evol = list({it: (it, r_, c_) for it, r_, c_ in evol}.values())   # uma entrada por iteração
            passo = None
            if len(evol) > 1:
                rotulos = [f"Iteração {it} – {c / 60:.1f} min" for it, _, c in evol]
                escolha = o2.select_slider("📈 Evolução da melhor rota do ACO", options=list(range(len(evol))),
                                           value=len(evol) - 1, format_func=lambda k: rotulos[k])
                passo = evol[escolha]
            if mostrar_tau and "ACO" in S.res:
                camadas += camadas_feromonio(G, S.paradas, S.res["ACO"]["tau"])
            for nome, r in S.res.items():
                rota = r["rota"]
                if nome == "ACO" and passo is not None:
                    rota = passo[1]
                xs, ys = caminho_xy(G, S.cam, rota + [0])
                camadas.append(dict(x=xs, y=ys, mode="lines", line=dict(color=CORES[nome], width=4), name=f"Rota {nome}"))
            rota_exibida = S.res["ACO"]["rota"] if "ACO" in S.res else S.res["AG"]["rota"]

        c1, c2 = st.columns([3, 1.2])
        c1.plotly_chart(desenhar_mapa(G, S.paradas, camadas), width="stretch")
        with c2:
            if S.res:
                for nome, r in S.res.items():
                    gap = ""
                    if S.otimo:
                        g_ = (r["custo"] / S.otimo["custo"] - 1) * 100
                        gap = " · **ótimo exato** ✅" if g_ < 1e-6 else f" · {g_:.2f}% acima do ótimo"
                    st.metric(f"{nome} – tempo total da rota", f"{r['custo'] / 60:.1f} min")
                    st.caption(f"Processamento: {r['tempo']:.2f} s · {r['avaliacoes']} rotas avaliadas{gap}")
                if S.otimo:
                    st.caption(f"Ótimo exato (Held-Karp): {S.otimo['custo'] / 60:.2f} min em {S.otimo['tempo'] * 1000:.1f} ms")
                fig = go.Figure()
                for nome, r in S.res.items():
                    xs = np.linspace(0, r["avaliacoes"], len(r["historico"]))
                    fig.add_trace(go.Scatter(x=xs, y=np.array(r["historico"]) / 60, name=nome, line=dict(color=CORES[nome])))
                if S.otimo:
                    fig.add_hline(y=S.otimo["custo"] / 60, line_dash="dot", line_color="#6e7781",
                                  annotation_text="ótimo", annotation_position="bottom right")
                fig.update_layout(title="Convergência", xaxis_title="Rotas avaliadas", yaxis_title="Melhor custo (min)",
                                  height=330, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, width="stretch")
                if "ACO" in S.res:
                    st.write("**Ordem de visita (ACO):** " + " → ".join("D" if k == 0 else str(k) for k in S.res["ACO"]["rota"] + [0]))
                if "AG" in S.res:
                    st.write("**Ordem de visita (AG):** " + " → ".join("D" if k == 0 else str(k) for k in S.res["AG"]["rota"] + [0]))
            else:
                st.info("Defina os parâmetros na barra lateral e clique em **Otimizar rota**.")

        if S.res:
            nome_base = "ACO" if "ACO" in S.res else "AG"
            with st.expander(f"📋 Itinerário detalhado da rota {nome_base}"):
                df_it = itinerario(G, S.paradas, S.D, S.cam, S.res[nome_base]["rota"] + [0])
                st.dataframe(df_it, hide_index=True, width="stretch")
                t1, t2 = st.columns(2)
                t1.metric("Tempo total", f"{df_it['Tempo do trecho (min)'].sum():.1f} min")
                t2.metric("Distância total", f"{df_it['Distância (km)'].sum():.2f} km")
                baixar_csv(df_it, f"itinerario_{nome_base.lower()}.csv")
            if "ACO" in S.res:
                with st.expander("🧪 Matriz de feromônio final (τ)"):
                    tau = S.res["ACO"]["tau"]
                    rot = ["D"] + [str(k) for k in range(1, len(tau))]
                    figh = go.Figure(go.Heatmap(z=tau / tau.max(), x=rot, y=rot, colorscale="YlOrBr",
                                                colorbar=dict(title="τ relativo")))
                    figh.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Para (j)",
                                       yaxis_title="De (i)", yaxis_autorange="reversed")
                    st.plotly_chart(figh, width="stretch")
                    st.caption("Cada célula mostra quanto feromônio ficou no trecho i → j. "
                               "As células mais escuras formam a rota em que a colônia convergiu.")

# ======================================================================
# Aba 2 — Trânsito dinâmico
# ======================================================================
with aba2:
    if not S.res or "ACO" not in S.res:
        st.warning("Primeiro otimize uma rota com o ACO na aba anterior.")
    elif n_pontos < 4:
        st.warning("O cenário dinâmico precisa de pelo menos 3 paradas além do depósito.")
    else:
        a, b, c = st.columns(3)
        k_max = n_pontos - 3
        if k_max > 1:
            k_atual = a.slider("Paradas já visitadas pelo veículo", 1, k_max, min(5, k_max))
        else:
            k_atual = 1
            a.write("Paradas já visitadas pelo veículo: **1**")
        evento = b.selectbox("Evento de trânsito", list(EVENTOS), index=2)
        raio = c.slider("Raio do evento (m)", 200, 1200, 500, 100)
        bb1, bb2 = st.columns([1, 4])
        if bb1.button("🚨 Simular evento de trânsito", type="primary"):
            limpar_transito(G)
            with st.spinner("Atualizando a matriz e reotimizando com o ACO..."):
                S.dyn = simular(G, S.paradas, S.D, S.cam, S.res["ACO"], k_atual=k_atual, fator=EVENTOS[evento],
                                raio=raio, n_iter=100, n_formigas=formigas, alpha=alpha, beta=beta, rho=rho,
                                seed=int(semente))
                S.dyn.update(k_atual=k_atual, evento=evento)
            st.rerun()
        if S.dyn and bb2.button("🧹 Limpar trânsito"):
            limpar_transito(G); S.dyn = None; st.rerun()
        if S.dyn:
            d = S.dyn
            k_atual, evento = d.get("k_atual", k_atual), d.get("evento", evento)
            rota0 = S.res["ACO"]["rota"] + [0]
            xs_f, ys_f = caminho_xy(G, S.cam, rota0[:k_atual + 1])
            xs_o, ys_o = caminho_xy(G, S.cam, rota0[k_atual:])
            xs_e, ys_e = linhas_xy(G, d["afetados"])
            opcoes = {"custo_A": d["custo_A"], "B": d["B"]["custo"], "C": d["C"]["custo"]}
            melhor = min(opcoes, key=opcoes.get)
            if melhor == "custo_A":
                rota_nova = list(range(len(d["idx"])))
            else:
                rota_nova = d[melhor]["rota"]
            xs_n, ys_n = caminho_xy(G, d["caminhos_novos"], rota_nova, idx=d["idx"])
            camadas = [dict(x=xs_f, y=ys_f, mode="lines", line=dict(color="#6e7781", width=4), name="Trecho já percorrido"),
                       dict(x=xs_o, y=ys_o, mode="lines", line=dict(color="#d1242f", width=3, dash="dot"), name="Rota original"),
                       dict(x=xs_n, y=ys_n, mode="lines", line=dict(color="#1a7f37", width=4), name="Rota reotimizada (ACO)"),
                       dict(x=xs_e, y=ys_e, mode="lines", line=dict(color="rgba(255,140,0,0.55)", width=6), name=f"Vias afetadas ({evento})")]
            pos = S.paradas[rota0[k_atual]]
            camadas.append(dict(x=[G.nodes[pos]["x"]], y=[G.nodes[pos]["y"]], mode="markers",
                                marker=dict(size=18, color="#1a7f37", symbol="diamond", line=dict(color="white", width=2)),
                                name="Posição do veículo"))
            c1, c2 = st.columns([3, 1.2])
            c1.plotly_chart(desenhar_mapa(G, S.paradas, camadas), width="stretch")
            with c2:
                sem = d["custo_sem_sistema"]; nov = opcoes[melhor]
                st.metric("Seguir rota original", f"{sem / 60:.1f} min")
                st.metric("Rota reotimizada", f"{nov / 60:.1f} min", delta=f"{(nov - sem) / 60:.1f} min", delta_color="inverse")
                st.caption(f"{len(d['afetados'])} vias afetadas · {d['linhas_recalculadas']} de {len(S.paradas)} "
                           f"linhas da matriz recalculadas em {d['t_seletivo'] * 1000:.0f} ms")
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=np.array(d["B"]["historico"]) / 60, name="Feromônio reiniciado"))
                fig.add_trace(go.Scatter(y=np.array(d["C"]["historico"]) / 60, name="Feromônio reaproveitado"))
                fig.update_layout(title="Reotimização", xaxis_title="Iteração", yaxis_title="Custo (min)",
                                  height=330, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, width="stretch")

            with st.expander("📊 Comparação das estratégias de reação ao trânsito", expanded=True):
                linhas = [("Planejado, antes do evento", d["custo_A_previsto"]),
                          ("Rota original sob trânsito (sem sistema)", sem),
                          ("Mesma ordem, caminhos recalculados (A*)", d["custo_A"]),
                          ("ACO com feromônio reiniciado", d["B"]["custo"]),
                          ("ACO com feromônio reaproveitado", d["C"]["custo"])]
                df = pd.DataFrame([{"Estratégia": n, "Tempo restante (min)": round(v / 60, 2),
                                    "Redução vs. rota original": "–" if k < 2 else f"{(1 - v / sem) * 100:.1f}%"}
                                   for k, (n, v) in enumerate(linhas)])
                st.dataframe(df, hide_index=True, width="stretch")
                it_b = next((k + 1 for k, v in enumerate(d["B"]["historico"]) if v <= d["B"]["historico"][-1] * 1.01), None)
                it_c = next((k + 1 for k, v in enumerate(d["C"]["historico"]) if v <= d["C"]["historico"][-1] * 1.01), None)
                st.caption(f"Iterações para chegar a 1% do resultado final: reiniciado = {it_b} · reaproveitado = {it_c}. "
                           f"A rota exibida em verde é a melhor das três estratégias do sistema.")
                ordem = [d["idx"][k] for k in rota_nova]
                st.write("**Nova ordem de visita:** " + " → ".join("D" if k == 0 else str(k) for k in ordem))
                df_it = itinerario(G, S.paradas, d["D_novo"], d["caminhos_novos"], rota_nova, idx=d["idx"])
                baixar_csv(df_it, "itinerario_reotimizado.csv", "⬇️ Baixar itinerário reotimizado (CSV)")

# ======================================================================
# Aba 3 — Ponto a ponto
# ======================================================================
with aba3:
    if not pronto:
        st.info("Defina as paradas para comparar os algoritmos de caminho mínimo.")
    else:
        a, b = st.columns(2)
        o = a.selectbox("Origem (parada)", list(range(n_pontos)), format_func=nome_parada)
        t = b.selectbox("Destino (parada)", list(range(n_pontos)), index=n_pontos - 1, format_func=nome_parada)
        if transito_ativo:
            st.caption("🚦 Há um evento de trânsito ativo: os caminhos consideram os pesos alterados.")
        if st.button("Comparar Dijkstra × A*", type="primary"):
            if o == t:
                st.warning("Escolha origem e destino diferentes.")
            else:
                out = {}
                for nome, h in (("Dijkstra", False), ("A*", True)):
                    t0 = time.perf_counter()
                    cam, c, ex = busca(G, S.paradas[o], S.paradas[t], usar_heuristica=h)
                    ms = (time.perf_counter() - t0) * 1000
                    _, _, _, fech = busca(G, S.paradas[o], S.paradas[t], usar_heuristica=h, retornar_fechados=True)
                    out[nome] = (cam, c, ex, ms, fech)
                S.p2p = out
        if S.get("p2p"):
            mostrar = st.radio("Destacar nós expandidos por:", ["A*", "Dijkstra", "Nenhum"], horizontal=True)
            cam = S.p2p["A*"][0]
            camadas = []
            if mostrar != "Nenhum":
                fech = S.p2p[mostrar][4]
                camadas.append(dict(x=[G.nodes[n]["x"] for n in fech], y=[G.nodes[n]["y"] for n in fech], mode="markers",
                                    marker=dict(size=5, color="rgba(237,161,0,0.75)"), name=f"Nós expandidos ({mostrar})",
                                    hoverinfo="skip"))
            camadas.append(dict(x=[G.nodes[n]["x"] for n in cam], y=[G.nodes[n]["y"] for n in cam], mode="lines",
                                line=dict(color="#d1242f", width=4), name="Caminho mínimo"))
            c1, c2 = st.columns([3, 1.2])
            c1.plotly_chart(desenhar_mapa(G, S.paradas, camadas), width="stretch")
            for nome, (cam_, c, ex, ms, _) in S.p2p.items():
                c2.metric(nome, f"{c / 60:.1f} min", help="custo do caminho")
                c2.caption(f"{ex} nós expandidos · {ms:.1f} ms")
            exd, exa = S.p2p["Dijkstra"][2], S.p2p["A*"][2]
            if exd:
                c2.success(f"O A* expandiu **{(1 - exa / exd) * 100:.0f}% menos nós** e encontrou o mesmo custo "
                           f"({'idêntico' if abs(S.p2p['A*'][1] - S.p2p['Dijkstra'][1]) < 1e-6 else 'diferente'}).")
            km = sum(G[cam[k]][cam[k + 1]]["length"] for k in range(len(cam) - 1)) / 1000
            c2.caption(f"Extensão do caminho: {km:.2f} km · {len(cam) - 1} trechos de via")

# ======================================================================
# Aba 4 — Experimentos e validação
# ======================================================================
with aba4:
    sub1, sub2, sub3 = st.tabs(["⚡ Benchmark do cenário atual", "📑 Resultados do TCC (30 execuções)", "✅ Testes de validação"])

    with sub1:
        if not pronto:
            st.info("Defina as paradas para executar o benchmark.")
        else:
            st.write(f"Executa o ACO e o AG várias vezes (sementes diferentes) no cenário atual "
                     f"de **{n_pontos - 1} paradas**, com os parâmetros da barra lateral.")
            execs = st.slider("Número de execuções", 5, 30, 10)
            if st.button("▶ Executar benchmark ACO × AG", type="primary"):
                limpar_transito(G); S.dyn = None
                D, _ = matriz_custos(G, S.paradas)
                ot = held_karp(D) if len(D) <= 11 else None
                barra = st.progress(0.0)
                linhas = []
                for r_ in range(execs):
                    ra = aco(D, n_formigas=formigas, n_iter=iteracoes, alpha=alpha, beta=beta, rho=rho, seed=r_)
                    rg = ag(D, pop=pop, geracoes=ger, pm=pm, seed=r_)
                    linhas += [{"Execução": r_ + 1, "Algoritmo": "ACO", "Custo (min)": ra["custo"] / 60, "Tempo (s)": ra["tempo"]},
                               {"Execução": r_ + 1, "Algoritmo": "AG", "Custo (min)": rg["custo"] / 60, "Tempo (s)": rg["tempo"]}]
                    barra.progress((r_ + 1) / execs, text=f"Execução {r_ + 1}/{execs}")
                barra.empty()
                S.bench = (pd.DataFrame(linhas), ot)
            if S.get("bench"):
                df, ot = S.bench
                ref = ot["custo"] / 60 if ot else df["Custo (min)"].min()
                df["Gap (%)"] = (df["Custo (min)"] / ref - 1) * 100
                resumo = df.groupby("Algoritmo").agg(
                    **{"Custo médio (min)": ("Custo (min)", "mean"), "Desvio-padrão": ("Custo (min)", "std"),
                       "Melhor (min)": ("Custo (min)", "min"), "Gap médio (%)": ("Gap (%)", "mean"),
                       "Acerto da referência": ("Gap (%)", lambda g: f"{(g < 1e-6).mean() * 100:.0f}%"),
                       "Tempo médio (s)": ("Tempo (s)", "mean")}).round(3).reset_index()
                st.dataframe(resumo, hide_index=True, width="stretch")
                st.caption(("Referência: ótimo exato (Held-Karp) = " if ot else "Referência: melhor solução encontrada = ")
                           + f"{ref:.2f} min")
                figb = go.Figure()
                for alg in ("ACO", "AG"):
                    figb.add_trace(go.Box(y=df[df.Algoritmo == alg]["Custo (min)"], name=alg, marker_color=CORES[alg],
                                          boxpoints="all", jitter=0.4))
                figb.update_layout(height=360, yaxis_title="Custo da rota (min)", margin=dict(l=0, r=0, t=10, b=0),
                                   showlegend=False)
                st.plotly_chart(figb, width="stretch")
                baixar_csv(df, "benchmark.csv", "⬇️ Baixar resultados do benchmark (CSV)")

    with sub2:
        pr, pf = os.path.join(PASTA, "resultados"), os.path.join(PASTA, "figuras")
        if not os.path.exists(os.path.join(pr, "e2_estatico.csv")):
            st.info("Rode `python experimentos.py sintetico` e `python graficos.py` para gerar os resultados.")
        else:
            st.caption("Resultados gravados por experimentos.py e apresentados no Capítulo 3 do TCC.")
            e1 = pd.read_csv(os.path.join(pr, "e1_dijkstra_astar.csv"))
            t4 = e1.groupby("algoritmo").agg(**{"Tempo médio (ms)": ("tempo_ms", "mean"),
                                                "Nós expandidos (média)": ("expandidos", "mean"),
                                                "Custo médio (min)": ("custo_s", lambda x: x.mean() / 60)}).round(2)
            st.markdown("**Tabela 4 — Dijkstra × A\\* (100 pares)**"); st.dataframe(t4, width="stretch")
            e2 = pd.read_csv(os.path.join(pr, "e2_estatico.csv"))
            best = e2.groupby("n").custo_s.min()
            e2["ref"] = e2.otimo_s.fillna(e2.n.map(best)); e2["gap"] = (e2.custo_s / e2.ref - 1) * 100
            t5 = e2[e2.algoritmo != "Held-Karp"].groupby(["n", "algoritmo"]).agg(
                **{"Custo médio (min)": ("custo_s", lambda x: x.mean() / 60), "Gap médio (%)": ("gap", "mean"),
                   "Tempo médio (s)": ("tempo_s", "mean")}).round(2).unstack("algoritmo")
            st.markdown("**Tabela 5 — ACO × AG por número de paradas (30 execuções)**"); st.dataframe(t5, width="stretch")
            if os.path.exists(os.path.join(pr, "e4_dinamico.csv")):
                e4 = pd.read_csv(os.path.join(pr, "e4_dinamico.csv"))
                e4["sistema_s"] = e4[["so_caminhos_s", "cold_s", "warm_s"]].min(axis=1)
                nomes = {"previsto_s": "Planejado, antes do evento", "sem_sistema_s": "Rota original sob trânsito",
                         "so_caminhos_s": "Mesma ordem, caminhos A*", "cold_s": "ACO reiniciado",
                         "warm_s": "ACO reaproveitado", "sistema_s": "Sistema (melhor das três)"}
                t6 = pd.DataFrame([{"Estratégia": v, "Tempo restante (min)": round(e4[k].mean() / 60, 2)} for k, v in nomes.items()])
                st.markdown("**Tabela 6 — Cenário dinâmico (30 instâncias)**"); st.dataframe(t6, hide_index=True, width="stretch")
            figs = [("fig_estatico.png", "Figura 9 — Convergência e gap ACO × AG"),
                    ("fig_escalabilidade.png", "Figura 10 — Escalabilidade dos métodos exatos e do ACO"),
                    ("fig_dinamico.png", "Figura 11 — Cenário dinâmico"),
                    ("fig_malha_busca.png", "Figura 6 — Malha viária e nós expandidos")]
            for arq, cap in figs:
                if os.path.exists(os.path.join(pf, arq)):
                    st.image(os.path.join(pf, arq), caption=cap)

    with sub3:
        st.write("Executa a bateria automática de testes (testes.py), que verifica a corretude de cada módulo "
                 "da arquitetura na malha sintética.")
        if st.button("▶ Executar testes de validação", type="primary"):
            import testes
            barra = st.progress(0.0)
            r = testes.executar(callback=lambda k, n: barra.progress(k / n, text=f"Teste {k}/{n}"))
            barra.empty()
            S.testes = r
        if S.get("testes"):
            ok = sum(x[1] for x in S.testes)
            (st.success if ok == len(S.testes) else st.error)(f"{ok}/{len(S.testes)} testes aprovados")
            st.dataframe(pd.DataFrame([{"": "✅" if a else "❌", "Teste": n, "Detalhe": d} for n, a, d in S.testes]),
                         hide_index=True, width="stretch")
