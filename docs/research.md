# Investigación y decisiones · 2026-09-10

Los prompts adjuntos se han interpretado como referencias y propuestas históricas.
La solicitud actual autoriza comenzar a programar y reutilizar código.

## Fuentes verificadas

| Fuente | Hallazgo | Uso concreto |
|---|---|---|
| https://github.com/Shengwei-Peng/CNC-Predictive-Maintenance | MIT; main.py y utils.py; CSV de ejemplo de 425372 bytes listado por GitHub | Adaptación de model_map en models.py con aviso y licencia |
| https://github.com/devwithmohit/predictive-maintenance-manufacturing-system | Arquitectura separa carga, ML, inferencia y dashboard; infraestructura amplia | Referencia arquitectónica; no código copiado ni servicios iniciados |
| https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset | 10000 filas sintéticas, 6 entradas, licencia CC BY 4.0 | Dataset de arranque, descarga implementada |
| https://data.nasa.gov/dataset/milling-wear | Ensayos de fresado y desgaste VB; fuente BEST Lab, Berkeley | Candidato para la siguiente iteración; aún no descargado ni auditado |
| https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/ | Enlace oficial a Milling y atribución a A. Agogino y K. Goebel (2007) | Localización de datos de desgaste real de herramienta |

## Auditoría del código reutilizado

Revisión de `utils.py` en commit `20308e0cc0093882f66d3602d15c2d234b0f311b`:

- `_features_selection` calcula correlaciones antes de separar los datos.
- `_create_rolling_features` genera ventanas solapadas y `_split_data` después
  utiliza `train_test_split` sin `shuffle=False`: riesgo de contaminación temporal.
- El bucle de horizontes reutiliza la instancia tomada de `model_map`.

Se adapta únicamente el registro de modelos. Cada candidato recibe su pipeline
independiente; scaler/encoder se ajustan solo sobre entrenamiento. Se añade baseline
trivial, partición de validación, average precision y umbral F2. No se conservan ventanas
ni selección por correlación global. Estas mejoras no convierten AI4I en telemetría real.

## ADR-001: dataset inicial

| Candidato | Ventaja | Limitación | Decisión |
|---|---|---|---|
| AI4I UCI | Pequeño, etiquetas, licencia clara, descarga sencilla | Sintético; sin horizonte físico defendible | Demo inicial |
| CSV de Shengwei-Peng | Relacionado con CNC y tiene columna temporal según README | Procedencia y significado de Anomaly insuficientemente documentados para predecir averías | No entrenar inicialmente |
| NASA Milling | Fresado y desgaste VB | Requiere inspeccionar señales, ensayos, muestreo y objetivos antes de modelar | Siguiente candidato |

Decisión provisional de ingeniería: comenzar con clasificación contemporánea, con
límites visibles en panel y documentación. Para anticipación: identificar trayectorias,
agrupar por ensayo/herramienta y definir un horizonte antes de entrenar.

## ADR-002: plataforma

Python, scikit-learn, Streamlit y SQLite; entrenamiento offline y consultas locales.
No se necesita infraestructura distribuida para 10000 filas. Esta elección permite
mostrar un recorrido completo y deja interfaces pequeñas para cambiar la ingesta.
Rollback: dejar de ejecutar este proyecto independiente; no modifica ningún original
adjunto ni conecta con CNC. No hay migraciones sobre datos existentes.

## Diccionario de entradas

| Campo | Unidad / significado |
|---|---|
| Type | Categoría L/M/H del producto |
| Air temperature [K] | Temperatura del aire en kelvin |
| Process temperature [K] | Temperatura del proceso en kelvin |
| Rotational speed [rpm] | Revoluciones por minuto |
| Torque [Nm] | Par en newton metro |
| Tool wear [min] | Desgaste expresado por la fuente en minutos de uso |

UDI y Product ID no identifican una flota de CNC. Machine failure y TWF/HDF/PWF/OSF/RNF
son salidas/etiquetas; nunca entradas. No se inventan vibraciones, presiones o machine_id.
