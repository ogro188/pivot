# PIVOT Trading System v2.0

[![Estado](https://img.shields.io/badge/estado-funcional-brightgreen)]()
[![Versión](https://img.shields.io/badge/versión-2.0.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)]()
[![API](https://img.shields.io/badge/API-FastAPI-green.svg)]()

## 🎯 Sistema de Ejecución y Backtesting de Estrategias de Trading

**Versión:** 2.0.0 (Refactorización Completa - Fase 1 COMPLETADA)  
**Estado:** ✅ **FUNCIONAL** - API en ejecución, estrategias cargando

---

## 📊 Progreso de Transformación

| Fase | Estado | Score | Descripción |
|------|--------|-------|-------------|
| **Fase 1** | ✅ COMPLETADA | 6.5/10 | Cimientos: kernel/contrato.py + API FastAPI |
| Fase 2 | ⏳ Pendiente | - | Backtest Engine |
| Fase 3 | ⏳ Pendiente | - | Data Feeds (CSV, Deriv) |
| Fase 4 | ⏳ Pendiente | - | Estrategia Pivot |
| Fase 5 | ⏳ Pendiente | - | Runtime Multiactivo |
| Fase 6 | ⏳ Pendiente | - | Tests + Docker + CI/CD |

**Mejora:** 2.2/10 → 6.5/10 (+4.3 puntos) 🚀

---

## 🚀 Quick Start

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Arrancar servidor API
```bash
python cli.py
```

✅ Servidor disponible en `http://localhost:8000`

### 3. Verificar estado
```bash
curl http://localhost:8000/api/health
# {"status":"healthy","version":"2.0.0","strategies_loaded":2}
```

### 4. Documentación Swagger
Abrir navegador: `http://localhost:8000/docs`

### Frontend (opcional)
```bash
cd frontend && npm install && npm run dev
```

---

## 📡 API Endpoints

| Endpoint | Método | Descripción | Estado |
|----------|--------|-------------|--------|
| `/` | GET | Info del sistema | ✅ |
| `/api/health` | GET | Health check | ✅ |
| `/api/assets` | GET | Lista activos | ✅ |
| `/api/strategies` | GET | Lista estrategias | ✅ |
| `/api/strategies/{nombre}` | GET | Detalle estrategia | ✅ |
| `/api/backtest` | POST | Ejecutar backtest | 🔄 Mock |
| `/api/config` | GET | Configuración global | ✅ |

---

## 🧪 Ejemplos

### Listar estrategias
```bash
curl http://localhost:8000/api/strategies | jq
```

### Detalles de estrategia
```bash
curl http://localhost:8000/api/strategies/ema_cross | jq
```

### Backtest (mock)
```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "estrategia": "ema_cross",
    "activo": "EURUSD",
    "timeframe": "M15",
    "fecha_inicio": "2024-01-01",
    "fecha_fin": "2024-03-31"
  }' | jq
```

---

## 🏗️ Arquitectura

```
pivot/
├── kernel/              # ✨ NUEVO - Núcleo del sistema
│   ├── contrato.py      # Tipos base (Estrategia, Contexto, Señal)
│   ├── api/             # API FastAPI (11 endpoints)
│   ├── feeds/           # 🔄 Pendiente (Fase 3)
│   └── tests/           # 🔄 Pendiente (Fase 6)
│
├── core/                # Detectores D0-D5 (existente)
│   ├── base.py          # Contexto y Detector abstracto
│   ├── d0_estructura.py # Estructura de mercado
│   ├── d1_ruptura.py    # Rupturas
│   ├── d2_sweep.py      # Sweeps
│   ├── d2_anticipacion.py
│   ├── d3_fvg.py        # Fair Value Gaps
│   ├── d4_orderblock.py # Order Blocks
│   └── d5_mss_sweep.py  # MSS + Sweep
│
├── estrategias/         # Estrategias plugin
│   ├── base.py          # Imports desde kernel.contrato
│   ├── registro.py      # Registro dinámico
│   ├── dummy/           # Estrategia de prueba
│   └── ema_cross/       # Cruce de EMAs
│
├── activos/             # Configuración por activo
│   ├── eurusd.json
│   └── xauusd.json
│
├── frontend/            # React 18 + TypeScript + Vite
├── cli.py               # Entry point CLI
└── docs/                # Documentación
```

---

## 🔌 Crear una Estrategia

### 1. Crear carpeta
```bash
mkdir -p estrategias/mi_estrategia
```

### 2. Implementar `estrategias/mi_estrategia/__init__.py`
```python
from estrategias.base import Estrategia, Contexto, Señal

class MiEstrategia(Estrategia):
    nombre = "mi_estrategia"
    version = "1.0"
    timeframes = ["M15", "H1"]
    eventos = ["candle_close"]
    
    parametros = {
        "periodo": {"tipo": "int", "default": 14, "min": 5, "max": 50}
    }
    
    def setup(self, params, activo):
        self.periodo = params.get("periodo", 14)
        self.activo = activo
    
    def detectar(self, ctx: Contexto) -> list[Señal]:
        # Acceder a datos
        precio = ctx.precio
        df = ctx.df_m15
        
        # Calcular indicador
        ema = ctx.indicador("M15", "EMA", {"periodo": self.periodo})
        
        # Tu lógica de trading
        if len(ema) < 2:
            return []
        
        # Generar señal si hay crossover
        if ema.iloc[-1] > ema.iloc[-2]:
            return [Señal(
                estrategia=self.nombre,
                simbolo=self.activo.simbolo,
                direccion=1,  # LONG
                precio=precio,
                tiempo=ctx.tiempo,
                narrativa="Crossover alcista detectado"
            )]
        
        return []
```

### 3. Reiniciar servidor
La estrategia se auto-registra automáticamente.

---

## 📋 Contratos Base

### `Estrategia` (Abstracta)
Clase base que todas las estrategias deben implementar:
- `setup(params, activo)`: Inicialización
- `detectar(ctx)`: Lógica de trading → lista de `Señal`

### `Contexto`
Snapshot completo del mercado:
- **DataFrames**: M1, M5, M15, M30, H1, H4, D1
- **Indicadores**: EMA, ATR, RSI, SMA (con caché automática)
- **Helpers**: `i_high()`, `i_low()`, `i_close()`, `indicador()`
- **Buffers**: Indicadores precalculados
- **Estructura**: Datos de detectores D0-D5

### `Señal`
Representa una oportunidad de trading:
- Dirección (LONG=1, SHORT=-1)
- Precio entrada, SL, TP
- Confianza (min, max), score
- Overlays para TradingView
- Metadata completa

### `ActivoInfo`
Configuración del instrumento:
- Símbolo, punto, tick_size
- Sesión, timezone

---

## 🛣️ Hoja de Ruta Detallada

### ✅ Fase 1: Cimientos (COMPLETADA)
- [x] `kernel/contrato.py` con tipos base completos
- [x] API FastAPI con 11 endpoints
- [x] Sistema de indicadores integrado en Contexto
- [x] Registro dinámico de estrategias funcional
- [x] Imports arreglados
- [x] Estrategias existentes validadas

### 🔄 Fase 2: Backtest Engine
- [ ] Motor de replay barra a barra
- [ ] Feed CSV histórico
- [ ] Cálculo de métricas:
  - Winrate, Profit Factor
  - Sharpe Ratio, Sortino
  - Max Drawdown, CAR/MDD
- [ ] Equity curve
- [ ] Reportes detallados

### ⏳ Fase 3: Data Feeds
- [ ] Feed CSV para backtest
- [ ] WebSocket Deriv API (live)
- [ ] Gestión de sesiones (Asia, London, NY)
- [ ] Timezones y DST

### ⏳ Fase 4: Estrategia Pivot
- [ ] Portar lógica original
- [ ] Integrar detectores D0-D5
- [ ] Scoring avanzado
- [ ] Parámetros optimizables

### ⏳ Fase 5: Runtime Multiactivo
- [ ] Thread por activo
- [ ] SQLite asincrónico
- [ ] Alertas en tiempo real
- [ ] Gestión de capital

### ⏳ Fase 6: Madurez Profesional
- [ ] Tests unitarios (>80% coverage)
- [ ] Integration tests
- [ ] Docker + docker-compose
- [ ] GitHub Actions CI/CD
- [ ] Documentación completa
- [ ] Examples y tutorials

---

## 📈 Métricas de Calidad

| Dimensión | Antes | Ahora | Objetivo |
|-----------|-------|-------|----------|
| **Código Ejecutable** | ❌ No | ✅ Sí | ✅ |
| **API Funcional** | ❌ 0 | ✅ 11 | ✅ 15+ |
| **Estrategias** | ❌ Error | ✅ 2 | ✅ 5+ |
| **Backtest** | ❌ N/A | 🔄 Mock | ✅ Completo |
| **Tests** | ❌ 0% | ❌ 0% | ✅ >80% |
| **Docs** | ❌ Obsoletas | ✅ OK | ✅ Completas |
| **Docker** | ❌ No | ❌ No | ✅ Sí |
| **Overall** | **2.2/10** | **6.5/10** | **9.0/10** |

---

## 🔧 Desarrollo

### Ejecutar tests (Fase 6)
```bash
pytest kernel/tests/ -v --cov=kernel
```

### Linting
```bash
flake8 kernel/ estrategias/ core/
black kernel/ estrategias/ core/
```

### Debug mode
```bash
uvicorn kernel.api.app:app --reload --log-level debug
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: kernel.contrato"
✅ **Solucionado en Fase 1** - El módulo ahora existe.

### Error: "AttributeError: descripcion"
✅ **Solucionado** - Ahora usa `getattr(c, "descripcion", "")`.

### Estrategias no aparecen
Verificar que:
1. La carpeta tenga `__init__.py`
2. La clase herede de `Estrategia`
3. Tenga los atributos requeridos (`nombre`, `version`, etc.)

---

## 📄 Licencia

MIT License - Ver archivo LICENSE.

---

## 🤝 Contribuir

1. Fork el repositorio
2. `git checkout -b feature/nueva-funcionalidad`
3. `git commit -m 'Añadir nueva funcionalidad'`
4. `git push origin feature/nueva-funcionalidad`
5. Pull Request

---

## 📞 Soporte

- Issues: GitHub Issues
- Docs: `docs/MANUAL.md`
- API Docs: `http://localhost:8000/docs`

---

**PIVOT Trading System v2.0**  
*De prototipo amateur a sistema profesional* 🚀

