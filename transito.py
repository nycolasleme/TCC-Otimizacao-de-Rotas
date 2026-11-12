"""Simulador de Trânsito Dinâmico: altera o peso w(u,v) dos arcos de uma região."""
from grafo import haversine

EVENTOS = {
    "Horário de pico": 1.8,
    "Lentidão": 3.0,
    "Acidente": 5.0,
    "Interdição parcial": 10.0,
}


def aplicar_evento(G, centro_no, raio_m, fator):
    """Multiplica o tempo de travessia dos arcos cuja origem está dentro do raio.
    Retorna o conjunto de arcos afetados."""
    lat0, lon0 = G.nodes[centro_no]["y"], G.nodes[centro_no]["x"]
    afetados = set()
    for u, v, d in G.edges(data=True):
        if haversine(lat0, lon0, G.nodes[u]["y"], G.nodes[u]["x"]) <= raio_m:
            d["fator"] = max(d["fator"], fator)
            d["custo"] = d["travel_time"] * d["fator"]
            afetados.add((u, v))
    return afetados


def limpar_transito(G):
    for _, _, d in G.edges(data=True):
        d["fator"] = 1.0
        d["custo"] = d["travel_time"]


def pares_afetados(caminhos, afetados):
    """Pares (i,j) da matriz cujo caminho mínimo usa ao menos um arco afetado.
    Como o evento apenas AUMENTA pesos, os demais pares continuam ótimos."""
    pares = set()
    for (i, j), cam in caminhos.items():
        if any((cam[k], cam[k + 1]) in afetados for k in range(len(cam) - 1)):
            pares.add((i, j))
    return pares
