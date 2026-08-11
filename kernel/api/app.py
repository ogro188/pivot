# -*- coding: utf-8 -*-
"""API FastAPI para PIVOT Trading System."""
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    if os.path.exists(_ENV_PATH):
        load_dotenv(_ENV_PATH)
    else:
        load_dotenv()
except Exception:
    pass

# Agregar el root del workspace al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from kernel.contrato import Estrategia, ActivoInfo
from estrategias.registro import RegistroEstrategias
from kernel.api.websocket_server import websocket_endpoint, manager

logger = logging.getLogger(__name__)

# =============================================================================
# Estado del runtime simulado (in-memory)
# =============================================================================
_RUNNING: Dict[str, bool] = {}
_RUNTIME_TASKS: Dict[str, asyncio.Task] = {}
_PRICES: Dict[str, float] = {}
_DERIV_RUNTIME: Any = None
_DERIV_STARTED: bool = False


def _decimales_desde_punto(punto: float) -> int:
    s = f"{punto:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def _session_actual() -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    h = now.hour
    if h < 7:
        return "ASIA"
    if h < 13:
        return "LONDON"
    if h < 15:
        return "NY_OPEN"
    if h < 16:
        return "LONDON_CLOSE"
    if h < 21:
        return "NY"
    return "OUT"


def _kill_zone_actual() -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    h, m = now.hour, now.minute
    if h in (7, 8):
        return "LONDON_OPEN_KILL"
    if h == 13 or (h == 14 and m <= 30):
        return "NY_OPEN_KILL"
    if 13 <= h < 15:
        return "LONDON_NY_OVERLAP"
    return "NONE"


def _iso_a_ms(value) -> int:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def _serialize_senal(s) -> Dict[str, Any]:
    """Convierte una Señal del core al DTO que consume el frontend."""
    ts = int(s.tiempo.timestamp() * 1000) if s.tiempo else int(datetime.now(timezone.utc).timestamp() * 1000)
    conf = s.confianza
    if isinstance(conf, (tuple, list)) and len(conf) >= 2:
        conf_min, conf_max = float(conf[0]), float(conf[1])
    else:
        conf_min = conf_max = float(conf or 0)
    detectores = []
    if isinstance(s.contexto, dict):
        detectores = s.contexto.get("detectores", []) or []
    return {
        "id": s.id_señal or f"sig_{ts}",
        "ts": ts,
        "asset": s.simbolo,
        "estrategia": s.estrategia,
        "etiqueta": s.etiqueta,
        "direccion": int(s.direccion),
        "precio": float(s.precio),
        "expiracion_velas": int(s.expiracion_velas),
        "confianza": [conf_min, conf_max],
        "objetivo": float(s.take_profit) if s.take_profit else None,
        "invalidacion": float(s.stop_loss) if s.stop_loss else None,
        "narrativa": s.narrativa,
        "estado": "activa",
        "detectores": detectores,
    }


def _df_a_velas(df, n: int) -> List[Dict[str, Any]]:
    out = []
    for ts, row in df.tail(n).iterrows():
        out.append({
            "time": int(ts.timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0) or 0),
        })
    return out


def _cargar_velas_deriv(simbolo: str, tf: str, count: int) -> Optional[List[Dict[str, Any]]]:
    """Carga velas reales desde el buffer del runtime Deriv (si está conectado).

    Incluye la vela formándose para que el chart refleje el precio en vivo.
    Devuelve None si el activo no tiene stream Deriv activo.
    """
    import pandas as pd
    from kernel.feeds.csv_resample import resamplear_ohlc

    stream = _DERIV_RUNTIME.streams.get(simbolo) if _DERIV_RUNTIME else None
    if not stream or not stream.connected:
        return None

    rows = list(stream.buffer)
    if stream._current and (not rows or stream._current["time"] > rows[-1]["time"]):
        rows = rows + [stream._current]
    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    if tf.upper() != "M15":
        try:
            df = resamplear_ohlc(df, tf.upper())
        except Exception:
            return None
    return _df_a_velas(df, count)


