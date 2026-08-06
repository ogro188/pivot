# RADAR v2.0

Sistema de ejecución y backtesting de estrategias de trading.

## Quick Start

```bash
pip install -r requirements.txt
python cli.py
```

Frontend:
```bash
cd frontend && npm install && npm run dev
```

## Documentación

Ver `docs/MANUAL.md` para instrucciones completas.

## Estructura

- `kernel/` — Motor core (feeds, indicadores, runtime, backtest, API)
- `estrategias/` — Plugins de estrategias (dummy, ema_cross, pivot*)
- `frontend/` — React SPA
- `activos/` — Configuración por activo

*El port de la estrategia Pivot se construye por aparte.
