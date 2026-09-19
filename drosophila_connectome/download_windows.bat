@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul

set "ROOT=%~dp0"
set "OUT=%ROOT%data"
set "PY=python"

echo ==================================================
echo   Drosophila connectome downloader (MaleCNS)
echo ==================================================
echo   Out dir: %OUT%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python not found in PATH
  goto :end
)

set "SCRIPT=%ROOT%scripts\fetch_connectome.py"
if not exist "%SCRIPT%" (
  echo [ERROR] missing %SCRIPT%
  goto :end
)

echo [1/5] MaleCNS cell annotations (small) ...
%PY% "%SCRIPT%" flyem-male-cns "v1.0/connectome-data/annotations/" "%OUT%\male_cns\annotations" --ext csv,json,tsv,parquet
if errorlevel 1 echo [WARN] annotations failed - bucket path may have changed

echo.
echo [2/5] MaleCNS flat-connectome (larger) ...
%PY% "%SCRIPT%" flyem-male-cns "v1.0/connectome-data/flat-connectome/" "%OUT%\male_cns\connectivity" --ext csv,json,tsv,parquet
if errorlevel 1 echo [WARN] connectivity failed - bucket path may have changed

echo.
echo [3/5] papers and docs ...
if not exist "%OUT%\papers" mkdir "%OUT%\papers"
curl -sSL --max-time 120 -o "%OUT%\papers\google-research-blog.html" "https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/"
curl -sSL --max-time 120 -o "%OUT%\papers\male-cns-download-page.html" "https://male-cns.janelia.org/download/"

echo.
echo [4/5] demo repos ...
if not exist "%OUT%\demos" mkdir "%OUT%\demos"
git clone --depth 1 https://github.com/evnsnclr/neurocraft-fly-public "%OUT%\demos\neurocraft-fly-public"
git clone --depth 1 https://github.com/MarkUnthank/flyhard "%OUT%\demos\flyhard"

echo.
echo [5/5] FlyWire probe (dry run, list only) ...
echo   NOTE: FlyWire connectivity is best pulled via neuPrint API. See README.
%PY% "%SCRIPT%" flywire "flywire_www/" "%OUT%\flywire" --ext csv,json --dry

:end
echo.
echo Done. Artifacts in %OUT%
pause
