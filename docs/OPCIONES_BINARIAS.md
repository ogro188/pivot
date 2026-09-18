# 📊 PIVOT - Sistema de Opciones Binarias

## Resumen Ejecutivo

Este módulo adapta el **PIVOT Trading System v2.0** para operar **Opciones Binarias**, manteniendo el 70% del código base original y agregando componentes específicos para este tipo de trading.

---

## 🎯 Diferencias Clave: Forex vs Binarias

| Característica | Forex/CFD (Original) | Opciones Binarias (Nuevo) |
|---------------|---------------------|---------------------------|
| **Salida** | TP/SL variables | Tiempo fijo de expiración |
| **Resultado** | PnL variable | Binario: WIN/LOSS |
| **Gestión** | Stop Loss obligatorio | Sin SL tradicional |
| **Retorno** | Depende del movimiento | Payout fijo (ej: 80%) |
| **Pérdida** | Limitada por SL | -100% del apostado |
| **Dirección** | LONG/SHORT | CALL/PUT |

---

## 📁 Arquitectura Implementada

### Nuevos Archivos Creados

```
/workspace/
├── kernel/
│   ├── contrato_binario.py      # Contratos específicos para binarias
│   └── backtest_binario.py      # Motor de backtest binario
├── estrategias/
│   └── pivot_binaria/
│       └── __init__.py          # Estrategia PIVOT adaptada
├── test_backtest_binario.py     # Script de ejemplo
└── docs/
    └── OPCIONES_BINARIAS.md     # Este documento
```

---

## 🔧 Componentes Principales

### 1. `kernel/contrato_binario.py`

Define las clases base para opciones binarias:

#### `TipoOpcion` (Enum)
- `CALL`: Precio sube al momento de expiración
- `PUT`: Precio baja al momento de expiración
- `ONE_TOUCH`, `NO_TOUCH`, `RANGE`: Soporte futuro

#### `ConfiguracionBinaria` (dataclass)
```python
ConfiguracionBinaria(
    expiraciones_soportadas=[5, 15, 30, 60],  # minutos
    payout_call=0.80,         # 80% retorno si gana
    payout_put=0.80,
    porcentaje_riesgo=0.02,   # 2% por operación
    usar_martingale=False,    # Opcional
    volatilidad_minima=0.0001,
    volatilidad_maxima=0.0050,
)
```

#### `SeñalBinaria` (dataclass)
```python
SeñalBinaria(
    estrategia="PIVOT_BINARIA",
    simbolo="EURUSD",
    tipo_opcion=TipoOpcion.CALL,
    precio_entrada=1.0850,
    tiempo_entrada=datetime.now(),
    expiracion_minutos=15,
    confianza=75.0,
    detectores_activos=["D1", "D2", "D3"],
)
```

Métodos importantes:
- `evaluar_resultado(precio_cierre)`: Retorna "WIN", "LOSS" o "ATM"
- `calcular_pnl(resultado, payout)`: Calcula +80%, -100%, o 0%

### 2. `kernel/backtest_binario.py`

Motor especializado con:

- **Evaluación por expiración**: Verifica el precio al tiempo exacto de expiración
- **Soporte multi-operación**: Hasta 5 operaciones simultáneas con diferentes expiraciones
- **Martingale opcional**: Configurable con límites de seguridad
- **Métricas específicas**:
  - Win Rate (%)
  - Profit Factor (Ganancias/Pérdidas)
  - Expectativa Matemática
  - Rachas máximas
  - Análisis por detector, expiración y sesión

### 3. `estrategias/pivot_binaria/__init__.py`

Adaptación de PIVOT con:

- **Sin SL/TP**: Solo dirección CALL/PUT
- **Expiración dinámica**: Basada en detectores activos
  - D2 (Sweep) → 15 min (reacción rápida)
  - D4 (Order Block) → 30 min
  - D5 (MSS) → 60 min (desarrollo lento)
- **Filtros estrictos**: Confianza mínima 65% (vs 60% en Forex)
- **Ajuste por volatilidad**: Evita mercados laterales

