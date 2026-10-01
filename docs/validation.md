# Estado de validación · 2026-09-10

## Hechos observados

- Se leyó el enunciado mediante pypdf y se consultaron los repositorios y UCI.
- La carpeta del proyecto ChatGPT no era un repositorio Git ni contenía código de aplicación.
- Python incluido con Codex tiene pandas y pytest, pero no scikit-learn ni Streamlit.
- Se solicitó crear un proyecto independiente con rama feat/erronka1-mvp y .venv.
  El comando no devolvió terminación; no se considera confirmada esa creación.

## Bloqueo de ejecución

Después de las lecturas iniciales, los comandos locales dejaron de devolver salida,
incluyendo una comprobación mínima `echo ready`, con distintos shells. No se han
podido confirmar instalación, descarga del CSV, entrenamiento, pruebas, lint o build.
No se afirman métricas ni funcionamiento visual. Los archivos de código se han
enviado mediante la herramienta de edición; falta lectura posterior de verificación.

## Comandos preparados para validación

```powershell
git status --short
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe -m cnc_guard.cli demo
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Antes de instalar, confirmar que se está dentro de cnc-guard y en una rama dedicada.
Los únicos cambios esperados son los archivos de esta primera implementación.
No hay commits ni publicación remota. Los documentos originales no se han editado.
