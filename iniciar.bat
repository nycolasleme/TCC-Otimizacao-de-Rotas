@echo off
chcp 65001 >nul
title RotaFormiga - Otimizacao de Rotas com ACO
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
    echo.
    echo [ERRO] Python nao encontrado.
    echo Instale em https://www.python.org/downloads/ e abra este arquivo novamente.
    pause
    exit /b 1
)

if not exist ".deps_ok" (
    echo Instalando as bibliotecas do sistema na primeira execucao. Aguarde alguns minutos...
    %PY% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel instalar as bibliotecas. Verifique a internet e tente novamente.
        pause
        exit /b 1
    )
    echo Instalando o suporte ao OpenStreetMap - opcional...
    %PY% -m pip install --disable-pip-version-check -r requirements-osm.txt >nul 2>nul
    if errorlevel 1 echo [AVISO] OSMnx nao instalado: a malha sintetica funciona normalmente.
    echo ok> ".deps_ok"
)

echo.
echo ============================================================
echo   RotaFormiga iniciado. O navegador vai abrir em instantes.
echo   Endereco: http://localhost:8501
echo   Para encerrar o sistema, feche esta janela.
echo ============================================================
start "" /b cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:8501"
%PY% -m streamlit run app.py
pause
