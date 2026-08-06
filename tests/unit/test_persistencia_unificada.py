"""
Test de unificación de persistencia (G12)
Verifica que core/persistencia.py fue eliminado y todo usa kernel/storage.py
"""
import os
import pytest
import tempfile
import asyncio
from datetime import datetime

def test_persistencia_csv_eliminada():
    """Verifica que core/persistencia.py ya no existe"""
    persistencia_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'persistencia.py')
    assert not os.path.exists(persistencia_path), "core/persistencia.py debe ser eliminado"

def test_motor_v8_no_importa_persistencia():
    """Verifica que motor_v8.py no importa desde core.persistencia"""
    motor_path = '/workspace/core/motor_v8.py'
    with open(motor_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'from core.persistencia import' not in content, "motor_v8.py no debe importar Persistencia"
    assert 'from core import persistencia' not in content, "motor_v8.py no debe importar persistencia"
    assert 'from kernel.storage import Database' in content, "motor_v8.py debe importar Database de kernel.storage"

def test_database_guarda_senal_core():
    """Test funcional de guardar señal en SQLite"""
    from kernel.storage import Database
    
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, 'test.db')
    db = Database(db_path)
    db.initialize()
    
    async def run_test():
        await db.guardar_senal_core(
            signal_id='TEST001',
            entry_time=datetime.now(),
            symbol='EURUSD',
            direction=1,
            entry_price=1.0850,
            detector='D2',
            tipo='SWEEP',
            hipotesis_prob_min=0.6,
            hipotesis_prob_max=0.8,
            hipotesis_expiry_velas=5,
            conviccion=75.0,
            regimen_volatilidad='NORMAL'
        )
        
        senales = await db.obtener_senales_core(symbol='EURUSD', limite=10)
        assert len(senales) == 1
        assert senales[0]['signal_id'] == 'TEST001'
        assert senales[0]['detector'] == 'D2'
        assert senales[0]['direction'] == 1
    
    asyncio.run(run_test())

def test_database_cola_pendientes():
    """Test funcional de cola de señales pendientes"""
    from kernel.storage import Database
    
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, 'test.db')
    db = Database(db_path)
    db.initialize()
    
    async def run_test():
        # Guardar 3 señales con diferentes prioridades
        await db.guardar_cola_senal('S1', 'EURUSD', 'D1', priority=1)
        await db.guardar_cola_senal('S2', 'EURUSD', 'D3', priority=3)
        await db.guardar_cola_senal('S3', 'EURUSD', 'D2', priority=2)
        
        pendientes = await db.obtener_cola_pendientes()
        assert len(pendientes) == 3
        
        # Verificar orden por prioridad
        assert pendientes[0]['signal_id'] == 'S1'  # Priority 1
        assert pendientes[1]['signal_id'] == 'S3'  # Priority 2
        assert pendientes[2]['signal_id'] == 'S2'  # Priority 3
        
        # Marcar una como procesada
        await db.marcar_cola_procesada('S1')
        pendientes2 = await db.obtener_cola_pendientes()
        assert len(pendientes2) == 2
    
    asyncio.run(run_test())

def test_motor_v8_usa_database():
    """Verifica que PivotRadarEngine usa Database en lugar de Persistencia"""
    from core.motor_v8 import PivotRadarEngine
    
    test_dir = tempfile.mkdtemp()
    engine = PivotRadarEngine(
        symbol='EURUSD',
        data_dir=test_dir,
        point=0.00001,
        modo_test=True
    )
    
    assert hasattr(engine, 'db'), "PivotRadarEngine debe tener atributo 'db'"
    assert not hasattr(engine, 'persistencia'), "PivotRadarEngine no debe tener atributo 'persistencia'"
    
    # Verificar que la DB está inicializada
    assert engine.db._initialized, "Database debe estar inicializada"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
