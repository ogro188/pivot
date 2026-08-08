# PIVOT — Sistema de trading algorítmico multi-timeframe

> **Nota para cualquier agente de IA que trabaje en este repo:** este documento está escrito para que entiendas la arquitectura, los contratos y las reglas del proyecto sin tener que inferirlos leyendo todo el código de cero. Las secciones "Estado verificado" y "Reglas no negociables" son las más importantes — léelas antes de tocar código.

## Qué es esto

PIVOT detecta patrones de estructura de mercado (barridos de liquidez, order blocks, fair value gaps, market structure shifts) por confluencia de múltiples detectores en múltiples timeframes (M15/H1/H4/D1), y genera señales de trading — **nunca ejecuta órdenes, solo alerta**. Tiene un motor de backtest propio, una API FastAPI + WebSocket, y un frontend React de terminal de trading.

Es la evolución standalone de un sistema anterior en MQL5 (MetaTrader). El operador (Martín) tiene 20 años de experiencia trading y diseñó la lógica de detección; el código se construye con asistencia de agentes de IA.

## Mapa de arquitectura

```
activos/*.json       → Configuración por instrumento (símbolo, punto, sesiones)
core/                → Detectores D0-D5 (heredados de PivotRadar v8, MQL5→Python)
                        d0_estructura.py, d1_ruptura.py, d2_sweep.py, d3_fvg.py,
                        d4_orderblock.py, d5_mss_sweep.py, motor_v8.py, scoring.py
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
data/                 → CSVs históricos (EURUSD M15/H1/H4/D1)
frontend/             → React + TS + Vite + Tailwind + Zustand + FastAPI/WebSocket client
tests/unit/, tests/integration/ → pytest
scripts/              → Utilidades (export_ml_dataset.py, run_deriv_ws.py)
docs/                 → Documentación de fases — ver advertencia abajo
```

## El contrato central (`kernel/contrato.py`)

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

## Filosofía de diseño — "radar puro" (regla de producto, no técnica)

Los detectores D0-D5 son los **únicos filtros de entrada**. Sesión, spread, ATR y volumen son **metadata que ajusta confianza, nunca gates duros** que bloquean una señal. Si vas a tocar `estrategias/pivot/__init__.py`, no agregues un `if condicion_de_contexto: return []` para filtros que no sean detectores D0-D5 — eso rompe el principio de diseño explícitamente establecido para este sistema. Penalizar confianza sí, bloquear no.

## Estado verificado (última auditoría — no confiar en `docs/FASE*_COMPLETADA.md` sin re-verificar)

⚠️ **Este repo tuvo, en más de una ronda de desarrollo, documentos de progreso con cifras de impacto inventadas** (ej. un doc afirmó "911 registros en dataset ML" cuando la tabla real tenía 0 filas). Los peores casos ya se eliminaron, pero la regla para cualquier doc de estado nuevo es: **ningún número entra sin el comando exacto que lo produjo, corrido en esa sesión.** Si vas a citar `docs/FASE*_COMPLETADA.md` como fuente de verdad, primero corré vos el test o comando que dice haber corrido — no asumas que el número es correcto.

Estado real confirmado por auditoría directa (no por los docs):

