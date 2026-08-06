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
        Obtiene la lista de activos disponibles.
        
        Returns:
            Lista de activos con su configuración
        """
        # Cargar activos desde la carpeta activos/
        activos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "activos")
        activos = []
        
        if os.path.exists(activos_dir):
            for archivo in os.listdir(activos_dir):
                if archivo.endswith(".json"):
                    simbolo = archivo.replace(".json", "")
                    activos.append({
                        "simbolo": simbolo,
                        "nombre": simbolo,
                        "activo": True
                    })
        
        # Activos por defecto si no hay archivos
        if not activos:
            activos = [
                {"simbolo": "EURUSD", "nombre": "Euro/US Dollar", "activo": True},
                {"simbolo": "XAUUSD", "nombre": "Gold/US Dollar", "activo": True},
                {"simbolo": "GBPUSD", "nombre": "British Pound/US Dollar", "activo": True},
                {"simbolo": "USDJPY", "nombre": "US Dollar/Japanese Yen", "activo": True}
            ]
        
        return activos
    
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
        Ejecuta un backtest de una estrategia.
        
        Request body:
        - estrategia: Nombre de la estrategia
        - activo: Símbolo del activo
        - timeframe: Timeframe a usar
        - fecha_inicio: Fecha de inicio (YYYY-MM-DD)
        - fecha_fin: Fecha de fin (YYYY-MM-DD)
        - parametros: Parámetros de la estrategia (opcional)
        
        Returns:
            Resultados del backtest con métricas
        """
        # Validar request
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
        
        # TODO: Implementar motor de backtest real (Fase 2)
        # Por ahora retornar resultado mock
        return {
            "status": "completed",
            "estrategia": request["estrategia"],
            "activo": request["activo"],
            "timeframe": request["timeframe"],
            "fecha_inicio": request["fecha_inicio"],
            "fecha_fin": request["fecha_fin"],
            "metricas": {
                "total_operaciones": 0,
                "ganadoras": 0,
                "perdedoras": 0,
                "winrate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "pnl_total": 0.0
            },
            "mensaje": "Backtest engine en implementación (Fase 2)"
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
