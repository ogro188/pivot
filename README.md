# PIVOT — Sistema de Trading Algorítmico Multi-Timeframe

> **Nota para cualquier agente de IA que trabaje en este repo:** este documento está escrito para que entiendas la arquitectura, los contratos y las reglas del proyecto sin tener que inferirlos leyendo todo el código de cero. Las secciones "Estado Verificado" y "Reglas No Negociables" son las más importantes — léelas antes de tocar código.

---

## Qué es esto

PIVOT detecta patrones de estructura de mercado (barridos de liquidez, order blocks, fair value gaps, market structure shifts) por confluencia de múltiples detectores en múltiples timeframes (M15/H1/H4/D1), y genera señales de trading — **nunca ejecuta órdenes, solo alerta**. Tiene un motor de backtest propio, una API FastAPI + WebSocket, y un frontend React de terminal de trading.

Es la evolución standalone de un sistema anterior en MQL5 (MetaTrader). El operador (Martín) tiene 20 años de experiencia trading y diseñó la lógica de detección; el código se construye con asistencia de agentes de IA.

---

## Mapa de Arquitectura

```
activos/*.json       → Configuración por instrumento (símbolo, punto, sesiones)
core/                → Detectores D0-D5 (heredados de PivotRadar v8, MQL5→Python)
                         d0_estructura.py, d1_ruptura.py, d2_sweep.py, d2_anticipacion.py,
                         d3_fvg.py, d4_orderblock.py, d5_mss_sweep.py,
                         motor_v8.py, scoring.py, hipotesis.py, alertas.py, estructuras.py, base.py, utils.py
kernel/
  contrato.py         → Contratos base: Estrategia, Contexto, Señal, ActivoInfo (ver abajo)
  core_adapter.py     → Traduce Contexto del kernel ↔ Contexto del core (para reusar D0-D5)
  activos_loader.py   → Carga activos/*.json → ActivoInfo
  backtest.py         → BacktestEngine: simulación vela por vela, sin look-ahead (ver reglas)
  storage.py          → Persistencia SQLite (operaciones, dataset ML, config)
  runtime.py          → Orquestación de ejecución en vivo
  feeds/               → CSVFeed (backtest), csv_resample.py (deriva H1/H4/D1 desde M15),
                           deriv.py (feed en vivo vía Deriv API)
  api/app.py          → Endpoints FastAPI (/api/backtest, /api/assets, /api/strategies, ...)
estrategias/
  registro.py         → Registro dinámico de estrategias (patrón plugin)
  pivot/               → Estrategia PIVOT (la principal — confluencia D0-D5 + WilsonScorer)
  ema_cross/, dummy/   → Estrategias de referencia/testing, mucho más simples
data/                 → CSVs históricos (EURUSD M15/H1/H4/D1, XAUUSD M15)
frontend/             → React + TS + Vite + Tailwind + Zustand + FastAPI/WebSocket client
tests/unit/, tests/integration/ → pytest
scripts/              → Utilidades (export_ml_dataset.py, run_deriv_ws.py)
docs/                 → Documentación de fases — ver advertencia abajo
```

---

## El Contrato Central (`kernel/contrato.py`)

Toda estrategia nueva implementa la clase abstracta `Estrategia`:

```python
class Estrategia(ABC):
    nombre: str
    version: str
    timeframes: List[str]      # qué timeframes necesita del Contexto
    eventos: List[str]

    def setup(self, params: dict, activo: ActivoInfo) -> None: ...
    def detectar(self, contexto: Contexto) -> List[Señal]: ...
```

`Contexto` trae `df_m15`, `df_h1`, `df_h4`, `df_d1` (DataFrames OHLC recortados al momento actual), `precio`, `tiempo`, `activo`. `Señal` trae dirección, precio, SL/TP, confianza, y los detectores que la generaron.

Esto es lo que hace que el sistema sea extensible: agregar una estrategia nueva es implementar esta interfaz y registrarla en `estrategias/registro.py`, sin tocar el motor de backtest ni la API.

---

## Detectores D0-D5 (Core)

