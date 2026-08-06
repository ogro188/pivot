# -*- coding: utf-8 -*-
"""API FastAPI para PIVOT Trading System."""
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import sys
import os

# Agregar el root del workspace al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from kernel.contrato import Estrategia, ActivoInfo
from estrategias.registro import RegistroEstrategias
from kernel.api.websocket_server import websocket_endpoint, manager


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI."""
    
    app = FastAPI(
        title="PIVOT Trading API",
        description="Sistema de ejecución y backtesting de estrategias de trading",
        version="2.0.0"
    )
    
    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # En producción, especificar dominios concretos
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Inicializar registro de estrategias
    registro = RegistroEstrategias()
    
    @app.websocket("/ws")
    async def websocket_route(websocket: WebSocket):
        """Endpoint WebSocket para comunicación en tiempo real."""
        await websocket_endpoint(websocket)
    
    @app.get("/")
    async def root():
        """Endpoint raíz."""
        return {
            "message": "PIVOT Trading API v2.0",
            "status": "running",
            "endpoints": [
                "/api/assets",
                "/api/strategies",
                "/api/backtest",
                "/api/health"
            ]
        }
    
    @app.get("/api/health")
    async def health_check():
        """Verifica el estado del sistema."""
        return {
            "status": "healthy",
            "version": "2.0.0",
            "strategies_loaded": len(registro.listar())
        }
    
    @app.get("/api/assets")
    async def get_assets() -> List[Dict[str, Any]]:
        """
        Obtiene la lista de activos disponibles desde configuración JSON.
        
        Returns:
            Lista de activos con su configuración básica
        """
        from kernel.activos_loader import listar_activos_disponibles, cargar_activo
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Usar el loader real para obtener activos desde archivos JSON
        simbolos = listar_activos_disponibles()
        resultado = []
        
        for simbolo in simbolos:
            try:
                activo = cargar_activo(simbolo)
                resultado.append({
                    "simbolo": activo.simbolo,
                    "punto": activo.punto,
                    "tick_size": activo.tick_size,
                    "contract_size": activo.contract_size,
                    "activo": True
                })
            except ValueError as e:
                # Loguear y omitir activos mal formados, no fallar toda la lista
                logger.warning(f"Activo {simbolo} inválido: {e}")
        
        return resultado
    
    @app.get("/api/strategies")
    async def get_strategies() -> List[Dict[str, Any]]:
        """
        Obtiene la lista de estrategias disponibles.
        
        Returns:
            Lista de estrategias con sus metadatos
        """
        try:
            return registro.listar()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error cargando estrategias: {str(e)}")
    
    @app.get("/api/strategies/{nombre}")
    async def get_strategy(nombre: str) -> Dict[str, Any]:
        """
        Obtiene los detalles de una estrategia específica.
        
        Args:
            nombre: Nombre de la estrategia
            
        Returns:
            Información completa de la estrategia
        """
        estrategias = registro.listar()
        for estr in estrategias:
            if estr["nombre"] == nombre:
                return estr
        
        raise HTTPException(status_code=404, detail=f"Estrategia '{nombre}' no encontrada")
    
    @app.post("/api/backtest")
    async def run_backtest(request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un backtest real de una estrategia usando BacktestEngine.
        
        Request body:
        - estrategia: Nombre de la estrategia
        - activo: Símbolo del activo
        - timeframe: Timeframe a usar (ej. "M15", "H1")
        - fecha_inicio: Fecha de inicio (YYYY-MM-DD)
        - fecha_fin: Fecha de fin (YYYY-MM-DD)
        - capital_inicial: Capital inicial (default: 10000)
        - riesgo_por_operacion: Riesgo por operación % (default: 0.01)
        - slippage_pips: Slippage en pips (default: 0)
        - comision_lote: Comisión por lote (default: 0)
        - parametros: Parámetros de la estrategia (opcional)
        
        Returns:
            Resultados del backtest con métricas completas
        """
        from kernel.backtest import BacktestEngine
        from kernel.feeds.csv import CSVFeed
        from kernel.activos_loader import cargar_activo
        from datetime import datetime
        
        # Validar campos requeridos
        required_fields = ["estrategia", "activo", "timeframe", "fecha_inicio", "fecha_fin"]
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Campo requerido faltante: {field}")
        
        # Verificar que la estrategia existe
        estrategias = registro.listar()
        estrategia_nombres = [e["nombre"] for e in estrategias]
        if request["estrategia"] not in estrategia_nombres:
            raise HTTPException(
                status_code=404, 
                detail=f"Estrategia '{request['estrategia']}' no encontrada. Disponibles: {estrategia_nombres}"
            )
        
        # Cargar configuración del activo desde JSON
        try:
            activo = cargar_activo(request["activo"])
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Fabricar instancia de la estrategia
        estrategia_instancia = registro.fabricar(request["estrategia"])
        
        # Construir path al CSV de datos históricos
        data_path = f"data/{request['activo'].lower()}_{request['timeframe'].lower()}.csv"
        if not os.path.exists(data_path):
            raise HTTPException(
                status_code=404, 
                detail=f"No hay datos históricos en {data_path}. Disponible: EURUSD M15 en data/eurusd_m15.csv"
            )
        
        # Crear feed CSV con filtro de fechas
        try:
            fecha_inicio = datetime.strptime(request["fecha_inicio"], "%Y-%m-%d")
            fecha_fin = datetime.strptime(request["fecha_fin"], "%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Formato de fecha inválido. Use YYYY-MM-DD")
        
        feed = CSVFeed(
            path=data_path,
            timeframe=request["timeframe"],
            symbol=activo.simbolo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        # Configurar y ejecutar motor de backtest
        engine = BacktestEngine(
            estrategia=estrategia_instancia,
            activo=activo,
            capital_inicial=request.get("capital_inicial", 10000.0),
            riesgo_por_operacion=request.get("riesgo_por_operacion", 0.01),
            slippage_pips=request.get("slippage_pips", 0.0),
            comision_lote=request.get("comision_lote", 0.0),
        )
        
        resultado = engine.ejecutar(
            feeds={request["timeframe"]: feed},
            params_estrategia=request.get("parametros", {})
        )
        
        # Retornar resultados completos
        return {
            "status": "completed",
            "estrategia": request["estrategia"],
            "activo": request["activo"],
            "timeframe": request["timeframe"],
            "fecha_inicio": request["fecha_inicio"],
            "fecha_fin": request["fecha_fin"],
            **resultado.to_dict()
        }
    
    @app.get("/api/config")
    async def get_config() -> Dict[str, Any]:
        """Obtiene la configuración global del sistema."""
        return {
            "version": "2.0.0",
            "timeframes_soportados": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            "sessions": ["ASIA", "LONDON", "NEWYORK"],
            "kill_zones": ["KZ1", "KZ2", "KZ3"],
            "detectores": ["D0", "D1", "D2", "D3", "D4", "D5"]
        }
    
    return app


# App instance para uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
