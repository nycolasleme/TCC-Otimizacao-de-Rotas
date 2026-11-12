<div align="center">
  <img src="banner.svg" alt="RotaFormiga Banner Animado" width="100%"/>

  <br/>

  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Streamlit](https://img.shields.io/badge/Streamlit-Interface_Web-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
  [![NetworkX](https://img.shields.io/badge/NetworkX-Grafos_Viários-2E7D32?style=for-the-badge)](https://networkx.org/)
  [![Plotly](https://img.shields.io/badge/Plotly-Visualização_Interativa-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/)
  [![Testes](https://img.shields.io/badge/Validação-12%2F12_Testes_OK-1a7f37?style=for-the-badge)](#-reprodução-dos-experimentos-e-testes)

  <p align="center">
    <strong>Sistema de roteamento e reotimização dinâmica de veículos em malhas urbanas assimétricas utilizando Otimização por Colônia de Formigas (ACO) com reaproveitamento de feromônio.</strong>
  </p>

  [Funcionalidades](#-funcionalidades-principais) •
  [Arquitetura](#-fluxo-da-arquitetura) •
  [Algoritmos](#-metodologia-e-algoritmos) •
  [Instalação](#-instalação-e-execução-rápida) •
  [Experimentos](#-reprodução-dos-experimentos-e-testes)
</div>

---

## ✨ Funcionalidades Principais

| Módulo | O que faz | Destaques |
| :--- | :--- | :--- |
| **🗺️ Malha Viária** | Modela a cidade como um dígrafo ponderado georreferenciado. | Suporta malha **Sintética (Jundiaí-SP)** 100% offline e **OpenStreetMap** real com cache local. |
| **📍 Caminho Mínimo** | Calcula rotas entre interseções e gera a matriz de custos assimétrica. | Comparação visual entre **Dijkstra** e **A\*** com heurística geodésica admissível (Haversine). |
| **🐜 ACO Estático** | Resolve o Problema do Caixeiro Viajante Assimétrico (ATSP). | Trilhas de feromônios no mapa, slider de evolução por iteração, mapa de calor e exportação CSV. |
| **🚦 Trânsito Dinâmico** | Reotimiza a rota com o veículo já em movimento após incidentes. | Atualização seletiva da matriz de custos e *warm start* com reaproveitamento de feromônio. |
| **📊 Validação & TCC** | Compara meta-heurísticas e métodos exatos. | Benchmark **ACO × Algoritmo Genético (AG)**, **Held-Karp** (ótimo exato) e 12 testes automáticos. |

---

## 🔄 Fluxo da Arquitetura

```mermaid
flowchart LR
    A[("🏙️ Malha Viária\n(OSM ou Sintética)")] --> B["📐 Dígrafo Ponderado\n(grafo.py)"]
    B --> C["⚡ Dijkstra / A*\n(caminho_minimo.py)"]
    C --> D["📊 Matriz de Custos D\n(Assimétrica)"]
    D --> E["🐜 Colônia de Formigas\n(aco.py · MAX-MIN)"]
    E --> F{"🚦 Evento de\nTrânsito?"}
    F -- "Não" --> G["✅ Rota Ótima &\nItinerário CSV"]
    F -- "Sim (transito.py)" --> H["🔄 Atualização Seletiva\ndos Pares Afetados"]
    H --> I["♻️ Warm Start ACO\n(dinamico.py)"]
    I --> G