def _cargar_velas(simbolo: str, tf: str, count: int) -> List[Dict[str, Any]]:
    """Carga velas OHLC para el chart. Usa el CSV del timeframe o resamplea desde M15."""
    from kernel.feeds.csv import CSVFeed
    from kernel.feeds.csv_resample import resamplear_ohlc

    path_m15 = f"data/{simbolo.lower()}_m15.csv"
    if not os.path.exists(path_m15):
        raise HTTPException(status_code=404, detail=f"No hay datos históricos para {simbolo}")

    if tf.upper() == "M15":
        feed = CSVFeed(path=path_m15, timeframe="M15", symbol=simbolo.upper())
        return _df_a_velas(feed.df, count)

    path_tf = f"data/{simbolo.lower()}_{tf.lower()}.csv"
    if os.path.exists(path_tf):
        feed = CSVFeed(path=path_tf, timeframe=tf.upper(), symbol=simbolo.upper())
        return _df_a_velas(feed.df, count)

    feed_m15 = CSVFeed(path=path_m15, timeframe="M15", symbol=simbolo.upper())
    df = resamplear_ohlc(feed_m15.df, tf.upper())
    return _df_a_velas(df, count)


async def _contar_senales_hoy(simbolo: str) -> int:
    try:
        from kernel.storage import get_database
        db = get_database()
        db.initialize()
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = await db.fetchall_async(
            "SELECT COUNT(*) AS n FROM senales_core WHERE symbol=? AND substr(entry_time,1,10)=?",
            (simbolo, hoy),
        )
        return int(rows[0]["n"]) if rows else 0
    except Exception:
        return 0


