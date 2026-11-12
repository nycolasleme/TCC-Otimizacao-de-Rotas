#!/bin/sh
cd "$(dirname "$0")"
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
if [ ! -f .deps_ok ]; then
  echo "Instalando as bibliotecas (primeira execucao)..."
  $PY -m pip install -r requirements.txt || { echo "Falha ao instalar as bibliotecas."; exit 1; }
  $PY -m pip install -r requirements-osm.txt >/dev/null 2>&1 || echo "Aviso: OSMnx nao instalado (malha sintetica funciona normalmente)."
  echo ok > .deps_ok
fi
( sleep 5; (xdg-open http://localhost:8501 || open http://localhost:8501) >/dev/null 2>&1 ) &
echo "RotaFormiga em http://localhost:8501  (Ctrl+C para encerrar)"
$PY -m streamlit run app.py