| Detector | Archivo | Qué Detecta | Filtros Clave (ahora informacionales) |
|----------|---------|-------------|----------------------------------------|
| **D0** | `d0_estructura.py` | Estructura H1 (swings, sweeps, zonas) | Base para todos los demás |
| **D1** | `d1_ruptura.py` | Ruptura de rango (n velas) | `penetracion_atr ≥ 0.5`, `body_ratio ≥ 0.4`, `volumen ≥ 1.2x`, `retest` |
| **D2** | `d2_sweep.py` | Sweep de liquidez + reclaim | `wick_ratio ≥ 0.55`, `sweep_reciente ≤ 2`, `distancia ≤ 2×ATR`, `reclaim_body ≥ 0.55` |
| **D2_A** | `d2_anticipacion.py` | Sweep anticipado + confluencias | `wick_ratio ≥ 0.33`, confluencias FVG/OB/MSS (≥2) |
| **D3/D3_DEF** | `d3_fvg.py` | Fair Value Gap (defendido/normal) | `fvg_size_atr ≥ 0.20`, `body_ratio ≥ 0.55`, `dir_ok`, MSS alineado |
| **D4** | `d4_orderblock.py` | Order Block + confluencia | `ob_body ≥ 0.40`, `impulse ≥ 0.70×ATR`, `no_tested`, `entering`, `distancia ≤ 2×ATR` |
| **D5** | `d5_mss_sweep.py` | MSS H4 + sweep M15 | `mss_aligned`, `mss_reciente ≤ 12`, `wick_ratio ≥ 0.55`, `sweep_reciente ≤ 2`, `distancia ≤ 2×ATR`, `reclaim ≥ 0.55` |

### Cambio Crítico (v8.1): Filtros Informacionales
**Todos los detectores ahora retornan `Signal` SIEMPRE (nunca `None` por filtros).** Los filtros duros anteriores ahora son **informacionales**:

- `signal.filtros_pasados: List[str]` — filtros que superaron el umbral
- `signal.filtros_fallados: List[str]` — filtros que NO superaron el umbral
- Campos numéricos dedicados: `filtro_penetracion_atr`, `filtro_wick_ratio`, `filtro_fvg_size_atr`, `filtro_ob_impulse`, `filtro_mss_reciente`, etc.
- `signal.direction = 0` indica "sin patrón válido" (el motor lo descarta antes de scoring)

**Beneficio:** Análisis post-hoc completo — "¿por qué esta señal tipo C falló el filtro de reclaim?" — sin perder la señal para ML/analytics.

---

## Filosofía de Diseño — "Radar Puro" (Regla de Producto, No Técnica)

Los detectores D0-D5 son los **únicos filtros de entrada**. Sesión, spread, ATR y volumen son **metadata que ajusta confianza, nunca gates duros** que bloquean una señal.

Si vas a tocar `estrategias/pivot/__init__.py`, **no agregues** un `if condicion_de_contexto: return []` para filtros que no sean detectores D0-D5 — eso rompe el principio de diseño explícitamente establecido. Penalizar confianza sí, bloquear no.

---

## Estado Verificado (Última Auditoría — No Confiar en `docs/FASE*_COMPLETADA.md` Sin Re-verificar)

⚠️ **Este repo tuvo, en más de una ronda de desarrollo, documentos de progreso con cifras de impacto inventadas** (ej. un doc afirmó "911 registros en dataset ML" cuando la tabla real tenía 0 filas). Los peores casos ya se eliminaron, pero la regla para cualquier doc de estado nuevo es: **ningún número entra sin el comando exacto que lo produjo, corrido en esa sesión.**

| Componente | Estado |
|---|---|
| `BacktestEngine` conectado a `/api/backtest` | ✅ Verificado — ya no es mock |
| Resampling H1/H4/D1 sin look-ahead masivo | ✅ Verificado — precalculado una vez, recortado por timestamp por vela |
| Look-ahead en el borde exacto de cada hora/4h/día | ⚠️ **Bug conocido, sin arreglar.** `_slice_tf()` en `kernel/backtest.py` usa `searchsorted(..., side="right")`, lo que incluye la vela H1/H4/D1 que recién está abriendo en el instante exacto del cambio de hora. Confirmado con test sobre 17.520 velas reales: ~32% de las barras tienen al menos una violación. Fix: cambiar a `side="left"` o filtro estricto `< tiempo_actual`. |
| WilsonScorer conectado a la estrategia real | ✅ Verificado (`estrategias/pivot/__init__.py:219-220`) |
| Persistencia de resultados en dataset ML | ✅ Verificado (`kernel/backtest.py:571`, llama a `db.guardar_resultado_operacion`) |
| `id_señal` sin colisión (hash de detectores+dirección) | ✅ Verificado |
| CI corre tests de integración pero no falla el build si fallan | ⚠️ **`.github/workflows/ci-cd.yml` línea 93 tiene `pytest tests/integration ... \|\| true`.** Un badge de CI en verde NO garantiza que los tests de integración pasen. |
| `test_pivot_backtest.py` en la raíz (no en `tests/`) | Corre en CI como script standalone (línea 97 del workflow), no vía pytest. Funciona pero es inconsistente. |
| Archivos sueltos en la raíz sin organizar | `especificacion_pivotradar_v8_sin_restricciones.md` → debería ir a `docs/`. `test_ml_export.csv` → fixture de test, una sola fila. |