| Componente | Estado |
|---|---|
| `BacktestEngine` conectado a `/api/backtest` | ✅ Verificado — ya no es mock |
| Resampling H1/H4/D1 sin look-ahead masivo | ✅ Verificado — precalculado una vez, recortado por timestamp por vela |
| Look-ahead en el borde exacto de cada hora/4h/día | ⚠️ **Bug conocido, sin arreglar.** `_slice_tf()` en `kernel/backtest.py` usa `searchsorted(..., side="right")`, lo que incluye la vela H1/H4/D1 que recién está abriendo (no cerrada) en el instante exacto del cambio de hora. Confirmado con test sobre 17.520 velas reales: ~32% de las barras tienen al menos una violación. Fix: cambiar a `side="left"` o filtro estricto `< tiempo_actual`. |
| WilsonScorer conectado a la estrategia real | ✅ Verificado (`estrategias/pivot/__init__.py:219-220`) |
| Persistencia de resultados en dataset ML | ✅ Verificado (`kernel/backtest.py:571`, llama a `db.guardar_resultado_operacion`) |
| `id_señal` sin colisión (hash de detectores+dirección) | ✅ Verificado |
| CI corre tests de integración pero no falla el build si fallan | ⚠️ **`.github/workflows/ci-cd.yml` línea 93 tiene `pytest tests/integration ... \|\| true`.** Un badge de CI en verde NO garantiza que los tests de integración pasen. Corregir sacando el `|| true` es trivial pero no está hecho. |
| `test_pivot_backtest.py` en la raíz (no en `tests/`) | Corre en CI como script standalone (línea 97 del workflow), no vía pytest. Funciona pero es inconsistente con el resto de la suite. |
| Archivos sueltos en la raíz sin organizar | `especificacion_pivotradar_v8_sin_restricciones.md` → debería ir a `docs/`. `test_ml_export.csv` → debería ir a `data/` o un fixture de test, y contiene una sola fila de prueba, no un dataset real. |

## Reglas no negociables para trabajar en este repo

1. **Cero look-ahead.** Cualquier dato que el `Contexto` le pase a una estrategia en el momento `t` no puede contener información de después de `t`. Esto ya causó dos bugs reales en este proyecto (uno masivo, ya resuelto; uno de borde, todavía activo — ver tabla arriba). Si tocás `_crear_contexto` o el resampling, el test de referencia es recorrer todas las velas del backtest y comparar `df_h1.index.max() < tiempo_actual` (estrictamente menor, no `<=`).
2. **Ningún test se considera válido sin assert sobre el resultado.** Un test que solo verifica "no tira excepción" no prueba nada — este repo tuvo tests así y pasaban aunque el detector no detectara nada. Todo test de detección necesita un assert explícito sobre lo que se esperaba.
3. **Ningún doc de estado/progreso lleva una cifra sin el comando que la produjo al lado**, corrido en la misma sesión en que se escribe el doc. Si no se corrió, el doc dice "no verificado", no un número inventado.
4. **No agregar gates duros de sesión/spread/volumen a la estrategia PIVOT** — ver "radar puro" arriba.
5. **`except: pass` silencioso está prohibido en el camino crítico** (generación de señal → persistencia de resultado). Si algo puede fallar ahí, tiene que verse — como excepción o como log explícito, nunca en silencio.

## Cómo correr esto

```bash
# Backend
pip install -r requirements.txt --break-system-packages
pip install "httpx<0.28" pytest pytest-cov --break-system-packages  # httpx>=0.28 rompe TestClient con starlette 0.36

pytest tests/unit -v                      # rápido, ~15s
pytest tests/integration -v               # más lento, incluye backtests reales sobre datos de 6 meses

# Backtest manual sobre EURUSD
python test_pivot_backtest.py

# Frontend
cd frontend && npm install && npm run dev   # dev server
cd frontend && npm run build                # build de producción, valida que Tailwind/TS compilen
```

## Frontend — identidad visual (PV-Terminal)

El frontend sigue el sistema de diseño documentado en `SPEC_PV_TERMINAL.md` (incluido en este repo: paleta, tipografía IBM Plex, y componentes de referencia `NavBar.tsx`/`DetectorReadout.tsx`). Regla dura: `signal-long`/`signal-short` (verde/rojo) se usan **exclusivamente** para dirección de mercado real, nunca como color decorativo de UI genérica.

## Símbolos y estrategias disponibles hoy

- **Activos configurados:** EURUSD, XAUUSD (`activos/*.json`)
- **Estrategias registradas:** `PIVOT` (la principal, confluencia D0-D5, ~30 parámetros configurables), `ema_cross` y `dummy` (referencia/testing, no para uso real)