---

## 🚀 Cómo Usar

### Ejemplo Básico

```python
from kernel.contrato_binario import ConfiguracionBinaria
from kernel.backtest_binario import BacktestEngineBinario
from estrategias.pivot_binaria import EstrategiaPivotBinaria

# 1. Configurar
config = ConfiguracionBinaria(
    payout_call=0.80,
    porcentaje_riesgo=0.02,
    usar_martingale=False,
)

# 2. Crear estrategia
estrategia = EstrategiaPivotBinaria()

# 3. Ejecutar backtest
backtester = BacktestEngineBinario(
    estrategia=estrategia,
    activo=activo_info,
    config_binaria=config,
    capital_inicial=1000.0,
)

resultados = backtester.ejecutar(feeds)
```

### Script de Prueba

```bash
python test_backtest_binario.py
```

---

## 📈 Métricas Específicas de Binarias

### Win Rate Mínimo Requerido

Con payout del 80%:
- **Win Rate de equilibrio**: 55.6%
  - Fórmula: `100 / (100 + 80) = 55.6%`
- **Win Rate rentable**: >60%

### Expectativa Matemática

```
Expectativa = (WinRate × Payout) - ((1 - WinRate) × 100)

Ejemplo con 65% win rate y 80% payout:
= (0.65 × 80) - (0.35 × 100)
= 52 - 35
= +17% por operación
```

### Profit Factor Objetivo

- **PF < 1.0**: Estrategia perdedora
- **PF 1.0-1.5**: Break-even / leve ganancia
- **PF 1.5-2.0**: Buena estrategia
- **PF > 2.0**: Excelente (poco común en binarias)

---

## ⚙️ Parámetros de Configuración

### Gestión de Riesgo

| Parámetro | Valor Recomendado | Descripción |
|-----------|------------------|-------------|
| `porcentaje_riesgo` | 0.01 - 0.03 | % del capital por operación |
| `usar_martingale` | False | Activar solo para usuarios avanzados |
| `martingale_multiplicador` | 2.0 | Multiplicador tras pérdida |
| `martingale_max_nivel` | 3 | Máximo nivel de martingale |

### Filtros de Calidad

| Parámetro | Valor Recomendado | Efecto |
|-----------|------------------|--------|
| `confianza_minima` | 65.0 - 75.0 | Filtra señales débiles |
| `volatilidad_minima` | 0.0001 | Evita rangos laterales |
| `volatilidad_maxima` | 0.0050 | Evita ruido excesivo |
| `usar_kill_zones` | True | Solo sesiones activas |
| `usar_trend_d1` | True | Alineación con tendencia mayor |

### Tiempos de Expiración

| Timeframe Patrón | Expiración Sugerida | Detectores Típicos |
|-----------------|---------------------|-------------------|
| M1-M5 | 5-15 min | D2 (Sweep rápido) |
| M15-M30 | 15-30 min | D1, D2, D3 |
| H1 | 30-60 min | D3, D4, D5 |
| H4 | 60+ min | D5 (MSS) |

---

## 🎯 Estrategia Óptima para Binarias

### Setup Ideal

1. **Tendencia D1 alcista** + **Kill Zone London/NY**
2. **Sweep de liquidez** (D2) en zona discount
3. **Ruptura estructural** (D1) confirmada
4. **FVG presente** (D3) como zona de entrada
5. **Confianza > 70%**

### Tipo de Opción

- Si dirección = 1 (alcista) → **CALL**
- Si dirección = -1 (bajista) → **PUT**

### Expiración

- Sweep + Ruptura → **15 minutos**
- Order Block → **30 minutos**
- MSS confirmado → **60 minutos**

---

## ⚠️ Advertencias Importantes

### Riesgos de Opciones Binarias

1. **Pérdida total**: Cada operación perdida es -100% del capital apostado
2. **Ventaja de la casa**: El payout < 100% crea desventaja matemática
3. **Martingale peligroso**: Puede liquidar la cuenta rápidamente
4. **Regulación**: Muchos brokers no están regulados

