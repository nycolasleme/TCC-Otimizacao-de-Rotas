"""Módulo de Grafo: modelagem da malha viária como dígrafo ponderado.

Duas fontes de dados:
  - "osm": malha viária real baixada do OpenStreetMap via OSMnx (requer internet);
  - "sintetico": malha urbana georreferenciada gerada com as características de
    uma região central (quarteirões, ruas de mão única, avenidas de mão dupla).
"""
import math
import random
import networkx as nx

CENTRO_JUNDIAI = (-23.1857, -46.8978)


def haversine(lat1, lon1, lat2, lon2):
    """Distância geodésica em metros entre duas coordenadas."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _finalizar(G):
    """Inicializa atributos de trânsito e o peso atual (custo) de cada arco."""
    for u, v, d in G.edges(data=True):
        d["fator"] = 1.0
        d["custo"] = d["travel_time"]
    G.graph["vmax"] = max(d["speed_kph"] for _, _, d in G.edges(data=True)) / 3.6
    return G


def carregar_osm(centro=CENTRO_JUNDIAI, raio=3000):
    """Baixa a malha real via OSMnx e converte MultiDiGraph -> DiGraph (menor tempo)."""
    import urllib.request
    import osmnx as ox
    # teste rápido de conexão: evita longas esperas quando não há internet
    urllib.request.urlopen("https://overpass-api.de/api/status", timeout=8).read(64)
    ox.settings.requests_timeout = 60
    M = ox.graph_from_point(centro, dist=raio, network_type="drive")
    M = ox.routing.add_edge_speeds(M)
    M = ox.routing.add_edge_travel_times(M)
    G = nx.DiGraph()
    for n, d in M.nodes(data=True):
        G.add_node(n, x=d["x"], y=d["y"])
    for u, v, d in M.edges(data=True):
        if u == v:
            continue
        if not G.has_edge(u, v) or d["travel_time"] < G[u][v]["travel_time"]:
            G.add_edge(u, v, length=d["length"], speed_kph=d["speed_kph"],
                       travel_time=d["travel_time"])
    G = G.subgraph(max(nx.strongly_connected_components(G), key=len)).copy()
    G.graph["fonte"] = "OpenStreetMap"
    return _finalizar(G)


def carregar_sintetico(centro=CENTRO_JUNDIAI, linhas=40, colunas=40,
                       quarteirao=110, seed=42):
    """Gera malha urbana georreferenciada.

    - Interseções em grade levemente irregular (ruído de posição);
    - A cada 6 vias: avenida de mão dupla (60 km/h);
    - Demais ruas: mão única alternada (30-40 km/h), algumas de mão dupla;
    - Remoção aleatória de trechos (quarteirões fechados, praças);
    - Mantém-se a maior componente fortemente conexa.
    """
    rnd = random.Random(seed)
    lat0, lon0 = centro
    dlat = quarteirao / 111320.0
    dlon = quarteirao / (111320.0 * math.cos(math.radians(lat0)))
    G = nx.DiGraph()
    for i in range(linhas):
        for j in range(colunas):
            lat = lat0 + (i - linhas / 2) * dlat + rnd.uniform(-0.18, 0.18) * dlat
            lon = lon0 + (j - colunas / 2) * dlon + rnd.uniform(-0.18, 0.18) * dlon
            G.add_node(i * colunas + j, y=lat, x=lon)

    def via(a, b, kph):
        d = haversine(G.nodes[a]["y"], G.nodes[a]["x"], G.nodes[b]["y"], G.nodes[b]["x"])
        d *= rnd.uniform(1.0, 1.12)  # sinuosidade da via
        G.add_edge(a, b, length=d, speed_kph=kph, travel_time=d / (kph / 3.6))

    for i in range(linhas):            # vias horizontais (ruas "leste-oeste")
        avenida = i % 6 == 0
        for j in range(colunas - 1):
            a, b = i * colunas + j, i * colunas + j + 1
            if avenida:
                via(a, b, 60); via(b, a, 60)
            elif rnd.random() < 0.93:
                kph = rnd.choice([30, 40])
                if rnd.random() < 0.2:
                    via(a, b, kph); via(b, a, kph)
                elif i % 2:
                    via(a, b, kph)
                else:
                    via(b, a, kph)
    for j in range(colunas):           # vias verticais (ruas "norte-sul")
        avenida = j % 6 == 0
        for i in range(linhas - 1):
            a, b = i * colunas + j, (i + 1) * colunas + j
            if avenida:
                via(a, b, 60); via(b, a, 60)
            elif rnd.random() < 0.93:
                kph = rnd.choice([30, 40])
                if rnd.random() < 0.2:
                    via(a, b, kph); via(b, a, kph)
                elif j % 2:
                    via(a, b, kph)
                else:
                    via(b, a, kph)
    G = G.subgraph(max(nx.strongly_connected_components(G), key=len)).copy()
    G.graph["fonte"] = "Malha sintética georreferenciada (Jundiaí-SP)"
    return _finalizar(G)


def carregar_osm_com_cache(centro=CENTRO_JUNDIAI, raio=3000, pasta="cache"):
    """Baixa a malha do OpenStreetMap uma única vez e guarda em disco; nas
    execuções seguintes (inclusive sem internet) lê a cópia local."""
    import os, pickle
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, f"osm_{centro[0]:.4f}_{centro[1]:.4f}_{raio}.pkl")
    if os.path.exists(arq):
        with open(arq, "rb") as f:
            G = pickle.load(f)
        limpar = [d for _, _, d in G.edges(data=True)]
        for d in limpar:
            d["fator"] = 1.0; d["custo"] = d["travel_time"]
        return G
    G = carregar_osm(centro, raio)
    with open(arq, "wb") as f:
        pickle.dump(G, f)
    return G


def carregar_grafo(fonte="auto", **kw):
    if fonte in ("osm", "auto"):
        try:
            return carregar_osm_com_cache(**kw)
        except Exception:
            if fonte == "osm":
                raise
    return carregar_sintetico(**kw)


def no_mais_proximo(G, lat, lon):
    return min(G.nodes, key=lambda n: (G.nodes[n]["y"] - lat) ** 2 + (G.nodes[n]["x"] - lon) ** 2)


def estatisticas(G):
    n, m = G.number_of_nodes(), G.number_of_edges()
    mao_unica = sum(1 for u, v in G.edges if not G.has_edge(v, u))
    return {"vertices": n, "arcos": m, "grau_medio_saida": m / n,
            "arcos_mao_unica_%": 100 * mao_unica / m,
            "extensao_km": sum(d["length"] for _, _, d in G.edges(data=True)) / 1000}