---

## Reglas No Negociables

1. **Cero Look-ahead.** Cualquier dato que el `Contexto` le pase a una estrategia en el momento `t` no puede contener información de después de `t`. Test de referencia: recorrer todas las velas del backtest y comparar `df_h1.index.max() < tiempo_actual` (estrictamente menor, no `<=`).

2. **Ningún Test Se Considera Válido Sin Assert Sobre el Resultado.** Un test que solo verifica "no tira excepción" no prueba nada. Todo test de detección necesita un assert explícito sobre lo que se esperaba.

3. **Ningún Doc de Estado Lleva Cifra Sin Comando Que La Produjo.** Si no se corrió, el doc dice "no verificado", no un número inventado.

4. **No Agregar Gates Duros de Sesión/Spread/Volumen a la Estrategia PIVOT** — ver "radar puro" arriba.

5. **`except: pass` Silencioso Prohibido en el Camino Crítico** (generación de señal → persistencia de resultado). Si algo puede fallar ahí, tiene que verse — como excepción o como log explícito, nunca en silencio.

---

## Cómo Correr Esto

### Backend
```bash
pip install -r requirements.txt --break-system-packages
pip install "httpx<0.28" pytest pytest-cov --break-system-packages  # httpx>=0.28 rompe TestClient con starlette 0.36

pytest tests/unit -v                      # rápido, ~15s
pytest tests/integration -v               # más lento, incluye backtests reales sobre datos de 6 meses

# Backtest manual sobre EURUSD
python test_pivot_backtest.py
```

### API Server (FastAPI + WebSocket)
```bash
python -m cli
# → Swagger UI: http://localhost:8000/docs
# → WebSocket: ws://localhost:8000/ws/signals
# → API Assets: http://localhost:8000/api/assets
```

### Frontend
```bash
cd frontend && npm install && npm run dev   # dev server
cd frontend && npm run build                # build de producción
```

### Exportar Dataset ML
```bash
python scripts/export_ml_dataset.py --symbol EURUSD --output ml_dataset.parquet
```

---

## Símbolos y Estrategias Disponibles

- **Activos configurados:** EURUSD, XAUUSD (`activos/*.json`)
- **Estrategias registradas:**
  - `PIVOT` — la principal, confluencia D0-D5, ~30 parámetros configurables
  - `ema_cross` y `dummy` — referencia/testing, no para uso real

---

## Pipeline ML-Ready (Para Escalado con IA)

El sistema ya genera un dataset estructurado por operación:

```python
# Cada operación guardada tiene:
{
    "timestamp_entrada": "...",
    "timestamp_salida": "...",
    "simbolo": "EURUSD",
    "direccion": 1,
    "detectores_activos": ["D2", "D3_DEF"],      # para feature engineering
    "pnl_puntos": 12.5,
    "razon_salida": "TP",
    "fue_ganadora": true,
    # + 100+ features implícitas en la señal original
}
```

**Próximo paso natural:**
1. `scripts/export_ml_dataset.py` → Parquet con 50+ features
2. XGBoost/LightGBM + Optuna (walk-forward purged CV)
3. Reemplazar scoring fijo → modelo calibrado (Platt/Isotonic)
4. SHAP feature importance → podar detectores/umbrales inútiles

---

## Frontend — Identidad Visual (PV-Terminal)

El frontend sigue el sistema de diseño documentado en `SPEC_PV_TERMINAL.md` (paleta, tipografía IBM Plex, componentes `NavBar.tsx`/`DetectorReadout.tsx`). Regla dura: `signal-long`/`signal-short` (verde/rojo) se usan **exclusivamente** para dirección de mercado real, nunca como color decorativo de UI genérica.

---

## Créditos y Licencia

Diseño de detección: Martín (20 años exp. trading)  
Implementación Python + arquitectura: Agentes de IA + Martín  
Licencia: Propietario — no redistribuir sin autorización.