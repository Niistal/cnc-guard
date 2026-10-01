"""Panel local CNC Guard. Ejecutar: streamlit run app.py --server.address 127.0.0.1"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from cnc_guard.data import NUMERIC
from cnc_guard.inference import history, load_model, predict, save_prediction
from cnc_guard.registry import Registry

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
try:
    _, MODEL_DIR = Registry(ARTIFACTS).resolve("ai4i")
except FileNotFoundError:
    MODEL_DIR = ARTIFACTS
st.set_page_config(page_title="CNC Guard · Erronka 1", page_icon="⚙️", layout="wide")
st.title("CNC Guard")
st.caption("Erronka 1 · Mantenimiento industrial · Prototipo académico")
st.warning("AI4I es un dataset sintético. Clasificamos la condición de una lectura; "
           "no predecimos cuándo fallará una CNC real. Sin conexión a maquinaria.")
if not (MODEL_DIR / "report.json").exists() or not (MODEL_DIR / "model.joblib").exists():
    st.info("Primero ejecuta: cnc-guard demo")
    st.stop()


@st.cache_resource
def get_model(modified: int):
    return load_model(MODEL_DIR / "model.joblib")


bundle = get_model((MODEL_DIR / "model.joblib").stat().st_mtime_ns)
report = json.loads((MODEL_DIR / "report.json").read_text(encoding="utf-8"))
demo_tab, metrics_tab, history_tab = st.tabs(["Probar una lectura", "Evaluación", "Historial"])
with demo_tab:
    st.subheader("Lectura de ejemplo editable")
    with st.form("reading"):
        kind = st.selectbox("Tipo de producto", ["L", "M", "H"])
        defaults = [298.1, 308.6, 1551.0, 42.8, 0.0]
        values = [st.number_input(name, min_value=0.0, value=default)
                  for name, default in zip(NUMERIC, defaults)]
        submitted = st.form_submit_button("Analizar y guardar lectura", type="primary")
    if submitted:
        reading = {"Type": kind, **dict(zip(NUMERIC, values))}
        try:
            result = predict(bundle, reading)
            save_prediction(ARTIFACTS / "history.sqlite3", reading, result)
            st.session_state["result"] = result
        except ValueError as error:
            st.error(str(error))
    if "result" in st.session_state:
        result = st.session_state["result"]
        st.subheader(result["status"])
        st.write(result["explanation"])
        st.info(result["recommended_action"])
        st.json(result)
with metrics_tab:
    st.write(f"Modelo seleccionado en validación: **{report['selected_model']}**")
    columns = st.columns(3)
    for column, label, key in zip(columns, ["Average precision", "Precisión", "Recall"],
                                   ["average_precision", "precision", "recall"]):
        column.metric(label + " · test", f"{report['test'][key]:.3f}")
    st.caption(report["split"])
    st.dataframe(pd.DataFrame(report["partitions"]).T)
    st.subheader("Matriz de confusión · test")
    tn, fp, fn, tp = report["test"]["confusion_matrix_tn_fp_fn_tp"]
    st.table(pd.DataFrame([[tn, fp], [fn, tp]], index=["Real normal", "Real fallo"],
                         columns=["Predicho normal", "Predicho fallo"]))
    st.subheader("Importancia global · no implica causalidad")
    st.bar_chart(pd.Series(report["global_importance"]).sort_values())
    st.download_button("Descargar evaluación JSON", json.dumps(report, indent=2),
                       file_name="cnc_guard_evaluation.json")
with history_tab:
    st.caption("Historial de pruebas del panel, no telemetría real de 50 máquinas.")
    st.dataframe(history(ARTIFACTS / "history.sqlite3"))
