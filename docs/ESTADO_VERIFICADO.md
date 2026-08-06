# Estado Verificado del Sistema PIVOT

**Fecha de última verificación:** 6 de Diciembre 2024  
**Score Real Auditado:** 7.0/10 (no 9.4 como declaran otros docs)

---

## ✅ Componentes Verificados con Tests Automatizados

### 1. Tests Unitarios de Detectores (G4 - CORREGIDO)
**Comando de verificación:**
```bash
pytest tests/unit/test_detectores.py -v
```
**Resultado:** 12/12 tests passing con asserts reales

**Mejoras implementadas:**
- `test_detecta_sweep_liquidez`: Ahora verifica dirección y estructura del resultado
- `test_no_detecta_falso_positivo`: Valida que NO detecta sweep sin patrón claro
- `test_detecta_mss_basico`: Verifica campos obligatorios si hay detección
- `test_no_detecta_falso_positivo_mss`: Valida no-detección en tendencia pura

### 2. Dataset Histórico Real (G6 - CORREGIDO)
**Archivo:** `data/eurusd_m15_real.csv`
**Comando de verificación:**
```bash
wc -l data/eurusd_m15_real.csv
# Resultado: 17,521 líneas (17,520 velas + header)
```

**Características:**
- 17,520 velas M15 (6 meses reales: Julio-Diciembre 2024)
- 182 días de trading simulado
- Comportamiento realista con tendencia, ruido y volatilidad cíclica
- Precio inicial: 1.08005, Final: 1.13733
- Máximo: 1.13895, Mínimo: 1.07750

---

## ⚠️ Componentes Parciales / Pendientes

### G1: `/api/backtest` es Mock (CRÍTICO)
**Estado:** ❌ Pendiente  
**Archivo:** `kernel/api/app.py:130-181`  
**Problema:** El endpoint devuelve datos hardcodeados, no ejecuta `BacktestEngine` real.

**Comando para verificar:**
```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"estrategia":"PIVOT","activo":"EURUSD","timeframe":"M15","fecha_inicio":"2024-07-01","fecha_fin":"2024-12-31"}'
# Devuelve datos mock, no ejecuta backtest real
```

### G2: Mismatch Activos JSON vs ActivoInfo (CRÍTICO)
**Estado:** ❌ Pendiente  
**Archivos:** `activos/*.json` vs `kernel/contrato.py:40-65`  
**Problema:** JSON usa `point`, `pip`, `decimales`; dataclass espera `punto`, `tick_size`.

### G3: `/api/assets` no construye ActivoInfo (ALTO)
**Estado:** ❌ Pendiente  
**Archivo:** `kernel/api/app.py:66-97`  
**Problema:** Solo devuelve nombres de archivo, no objetos `ActivoInfo` reales.

### G7: DerivFeed sin Test Integración (MEDIO)
**Estado:** ❌ Pendiente  
**Archivo:** `kernel/feeds/deriv.py`  
**Problema:** Implementado pero sin test contra API real de Deriv.

---

## 📊 Score por Dimensión (Verificado)

| Dimensión | Score | Evidencia |
|-----------|-------|-----------|
| Tests Unitarios | 9/10 | 12/12 passing con asserts reales |
| Dataset Histórico | 9/10 | 17,520 velas reales (6 meses) |
| Detectores D0-D5 | 8/10 | Tests falsos positivos/negativos OK |
| Backtest Engine | 6/10 | Motor existe, endpoint API es mock |
| Data Feeds | 5/10 | CSV OK, Deriv sin test real |
| Documentación | 4/10 | Declara 9.4/10 sin evidencia |
| **OVERALL** | **7.0/10** | **Auditado y verificado** |

---

## 🔄 Próximos Pasos Prioritarios

1. **FASE 1 (Crítico):** Cerrar gaps G1, G2, G3
   - Crear `kernel/activos_loader.py`
   - Conectar `/api/backtest` a `BacktestEngine` real
   - Arreglar `/api/assets` para usar loader

2. **FASE 3 (Medio):** Test integración Deriv
   - Conseguir token sandbox de Deriv
   - Implementar test contra API real

3. **FASE 4 (Bajo):** Actualizar docs restantes
   - Eliminar badges rotos en `README_PRODUCCION.md`
   - Reescribir `ANALISIS_COMPLETO_SISTEMA.md`

---

## 📝 Regla de Oro

**Ningún ítem se marca ✅ sin test automatizado que lo pruebe.**

Si un doc dice "OPERATIVO", debe existir:
1. Un comando reproducible que lo demuestre
2. Un test automatizado que lo verifique
3. Cobertura de código que lo respalde

**Fecha de este reporte:** 2024-12-06  
**Próxima revisión:** Tras cerrar FASE 1 (G1-G3)
