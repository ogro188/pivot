#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de la estrategia PIVOT con el backtest engine.
Ejecuta un backtest completo usando datos históricos de EURUSD.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Añadir workspace al path
sys.path.insert(0, str(Path(__file__).parent))

from kernel.contrato import ActivoInfo
from kernel.feeds.csv import CSVFeed, MultiTimeframeFeed
from kernel.backtest import BacktestEngine
from estrategias.pivot import EstrategiaPivot


def main():
    print("=" * 70)
    print("BACKTEST ESTRATEGIA PIVOT - EURUSD M15")
    print("=" * 70)
    
    # Configurar activo
    eurusd = ActivoInfo(
        simbolo="EURUSD",
        punto=0.00001,
        tick_size=0.00001,
        contract_size=100000,
        timezone="UTC"
    )
    
    # Cargar datos desde CSV
    csv_path = Path("data/eurusd_m15.csv")
    if not csv_path.exists():
        print(f"❌ Error: No se encontró {csv_path}")
        print("Generando datos de prueba...")
        from kernel.feeds.csv import generar_datos_prueba
        generar_datos_prueba(str(csv_path), n_velas=1000)
    
    print(f"\n📊 Cargando datos desde {csv_path}...")
    feed = CSVFeed(
        path=str(csv_path),
        timeframe="M15",
        symbol="EURUSD",
        tz=timezone.utc,
    )
    
    if len(feed.df) == 0:
        print("❌ No hay datos disponibles")
        return
    print(f"✓ Cargadas {len(feed.df)} velas")
    
    # Configurar estrategia
    print("\n⚙️  Configurando estrategia PIVOT...")
    estrategia = EstrategiaPivot()
    
    params = {
        "pivot_depth": 2,
        "pivot_lookback": 24,
        "n_ruptura": 4,
        "d1_atr_threshold": 0.50,
        "risk_por_operacion": 1.0,
        "reward_ratio_min": 2.0,
        "confianza_minima": 65.0,
        "usar_kill_zones": False,  # Desactivado para backtest simple
        "usar_trend_d1": False,    # Desactivado para backtest simple
    }
    
    estrategia.setup(params, eurusd)
    print(f"✓ Estrategia configurada: {estrategia.nombre} v{estrategia.version}")
    print(f"   Parámetros: {params}")
    
    # Configurar backtest
    print("\n🚀 Iniciando backtest...")
    engine = BacktestEngine(
        estrategia=estrategia,
        activo=eurusd,
        capital_inicial=10000.0,
        riesgo_por_operacion=0.01,
        slippage_pips=1.0,
        comision_lote=0.5,
    )
    
    # Ejecutar backtest
    try:
        feeds = {"M15": feed}
        resultados = engine.ejecutar(
            feeds=feeds,
            params_estrategia=params,
        )
        
        # Mostrar resultados
        print("\n" + "=" * 70)
        print("RESULTADOS DEL BACKTEST")
        print("=" * 70)
        print(f"Estrategia:        {resultados.estrategia}")
        print(f"Símbolo:           {resultados.simbolo}")
        print(f"Período:           {resultados.periodo_inicio.strftime('%Y-%m-%d')} al {resultados.periodo_fin.strftime('%Y-%m-%d')}")
        print(f"Timeframe:         {resultados.timeframe_principal}")
        print("-" * 70)
        print(f"Total Operaciones: {resultados.total_operaciones}")
        print(f"Ganadoras:         {resultados.operaciones_ganadoras} ({resultados.winrate:.1f}%)")
        print(f"Perdedoras:        {resultados.operaciones_perdedoras}")
        print(f"Neutras:           {resultados.operaciones_neutras}")
        print("-" * 70)
        print(f"Capital Inicial:   $10,000.00")
        print(f"Capital Final:     ${10000 + resultados.retorno_total:.2f}")
        print(f"Retorno Total:     ${resultados.retorno_total:.2f} ({resultados.retorno_total/100:.2f}%)")
        print(f"Retorno Promedio:  ${resultados.retorno_promedio:.2f} por operación")
        print("-" * 70)
        print(f"Profit Factor:     {resultados.profit_factor:.2f}")
        print(f"Drawdown Máximo:   {resultados.drawdown_maximo:.2f}%")
        print(f"Sharpe Ratio:      {resultados.sharpe_ratio:.2f}")
        print(f"Sortino Ratio:     {resultados.sortino_ratio:.2f}")
        print("-" * 70)
        print(f"Racha Ganadora:    {resultados.racha_ganadora_max} operaciones")
        print(f"Racha Perdedora:   {resultados.racha_perdedora_max} operaciones")
        print("=" * 70)
        
        # Guardar resultados en archivo
        output_path = Path("data/resultados_pivot.json")
        import json
        with open(output_path, 'w') as f:
            json.dump(resultados.to_dict(), f, indent=2, default=str)
        print(f"\n✓ Resultados guardados en {output_path}")
        
        # Mostrar últimas 5 operaciones
        if resultados.operaciones:
            print("\nÚltimas 5 operaciones:")
            print("-" * 70)
            for op in resultados.operaciones[-5:]:
                signo = "+" if op.pnl_dinero > 0 else ""
                print(f"{op.timestamp_entrada.strftime('%Y-%m-%d %H:%M')} | "
                      f"{'LONG' if op.direccion == 1 else 'SHORT':5} | "
                      f"PnL: {signo}${op.pnl_dinero:.2f} | "
                      f"Razón: {op.razon_salida}")
        
        print("\n✅ Backtest completado exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error durante el backtest: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