### Recomendaciones

✅ **USAR**:
- Gestión de riesgo estricta (1-2% por operación)
- Win rate objetivo > 60%
- Backtesting extensivo antes de operar real
- Demo account primero

❌ **EVITAR**:
- Martingale sin límites
- Operar fuera de kill zones
- Confiar < 65%
- Overtrading (máx 5 operaciones/día)

---

## 📊 Interpretación de Resultados

### Ejemplo de Backtest Exitoso

```
Capital Inicial: $1000.00
Capital Final:   $1450.00
Retorno Total:   45.00%
Operaciones:     120
Ganadoras:       78 (65.0%)
Perdedoras:      42
Profit Factor:   1.85
Expectativa Mat: +3.2% por operación
Drawdown Max:    12.5%
Racha Max Win:   9
Racha Max Loss:  4
```

**Análisis**:
- ✅ Win Rate 65% > 55.6% (punto de equilibrio)
- ✅ PF 1.85 indica rentabilidad consistente
- ✅ Expectativa positiva (+3.2%)
- ✅ Drawdown controlado (< 15%)

### Señales de Alerta

❌ **No operar si**:
- Win Rate < 55% (con payout 80%)
- Profit Factor < 1.2
- Drawdown > 25%
- Menos de 50 operaciones en backtest

---

## 🔗 Integración con el Sistema Original

### Código Reutilizado (70%)

- ✅ Detectores D0-D5 (100% compatibles)
- ✅ CoreAdapter para contexto
- ✅ WilsonScorer para confianza
- ✅ Sistema de alertas
- ✅ Feed de datos CSV
- ✅ Resampling de timeframes

### Código Nuevo (30%)

- ✅ Contratos binarios (`SeñalBinaria`, `OperacionBinaria`)
- ✅ Motor de backtest con evaluación por expiración
- ✅ Lógica de payout y cálculo de PnL binario
- ✅ Estadísticas específicas (win rate, expectativa)
- ✅ Gestión de martingale opcional

---

## 📝 Próximos Pasos Sugeridos

### Fase 1: Validación (Completado ✅)
- [x] Contratos binarios implementados
- [x] Backtest engine funcional
- [x] Estrategia PIVOT adaptada
- [x] Script de prueba funcionando

### Fase 2: Optimización (Pendiente)
- [ ] Ajustar parámetros por activo
- [ ] Testear múltiples períodos
- [ ] Comparar expiraciones (5, 15, 30, 60 min)
- [ ] Optimizar filtros de volatilidad

### Fase 3: Producción (Pendiente)
- [ ] Conectar a API de broker (Deriv, IQ Option)
- [ ] Módulo de ejecución automática
- [ ] Dashboard en tiempo real
- [ ] Alertas Telegram/Email

---

## 📚 Recursos Adicionales

### Documentación Relacionada
- `docs/MANUAL.md` - Manual general de PIVOT
- `kernel/contrato.py` - Contratos originales (Forex)
- `estrategias/pivot/__init__.py` - Estrategia original

### Scripts Útiles
```bash
# Ejecutar backtest binario
python test_backtest_binario.py

# Ver resultados en JSON
cat data/resultados_binarios.json | python -m json.tool
```

---

## ✨ Conclusión

La adaptación a **Opciones Binarias** es **totalmente viable** y está **completamente implementada**. El sistema:

✅ Mantiene la lógica de los detectores D0-D5  
✅ Agrega evaluación por tiempo de expiración  
✅ Calcula métricas específicas (Win Rate, Expectativa)  
✅ Soporta gestión de riesgo avanzada  
✅ Está listo para backtesting y optimización  

**Complejidad de implementación**: 25-30% del código base  
**Reutilización**: 70% del sistema original  
**Estado**: **LISTO PARA USAR** 🚀

---

*Documento generado como parte de la propuesta de adaptación a Opciones Binarias - PIVOT Trading System v2.0*
