#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de ejemplo para ejecutar backtest de opciones binarias con PIVOT.
Muestra cómo configurar y usar el motor binario.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Agregar ruta al path
sys.path.insert(0, str(Path(__file__).parent))

from kernel.contrato_binario import ConfiguracionBinaria
from kernel.contrato import ActivoInfo
from kernel.feeds.csv import CSVFeed
from kernel.backtest_binario import BacktestEngineBinario
from estrategias.pivot_binaria import EstrategiaPivotBinaria


def main():
    """Ejecuta un backtest de ejemplo con opciones binarias."""
    
    print("="*70)
    print("PIVOT - SISTEMA DE OPCIONES BINARIAS")
    print("="*70)
    
    # 1. Configurar activo (EURUSD)
    activo = ActivoInfo(
        simbolo="EURUSD",
        punto=0.00001,
        tick_size=0.00001,
        contract_size=100000,
        session_open="00:00",
        session_close="23:59",
        timezone=timezone.utc,
    )
    
    # 2. Configurar parámetros para opciones binarias
    config_binaria = ConfiguracionBinaria(
        expiraciones_soportadas=[5, 15, 30, 60],
        payout_call=0.80,      # 80% de retorno si gana
        payout_put=0.80,       # 80% de retorno si gana
        reembolso_atm=0.0,     # Sin reembolso en empate
        porcentaje_riesgo=0.02,  # 2% del capital por operación
        usar_martingale=False,   # Martingale desactivado por defecto
        martingale_multiplicador=2.0,
        martingale_max_nivel=3,
        volatilidad_minima=0.0001,  # Filtrar mercados muy tranquilos
        volatilidad_maxima=0.0050,  # Filtrar mercados muy volátiles
    )
    
    # 3. Crear estrategia
    estrategia = EstrategiaPivotBinaria()
    
    # 4. Cargar datos históricos
    print("\nCargando datos históricos...")
    
    try:
        # Feed M15 (principal para binarias)
        feed_m15 = CSVFeed(
            path="/workspace/data/eurusd_m15.csv",
            timeframe="M15",
            symbol="EURUSD"
        )
        
        # Feed H1 para contexto
        feed_h1 = CSVFeed(
            path="/workspace/data/eurusd_h1.csv",
            timeframe="H1",
            symbol="EURUSD"
        )
        
        # Feed H4 para tendencia mayor
        feed_h4 = CSVFeed(
            path="/workspace/data/eurusd_h4.csv",
            timeframe="H4",
            symbol="EURUSD"
        )
        
        feeds = {
            "M15": feed_m15,
            "H1": feed_h1,
            "H4": feed_h4,
        }
        
        print(f"✓ Datos cargados:")
        print(f"  - M15: {len(feed_m15.df)} barras")
        print(f"  - H1: {len(feed_h1.df)} barras")
        print(f"  - H4: {len(feed_h4.df)} barras")
        
    except Exception as e:
        print(f"✗ Error cargando datos: {e}")
        print("\nNOTA: Si no tienes archivos CSV, crea datos dummy para probar:")
        print("  python scripts/generar_datos_dummy.py")
        return 1
    
    # 5. Crear motor de backtest
    backtester = BacktestEngineBinario(
        estrategia=estrategia,
        activo=activo,
        config_binaria=config_binaria,
        capital_inicial=1000.0,  # $1000 iniciales
        db=None,  # Sin DB para este ejemplo
    )
    
    # 6. Ejecutar backtest
    print("\n" + "="*70)
    print("EJECUTANDO BACKTEST...")
    print("="*70 + "\n")
    
    resultados = backtester.ejecutar(feeds)
    
    # 7. Mostrar resultados detallados
    print("\n" + "="*70)
    print("ANÁLISIS POR DETECTOR")
    print("="*70)
    
    if resultados.estadisticas_por_detector:
        for detector, stats in sorted(resultados.estadisticas_por_detector.items()):
            print(f"\n{detector}:")
            print(f"  Operaciones: {stats['total']}")
            print(f"  Win Rate:    {stats['winrate']:.1f}%")
            print(f"  PnL Total:   ${stats['pnl_total']:.2f}")
            print(f"  PnL Prom:    ${stats['pnl_promedio']:.2f}")
    
    print("\n" + "="*70)
    print("ANÁLISIS POR TIEMPO DE EXPIRACIÓN")
    print("="*70)
    
    if resultados.estadisticas_por_expiracion:
        for exp, stats in sorted(resultados.estadisticas_por_expiracion.items()):
            print(f"\n{exp} minutos:")
            print(f"  Operaciones: {stats['total']}")
            print(f"  Win Rate:    {stats['winrate']:.1f}%")
            print(f"  PnL Total:   ${stats['pnl_total']:.2f}")
    
    print("\n" + "="*70)
    print("ANÁLISIS POR SESIÓN")
    print("="*70)
    
    if resultados.estadisticas_por_sesion:
        for sesion, stats in sorted(resultados.estadisticas_por_sesion.items()):
            print(f"\n{sesion}:")
            print(f"  Operaciones: {stats['total']}")
            print(f"  Win Rate:    {stats['winrate']:.1f}%")
            print(f"  PnL Total:   ${stats['pnl_total']:.2f}")
    
    # 8. Guardar resultados en JSON (opcional)
    try:
        import json
        resultado_dict = resultados.to_dict()
        with open("/workspace/data/resultados_binarios.json", "w") as f:
            json.dump(resultado_dict, f, indent=2, default=str)
        print(f"\n✓ Resultados guardados en /workspace/data/resultados_binarios.json")
    except Exception as e:
        print(f"\n✗ Error guardando resultados: {e}")
    
    print("\n" + "="*70)
    print("BACKTEST FINALIZADO")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
