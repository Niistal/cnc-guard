# Erronka 1: cobertura y siguientes entregas

Fuente académica: `1Erronka_ikaslearen_txostena.docx.pdf`, Uni Eibar-Ermua, CC-BY.
El enunciado plantea 50 CNC en Bilbao, 1200 EUR/h de parada, 11 semanas y equipos
de 3-4 personas. El desarrollo se evalúa mediante propuesta (25%), presentación
final (25%) y controles (50%). Este código es un primer incremento, no la entrega completa.

| Área | Evidencia preparada | Estado |
|---|---|---|
| IA y negocio | Problema y límites, research.md | Base documentada |
| ML supervisado | Dos candidatos, baseline, split, métricas, umbral | Implementado; ejecución pendiente |
| ML no supervisado | Isolation Forest sin etiquetas en fit | Implementado; ejecución pendiente |
| Programación IA | Módulos y pruebas de contrato/leakage/integración | Implementado; pruebas pendientes |
| Ingesta y almacenamiento | CSV oficial, SHA256, SQLite parametrizado | Implementado; verificación pendiente |
| Dashboard / BI | Panel y exportación de evaluación | Implementado; prueba visual pendiente |
| Big Data | Decisión de MVP local | Pendiente diseño y evidencia de escala |
| Anticipación de averías | AI4I solo etiqueta de la misma fila | Pendiente dataset temporal y formulación |
| Seguridad / privacidad | Localhost, sin control OT, abstención y threat model | Base documentada |
| Equipo y comunicación | El enunciado exige contrato y roles | Pendiente asignación por el equipo |
| Presentación y controles | Esta matriz permite preparar el primer control | Pendiente validación y defensa |

## Próximo trabajo en orden

1. Recuperar ejecución local, instalar dependencias en .venv, correr tests/lint/build.
2. Descargar AI4I, revisar auditoría y entrenar. Guardar report.json como evidencia real.
3. Probar el panel y verificar persistencia y abstención con entradas inválidas.
4. Auditar NASA Milling: señales, etiquetas VB, grupos y trayectoria por herramienta.
5. Formular predicción anticipada o regresión de desgaste según datos observados;
   reservar ensayos completos para test. No reciclar métricas de AI4I como resultados CNC.
6. Con el equipo, cerrar propuesta, calendario, roles y memoria del primer control.
7. Añadir evidencia de BI/Big Data justificada, análisis de impacto con supuestos
   explícitos y guion de presentación. No inventar horas de parada evitadas o ahorro.

## Amenazas y límites del prototipo

- Datos inválidos o fuera de rango: validación y abstención; dentro de rango aún puede
  haber manipulación o cambio de distribución que el modelo no detecte.
- Artefactos manipulados: joblib puede ejecutar código; solo cargar el modelo generado
  localmente por este proyecto, nunca artefactos descargados. Falta firma de artefactos.
- Acceso al panel: usar 127.0.0.1; no hay autenticación para exposición en red.
- Confusión de demo con producción: banner y campos sin horizonte/RUL; sin conexiones OT.
- Datos personales: la aplicación no necesita nombres del equipo ni información personal.

Rollback operativo: detener Streamlit y volver a los CSV originales; todos los resultados
se guardan bajo artifacts/. No se han diseñado acciones que modifiquen una máquina.
