"""Endpoints REST."""
import os
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from kernel.storage import Storage
from kernel.contrato import ActivoInfo
from kernel.runtime import MultiActivo, ActivoRuntime
from kernel.backtest import Backtest
from kernel.feeds.csv import CSVFeed
from kernel.feeds.deriv import DerivFeed
from kernel.alertas import Alertador
from estrategias.registro import RegistroEstrategias

router = APIRouter()
storage = Storage()
multi = MultiActivo()
registro = RegistroEstrategias()

activos_config: dict[str, ActivoInfo] = {}
jobs: dict[str, dict] = {}

# Alertador global (se configura vía /config más adelante)
alertador: Alertador | None = None


def _load_activos():
    path = os.path.join(os.path.dirname(__file__), "../../activos")
    if not os.path.isdir(path):
        return
    for fn in os.listdir(path):
        if fn.endswith(".json") and not fn.endswith(".secrets.json"):
            with open(os.path.join(path, fn)) as f:
                data = json.load(f)
                activos_config[data["simbolo"]] = ActivoInfo(**data)

_load_activos()


class AssetDTO(BaseModel):
    simbolo: str
    nombre: str
    running: bool
    connected: bool
    price: float
    session: str
    kill_zone: str
    strategies_active: int
    signals_today: int


class SignalDTO(BaseModel):
    id: int
    ts: int
    asset: str
    estrategia: str
    etiqueta: str
    direccion: int
    precio: float
    expiracion_velas: int
    confianza: list
    objetivo: float | None = None
    invalidacion: float | None = None
    narrativa: str
    estado: str


class BacktestRequestDTO(BaseModel):
    asset: str
    estrategia: str
    desde: str
    hasta: str
    params: dict | None = None


class BacktestResultDTO(BaseModel):
    job_id: str
    estado: str
    n_senales: int
    winrate: float
    profit_factor: float
    drawdown_max: float
    sharpe: float
    equity: list
    error: str | None = None


class ConfigNtfyDTO(BaseModel):
    topic: str
    server: str = "https://ntfy.sh"


@router.get("/assets", response_model=list[AssetDTO])
def list_assets():
    result = []
    for sim, info in activos_config.items():
        rt = multi.runtimes.get(sim)
        running = rt is not None and rt.is_alive()
        price = 0.0
        session = "OUT"
        kill_zone = "NONE"
        if rt:
            price = rt.feed._velas.get(info.timeframes[0], {}).iloc[-1]["close"] if len(rt.feed._velas.get(info.timeframes[0], {})) > 0 else 0.0
            session = rt.tiempo.get_session(datetime.utcnow())
            kill_zone = rt.tiempo.get_kill_zone(datetime.utcnow())
        result.append(AssetDTO(
            simbolo=sim, nombre=info.nombre, running=running,
            connected=rt.fuente.conectado if rt else False,
            price=price, session=session, kill_zone=kill_zone,
            strategies_active=0, signals_today=0
        ))
    return result


@router.get("/assets/{simbolo}")
def get_asset(simbolo: str):
    if simbolo not in activos_config:
        raise HTTPException(404, "Activo no encontrado")
    return activos_config[simbolo]


@router.post("/assets/{simbolo}/start")
def start_asset(simbolo: str):
    if simbolo not in activos_config:
        raise HTTPException(404, "Activo no encontrado")
    info = activos_config[simbolo]
    estrategias = []
    for nombre in ["dummy", "ema_cross"]:
        try:
            e = registro.fabricar(nombre)
            e.setup({}, info)
            estrategias.append(e)
        except Exception:
            pass
    fuente = DerivFeed(info.fuente_config.get("instrumento", simbolo))
    from kernel.api.ws import ws_queue
    rt = ActivoRuntime(info, fuente, estrategias, storage, ws_queue, alertador)
    multi.add(rt)
    return {"ok": True}


@router.post("/assets/{simbolo}/stop")
def stop_asset(simbolo: str):
    multi.stop(simbolo)
    return {"ok": True}


@router.get("/assets/{simbolo}/history")
def get_history(simbolo: str, tf: str = Query("M15"), count: int = Query(200)):
    rt = multi.runtimes.get(simbolo)
    if not rt:
        raise HTTPException(404, "Activo no está corriendo")
    return rt.get_history(tf, count)


@router.get("/assets/{simbolo}/signals")
def get_signals(simbolo: str, limit: int = 50, estado: str | None = None):
    return storage.query_signals(asset=simbolo, limit=limit, estado=estado)


@router.get("/assets/{simbolo}/consola")
def get_consola(simbolo: str, limit: int = 200, level: str | None = None):
    return storage.query_logs(asset=simbolo, limit=limit, level=level)


@router.get("/strategies")
def list_strategies():
    return registro.listar()


@router.post("/assets/{simbolo}/strategies/{nombre}/enable")
def enable_strategy(simbolo: str, nombre: str):
    return {"ok": True}


@router.post("/assets/{simbolo}/strategies/{nombre}/disable")
def disable_strategy(simbolo: str, nombre: str):
    return {"ok": True}


@router.get("/assets/{simbolo}/strategies/{nombre}/params")
def get_params(simbolo: str, nombre: str):
    e = registro.fabricar(nombre)
    return e.parametros


@router.post("/assets/{simbolo}/strategies/{nombre}/params")
def set_params(simbolo: str, nombre: str, body: dict):
    return {"ok": True}


@router.post("/backtest")
def run_backtest(req: BacktestRequestDTO):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"estado": "running", "result": None, "error": None}
    def _run():
        try:
            info = activos_config[req.asset]
            e = registro.fabricar(req.estrategia)
            e.setup(req.params or {}, info)
            csv_path = os.path.join("data", f"{req.asset}.csv")
            fuente = CSVFeed(csv_path)
            desde = datetime.fromisoformat(req.desde)
            hasta = datetime.fromisoformat(req.hasta)
            bt = Backtest(info, e, fuente, desde, hasta)
            res = bt.run()
            jobs[job_id]["estado"] = "completado"
            jobs[job_id]["result"] = {
                "job_id": job_id,
                "estado": "completado",
                "n_senales": res.n_senales,
                "winrate": res.winrate,
                "profit_factor": res.profit_factor,
                "drawdown_max": res.drawdown_max,
                "sharpe": res.sharpe,
                "equity": [[int(t.timestamp()*1000), v] for t, v in res.equity]
            }
        except Exception as ex:
            jobs[job_id]["estado"] = "error"
            jobs[job_id]["error"] = str(ex)
    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.get("/backtest/{job_id}", response_model=BacktestResultDTO)
def get_backtest(job_id: str):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "Job no encontrado")
    res = j.get("result")
    return BacktestResultDTO(
        job_id=job_id,
        estado=j["estado"],
        n_senales=res["n_senales"] if res else 0,
        winrate=res["winrate"] if res else 0.0,
        profit_factor=res["profit_factor"] if res else 0.0,
        drawdown_max=res["drawdown_max"] if res else 0.0,
        sharpe=res["sharpe"] if res else 0.0,
        equity=res["equity"] if res else [],
        error=j.get("error")
    )


@router.post("/config/ntfy")
def config_ntfy(cfg: ConfigNtfyDTO):
    global alertador
    alertador = Alertador(cfg.topic, cfg.server)
    return {"ok": True, "topic": cfg.topic}


@router.get("/system/status")
def system_status():
    return {"status": "ok", "activos": len(activos_config), "running": len(multi.runtimes)}
