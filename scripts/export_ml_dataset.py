#!/usr/bin/env python3
"""
Script para exportar dataset de ML desde la base de datos SQLite.

Uso:
    python scripts/export_ml_dataset.py [--output salida.csv] [--format csv|parquet]

Exporta todas las señales históricas con sus resultados para entrenamiento de modelos.
"""

import argparse
import sys
from pathlib import Path

# Agregar root al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.storage import Database
import pandas as pd


def export_ml_dataset(output_path: str = "ml_dataset.csv", format: str = "csv"):
    """
    Exporta la tabla signals_ml_dataset a CSV o Parquet.
    
    Args:
        output_path: Ruta del archivo de salida
        format: 'csv' o 'parquet'
    """
    db = Database("data/pivot.db")
    db.initialize()
    
    conn = db._get_connection()
    
    # Verificar si existe la tabla
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='signals_ml_dataset'
    """)
    
    if not cursor.fetchone():
        print("❌ No existe la tabla signals_ml_dataset en la base de datos.")
        print("   Ejecutá backtests o operaciones en vivo primero.")
        return False
    
    # Consultar todos los datos
    query = """
        SELECT * FROM signals_ml_dataset 
        ORDER BY timestamp_entrada
    """
    
    df = pd.read_sql_query(query, conn)
    
    if len(df) == 0:
        print("⚠️  La tabla signals_ml_dataset está vacía.")
        return False
    
    # Exportar
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    if format.lower() == "csv":
        df.to_csv(output_path, index=False)
        print(f"✅ Dataset exportado a {output_path}")
        print(f"   - {len(df)} registros")
        print(f"   - {len(df.columns)} columnas")
        
        # Estadísticas básicas
        if 'fue_ganadora' in df.columns:
            ganadoras = df['fue_ganadora'].sum()
            total = len(df)
            winrate = (ganadoras / total * 100) if total > 0 else 0
            print(f"   - Win Rate histórico: {winrate:.2f}% ({ganadoras}/{total})")
            
    elif format.lower() == "parquet":
        try:
            parquet_path = str(output_file.with_suffix('.parquet'))
            df.to_parquet(parquet_path, index=False)
            print(f"✅ Dataset exportado a {parquet_path}")
            print(f"   - {len(df)} registros")
        except ImportError:
            print("❌ PyArrow no instalado. Instalalo con: pip install pyarrow")
            return False
    else:
        print(f"❌ Formato '{format}' no soportado. Usá 'csv' o 'parquet'.")
        return False
    
    # Mostrar columnas disponibles
    print(f"\n📊 Columnas disponibles:")
    for col in df.columns:
        print(f"   - {col}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Exportar dataset de ML para entrenamiento de modelos"
    )
    parser.add_argument(
        "--output", "-o",
        default="ml_dataset.csv",
        help="Ruta del archivo de salida (default: ml_dataset.csv)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "parquet"],
        default="csv",
        help="Formato de salida (default: csv)"
    )
    
    args = parser.parse_args()
    
    success = export_ml_dataset(args.output, args.format)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
