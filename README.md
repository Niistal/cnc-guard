# CNC Guard · Erronka 1

Primera implementación de una demo local de mantenimiento industrial: descarga de
AI4I (UCI), validación, clasificación supervisada, Isolation Forest, evaluación,
panel Streamlit e historial SQLite. Estado: código preparado; ejecución pendiente
de recuperar el entorno de comandos. No se han obtenido métricas reales todavía.

## Qué demuestra

- Compara Dummy, regresión logística y Random Forest; selecciona por average precision
  en validación y ajusta el umbral por F2 en validación.
- Conserva el orden UDI con particiones 60/20/20. Es orden del fichero, no tiempo físico.
- Excluye identificadores, etiqueta principal y etiquetas de tipos de fallo de las entradas.
- Ajusta el preprocesamiento solo en entrenamiento. No usa SMOTE.
- Isolation Forest detecta lecturas inusuales; una anomalía no equivale a avería.
- Permite editar una lectura y guardar el resultado localmente, con versión del modelo.
- Se abstiene cuando una lectura excede los rangos de entrenamiento.

## Arranque en Windows

Desde esta carpeta, con Python 3.11 o superior disponible:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m cnc_guard.cli demo
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

El panel se abre en http://127.0.0.1:8501. `demo` descarga unos 510 KB de UCI,
entrena en CPU y genera `artifacts/report.json`, `model.joblib` y
`test_predictions.csv`. No requiere claves API ni servicios de pago.
No activar el entorno virtual evita depender de cambios en la política PowerShell.
La instalación usa pip porque este proyecto es Python, sin dependencias Node.
Las dependencias tienen intervalos compatibles; falta congelarlas tras una instalación validada.

Para usar datos ya descargados:

```powershell
.\.venv\Scripts\python.exe -m cnc_guard.cli train --data data/raw/ai4i2020.csv
```

## Verificación

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m build
```

Las pruebas usan una fixture artificial identificada expresamente como tal. Sus
resultados no sustituyen la evaluación de AI4I. El script de entrenamiento requiere
ambas clases en cada partición y falla explícitamente si no se cumple.

## Dataset y límites

[AI4I 2020, UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset),
DOI 10.24432/C5HS5C, CC BY 4.0. La fuente describe 10.000 filas sintéticas, no
mediciones de las 50 máquinas de ARAKAIN. El archivo se descarga sin modificaciones;
su SHA256 y auditoría se registran al ejecutarlo. No se atribuye a UDI una frecuencia
de muestreo. Las temperaturas tienen dependencia en su generación; por eso se evita
mezclar aleatoriamente todas las filas. El split no valida transferencia a otra fábrica.

El objetivo es `Machine failure` de la misma fila. El score no está calibrado;
**no es una probabilidad de fallo futuro**, ni permite RUL o anticipación de 24 h.
CRITICAL es una prioridad de revisión de la demo, no una orden de parada.
El timestamp guardado es el momento de consulta, nunca una fecha del dataset.

## Reutilización de GitHub

`src/cnc_guard/models.py` adapta la selección de modelos de `CNC.model_map` en
[Shengwei-Peng/CNC-Predictive-Maintenance](https://github.com/Shengwei-Peng/CNC-Predictive-Maintenance),
commit `20308e0cc0093882f66d3602d15c2d234b0f311b`. Se conserva su licencia MIT en
`third_party/`. El resto es integración propia; no se ha importado el repositorio completo.
La separación entre datos, entrenamiento, inferencia y panel toma como referencia
la arquitectura de `devwithmohit/predictive-maintenance-manufacturing-system`.
Ver `docs/research.md` para decisiones y diferencias.

## Qué falta para completar la Erronka

Ver `docs/erronka1.md`: el prototipo cubre una base de programación, ML y visualización.
Quedan validación ejecutada, datos de degradación temporal, justificación de anticipación,
evidencias de Big Data, memoria final, planificación de equipo y defensa.
No se presenta la Erronka completa como terminada.