async def _replay_asset(simbolo: str):
    """Replay simulado en vivo: recorre el CSV M15 barra a barra, emite ticks por
    WebSocket y emite/persiste las señales del motor PIVOT."""
    from kernel.activos_loader import cargar_activo
    from kernel.feeds.csv import CSVFeed
    from kernel.backtest import BacktestEngine
    from kernel.storage import get_database

    db = get_database()
    db.initialize()

    async def _log(nivel: str, mensaje: str):
        try:
            await db.log_strategy(estrategia="PIVOT", nivel=nivel, simbolo=simbolo, mensaje=mensaje)
            await manager.send_console_log({
                "ts": datetime.utcnow().isoformat(),
                "t": datetime.utcnow().strftime("%H:%M:%S"),
                "level": nivel,
                "cat": "PIVOT",
                "msg": mensaje,
            })
        except Exception:
            pass

    try:
        activo = cargar_activo(simbolo)
        feed = CSVFeed(path=f"data/{simbolo.lower()}_m15.csv", timeframe="M15", symbol=activo.simbolo)

        señales = []
        try:
            registro = RegistroEstrategias()
            estrategia = registro.fabricar("PIVOT")
            engine = BacktestEngine(estrategia=estrategia, activo=activo)
            engine.ejecutar(feeds={"M15": feed})
            señales = list(getattr(engine, "señales_generadas", []))
        except Exception as e:
            logger.error(f"Error precomputando señales para {simbolo}: {e}")

        signals_payload = [_serialize_senal(s) for s in señales]
        signals_sent = set()

        await _log("INFO", f"Runtime {activo.simbolo} iniciado (replay {len(feed.df)} velas)")

        for bar in feed.iter_barras():
            if not _RUNNING.get(activo.simbolo, False):
                break

            price = float(bar["close"])
            _PRICES[activo.simbolo] = price

            await manager.broadcast({
                "type": "tick",
                "asset": activo.simbolo,
                "price": price,
                "bid": price,
                "ask": price,
                "timestamp": datetime.utcnow().isoformat(),
            })

            ts_bar = int(bar["timestamp"].timestamp() * 1000)
            for sig in signals_payload:
                key = sig.get("id")
                if key in signals_sent or sig.get("ts", 0) > ts_bar:
                    continue
                signals_sent.add(key)
                try:
                    entry_time = datetime.fromtimestamp(sig["ts"] / 1000, tz=timezone.utc)
                    await db.guardar_senal_core(
                        signal_id=str(key),
                        entry_time=entry_time,
                        symbol=sig["asset"],
                        direction=sig["direccion"],
                        entry_price=sig["precio"],
                        detector=",".join(sig.get("detectores", []) or ["D0"]),
                        tipo=sig["etiqueta"],
                        hipotesis_prob_min=sig["confianza"][0],
                        hipotesis_prob_max=sig["confianza"][1],
                        hipotesis_expiry_velas=sig["expiracion_velas"],
                        conviccion=sig["confianza"][1] / 100.0,
                        regimen_volatilidad="NORMAL",
                    )
                except Exception as e:
                    logger.error(f"Error persistiendo señal: {e}")
                await manager.broadcast({
                    "type": "signal",
                    "data": sig,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            await asyncio.sleep(0.15)

        await _log("INFO", f"Runtime {activo.simbolo} detenido tras replay")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Replay de {simbolo} terminó con error: {e}")
    finally:
        _RUNNING[simbolo] = False


async def _iniciar_deriv():
    """Conecta los streams de Deriv para todos los activos de fuente deriv."""
    global _DERIV_RUNTIME, _DERIV_STARTED
    if _DERIV_STARTED:
        return _DERIV_RUNTIME
    _DERIV_STARTED = True
    try:
        from kernel.deriv_runtime import DerivRuntime
        from kernel.activos_loader import listar_activos_disponibles, cargar_activo
        from kernel.storage import get_database

        db = get_database()
        db.initialize()

        info = {}
        for simbolo in listar_activos_disponibles():
            path_json = f"activos/{simbolo.lower()}.json"
            if not os.path.exists(path_json):
                continue
            try:
                with open(path_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if (data.get("fuente_tipo") or "").lower() != "deriv":
                continue
            try:
                info[simbolo] = cargar_activo(simbolo)
            except ValueError:
                continue

        if not info:
            logger.info("Sin activos de fuente deriv, runtime Deriv no arranca")
            return None

        _DERIV_RUNTIME = DerivRuntime(activos_info=info, serialize_senal=_serialize_senal, db=db)
        await _DERIV_RUNTIME.start()
        logger.info(f"Deriv runtime iniciado para: {list(info.keys())}")
        return _DERIV_RUNTIME
    except Exception as e:
        logger.error(f"Error iniciando runtime Deriv: {e}")
        return None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await _iniciar_deriv()
    yield
    if _DERIV_RUNTIME:
        try:
            await _DERIV_RUNTIME.stop()
        except Exception:
            pass


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI."""
    app = FastAPI(
        title="PIVOT Trading API",
        description="Sistema de ejecución y backtesting de estrategias de trading",
        version="2.0.0",
        lifespan=_lifespan,
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
                "/api/health",
            ],
        }

    @app.get("/api/health")
    async def health_check():
        """Verifica el estado del sistema."""
        deriv = None
        if _DERIV_RUNTIME:
            deriv = _DERIV_RUNTIME.status()
        return {
            "status": "healthy",
            "version": "2.0.0",
            "strategies_loaded": len(registro.listar()),
            "deriv_connected": bool(deriv and deriv.get("connected")),
            "deriv": deriv,
        }

    @app.get("/api/deriv/status")
    async def deriv_status() -> Dict[str, Any]:
        """Estado detallado de la conexión a Deriv por activo."""
        if not _DERIV_RUNTIME:
            return {"connected": False, "started": False, "assets": {}}
        status = _DERIV_RUNTIME.status()
        status["started"] = True
        return status

    @app.get("/api/assets")
    async def get_assets() -> List[Dict[str, Any]]:
        """
        Obtiene la lista de activos disponibles con el estado en tiempo real.
        """
        from kernel.activos_loader import listar_activos_disponibles, cargar_activo
        from kernel.feeds.csv import CSVFeed

        simbolos = listar_activos_disponibles()
        resultado = []

        for simbolo in simbolos:
            try:
                activo = cargar_activo(simbolo)
            except ValueError as e:
                logger.warning(f"Activo {simbolo} inválido: {e}")
                continue

            extra = {}
            path_json = f"activos/{simbolo.lower()}.json"
            if os.path.exists(path_json):
                try:
                    with open(path_json, "r", encoding="utf-8") as f:
                        extra = json.load(f)
                except Exception:
                    extra = {}

            running = _RUNNING.get(activo.simbolo, False)

            # Estado de conexión Deriv del activo (si aplica)
            deriv_stream = None
            if _DERIV_RUNTIME:
                deriv_stream = _DERIV_RUNTIME.streams.get(activo.simbolo)
            deriv_connected = bool(deriv_stream and deriv_stream.connected)
            fuente = extra.get("fuente_tipo", "csv")
            if fuente == "deriv" and not deriv_stream:
                fuente = "csv"  # el activo es deriv pero no hay stream activo

            precio = _PRICES.get(activo.simbolo)
            if deriv_stream and deriv_stream.price is not None:
                price = deriv_stream.price
            elif price is None:
                try:
                    feed = CSVFeed(path=f"data/{simbolo.lower()}_m15.csv", timeframe="M15", symbol=activo.simbolo)
                    price = float(feed.df["close"].iloc[-1])
                except Exception:
                    price = None

            from kernel.ntfy import cargar_config_activo
            ntfy_cfg = cargar_config_activo(activo.simbolo)

            resultado.append({
                "simbolo": activo.simbolo,
                "nombre": extra.get("nombre", activo.simbolo),
                "decimales": extra.get("decimales", _decimales_desde_punto(activo.punto)),
                "punto": activo.punto,
                "tick_size": activo.tick_size,
                "contract_size": activo.contract_size,
                "activo": True,
                "fuente": fuente,
                "running": running,
                "connected": deriv_connected or running,
                "deriv_connected": deriv_connected,
                "price": price,
                "session": _session_actual(),
                "kill_zone": _kill_zone_actual(),
                "strategies_active": len(registro.listar()),
                "signals_today": await _contar_senales_hoy(activo.simbolo),
                "ntfy_topic": ntfy_cfg.get("topic", ""),
                "ntfy_server": ntfy_cfg.get("server", ""),
            })

        return resultado

    @app.get("/api/strategies")
    async def get_strategies() -> List[Dict[str, Any]]:
        """Obtiene la lista de estrategias disponibles."""
        try:
            return registro.listar()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error cargando estrategias: {str(e)}")

    @app.get("/api/strategies/{nombre}")
    async def get_strategy(nombre: str) -> Dict[str, Any]:
        """Obtiene los detalles de una estrategia específica."""
        for estr in registro.listar():
            if estr["nombre"] == nombre:
                return estr
        raise HTTPException(status_code=404, detail=f"Estrategia '{nombre}' no encontrada")

    @app.get("/api/assets/{simbolo}/history")
    async def get_asset_history(simbolo: str, tf: str = "M15", count: int = 200) -> List[Dict[str, Any]]:
        """Obtiene velas históricas para el chart. Prioriza el stream real de Deriv."""
        deriv = _cargar_velas_deriv(simbolo, tf, count)
        if deriv is not None:
            return deriv
        return _cargar_velas(simbolo, tf, count)

    @app.get("/api/assets/{simbolo}/signals")
    async def get_asset_signals(simbolo: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene las señales registradas de un activo."""
        from kernel.storage import get_database
        db = get_database()
        db.initialize()
        rows = await db.fetchall_async(
            "SELECT * FROM senales_core WHERE symbol=? ORDER BY entry_time DESC LIMIT ?",
            (simbolo.upper(), limit),
        )
        return [{
            "id": r["signal_id"],
            "ts": _iso_a_ms(r["entry_time"]),
            "asset": r["symbol"],
            "estrategia": "PIVOT",
            "etiqueta": r["tipo"] or "",
            "direccion": int(r["direction"] or 0),
            "precio": r["entry_price"],
            "expiracion_velas": int(r["hipotesis_expiry_velas"] or 0),
            "confianza": [float(r["hipotesis_prob_min"] or 0), float(r["hipotesis_prob_max"] or 0)],
            "objetivo": None,
            "invalidacion": None,
            "narrativa": f"Detector: {r['detector'] or 'D0'}",
            "estado": "activa",
        } for r in rows]

    @app.get("/api/assets/{simbolo}/consola")
    async def get_asset_consola(simbolo: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Obtiene los logs de consola de un activo."""
        from kernel.storage import get_database
        db = get_database()
        db.initialize()
        rows = await db.fetchall_async(
            "SELECT * FROM strategy_logs WHERE simbolo=? ORDER BY id DESC LIMIT ?",
            (simbolo.upper(), limit),
        )
        return [{
            "ts": r["timestamp"],
            "t": r["timestamp"],
            "level": r["nivel"] or "INFO",
            "cat": r["estrategia"] or "PIVOT",
            "msg": r["mensaje"],
        } for r in rows]

    @app.post("/api/assets/{simbolo}/start")
    async def start_asset(simbolo: str) -> Dict[str, Any]:
        """Inicia el runtime simulado (replay CSV + WebSocket) de un activo."""
        from kernel.activos_loader import cargar_activo
        try:
            activo = cargar_activo(simbolo)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if _RUNNING.get(activo.simbolo, False):
            return {"status": "ok", "simbolo": activo.simbolo, "running": True}

        data_path = f"data/{activo.simbolo.lower()}_m15.csv"
        if not os.path.exists(data_path):
            raise HTTPException(
                status_code=404,
                detail=f"No hay datos históricos para {activo.simbolo} en {data_path}",
            )

        _RUNNING[activo.simbolo] = True
        task = asyncio.create_task(_replay_asset(activo.simbolo))
        _RUNTIME_TASKS[activo.simbolo] = task
        return {"status": "ok", "simbolo": activo.simbolo, "running": True}

    @app.post("/api/assets/{simbolo}/stop")
    async def stop_asset(simbolo: str) -> Dict[str, Any]:
        """Detiene el runtime simulado de un activo."""
        from kernel.activos_loader import cargar_activo
        try:
            activo = cargar_activo(simbolo)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        _RUNNING[activo.simbolo] = False
        task = _RUNTIME_TASKS.pop(activo.simbolo, None)
        if task:
            task.cancel()
        return {"status": "ok", "simbolo": activo.simbolo, "running": False}

    @app.get("/api/assets/{simbolo}/ntfy")
    async def get_asset_ntfy(simbolo: str) -> Dict[str, Any]:
        """Obtiene la configuración ntfy del activo (topic + server)."""
        from kernel.ntfy import cargar_config_activo
        return cargar_config_activo(simbolo)

    @app.post("/api/assets/{simbolo}/ntfy")
    async def save_asset_ntfy(simbolo: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Guarda la configuración ntfy del activo."""
        from kernel.ntfy import guardar_config_activo
        topic = request.get("topic", "")
        server = request.get("server", "https://ntfy.sh")
        guardar_config_activo(simbolo, topic, server)
        # Aplicar al detector v8 del stream live si está corriendo
        if _DERIV_RUNTIME:
            stream = _DERIV_RUNTIME.streams.get(simbolo)
            if stream and stream.engine:
                stream.engine.alertas.ntfy_topic = topic
                stream.engine.alertas.ntfy_server = server.rstrip("/")
        return {"status": "ok", "simbolo": simbolo, "topic": topic, "server": server}

    @app.post("/api/assets/{simbolo}/ntfy/test")
    async def test_asset_ntfy(simbolo: str) -> Dict[str, Any]:
        """Envía un mensaje de prueba ntfy para verificar la conexión."""
        from kernel.ntfy import enviar, mensaje_prueba, cargar_config_activo
        cfg = cargar_config_activo(simbolo)
        if not cfg.get("topic"):
            raise HTTPException(status_code=400, detail="No hay topic ntfy configurado para este activo")
        ok, detalle = await asyncio.to_thread(enviar, simbolo, mensaje_prueba(simbolo), cfg)
        return {"ok": ok, "simbolo": simbolo, "detail": detalle, "topic": cfg.get("topic"), "server": cfg.get("server")}

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
        - capital_inicial, riesgo_por_operacion, slippage_pips, comision_lote
        - parametros: Parámetros de la estrategia (opcional)
        """
        from kernel.backtest import BacktestEngine
        from kernel.feeds.csv import CSVFeed
        from kernel.activos_loader import cargar_activo
        from datetime import datetime as _dt

        required_fields = ["estrategia", "activo", "timeframe", "fecha_inicio", "fecha_fin"]
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Campo requerido faltante: {field}")

        estrategia_nombres = [e["nombre"] for e in registro.listar()]
        if request["estrategia"] not in estrategia_nombres:
            raise HTTPException(
                status_code=404,
                detail=f"Estrategia '{request['estrategia']}' no encontrada. Disponibles: {estrategia_nombres}",
            )

        try:
            activo = cargar_activo(request["activo"])
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        estrategia_instancia = registro.fabricar(request["estrategia"])

        data_path = f"data/{request['activo'].lower()}_{request['timeframe'].lower()}.csv"
        if not os.path.exists(data_path):
            raise HTTPException(
                status_code=404,
                detail=f"No hay datos históricos en {data_path}. Disponible: EURUSD M15 en data/eurusd_m15.csv",
            )

        try:
            fecha_inicio = _dt.strptime(request["fecha_inicio"], "%Y-%m-%d")
            fecha_fin = _dt.strptime(request["fecha_fin"], "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

        feed = CSVFeed(
            path=data_path,
            timeframe=request["timeframe"],
            symbol=activo.simbolo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )

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
            params_estrategia=request.get("parametros", {}),
        )

        equity_raw = getattr(resultado, "equity_curve", [])
        equity = [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in equity_raw[-100:]]

        return {
            "status": "completed",
            "estrategia": request["estrategia"],
            "activo": request["activo"],
            "timeframe": request["timeframe"],
            "fecha_inicio": request["fecha_inicio"],
            "fecha_fin": request["fecha_fin"],
            "n_senales": len(getattr(engine, "señales_generadas", [])),
            "capital_inicial": resultado.capital_inicial,
            "capital_final": resultado.capital_final,
            "equity": equity,
            **resultado.to_dict(),
        }

    @app.post("/api/config/ntfy")
    async def config_ntfy(request: Dict[str, Any]) -> Dict[str, Any]:
        """Guarda la configuración de notificaciones ntfy."""
        topic = request.get("topic", "")
        server = request.get("server", "https://ntfy.sh")
        try:
            Path("data/ntfy_config.json").write_text(
                json.dumps({"topic": topic, "server": server}), encoding="utf-8"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo guardar la configuración: {e}")
        return {"status": "ok", "topic": topic, "server": server}

    @app.get("/api/config")
    async def get_config() -> Dict[str, Any]:
        """Obtiene la configuración global del sistema."""
        return {
            "version": "2.0.0",
            "timeframes_soportados": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
            "sessions": ["ASIA", "LONDON", "NEWYORK"],
            "kill_zones": ["KZ1", "KZ2", "KZ3"],
            "detectores": ["D0", "D1", "D2", "D3", "D4", "D5"],
        }

    return app


# App instance para uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
