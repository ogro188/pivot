# -*- coding: utf-8 -*-
"""Utilidades ntfy: config por activo, envío de mensajes y prueba de conexión."""
import json
import os
import requests
from datetime import datetime
from typing import Dict, Tuple

DEFAULT_SERVER = "https://ntfy.sh"


def cargar_config_activo(simbolo: str) -> Dict[str, str]:
    """Config ntfy del activo: prioriza activos/{simbolo}.json -> data/ntfy_config.json."""
    ntfy: Dict[str, str] = {}
    path_json = f"activos/{simbolo.lower()}.json"
    if os.path.exists(path_json):
        try:
            with open(path_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            ntfy = data.get("ntfy") or {}
        except Exception:
            ntfy = {}
    if not ntfy.get("topic"):
        try:
            with open("data/ntfy_config.json", "r", encoding="utf-8") as f:
                g = json.load(f)
            ntfy = {"topic": g.get("topic", ""), "server": g.get("server", DEFAULT_SERVER)}
        except Exception:
            ntfy = {}
    if not ntfy.get("server"):
        ntfy["server"] = DEFAULT_SERVER
    return ntfy


def guardar_config_activo(simbolo: str, topic: str, server: str) -> None:
    """Persiste la config ntfy del activo en activos/{simbolo}.json."""
    path_json = f"activos/{simbolo.lower()}.json"
    data: Dict = {}
    if os.path.exists(path_json):
        try:
            with open(path_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data["ntfy"] = {"topic": topic, "server": server or DEFAULT_SERVER}
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def enviar(simbolo: str, text: str, config: Dict[str, str] | None = None) -> Tuple[bool, str]:
    """Envía un mensaje ntfy para el activo. Devuelve (ok, detalle)."""
    cfg = config or cargar_config_activo(simbolo)
    topic = cfg.get("topic", "")
    if not topic:
        return False, "Sin topic ntfy configurado"
    server = cfg.get("server", DEFAULT_SERVER).rstrip("/")
    url = f"{server}/{topic}"
    try:
        resp = requests.post(url, data=text.encode("utf-8"), headers={"Content-Type": "text/plain"}, timeout=5)
        if resp.status_code in (200, 201):
            return True, f"OK (HTTP {resp.status_code})"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def mensaje_prueba(simbolo: str) -> str:
    return (
        "🔧 TEST — PIVOT Terminal\n"
        f"Activo: {simbolo}\n"
        "Conexión ntfy correcta.\n"
        f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
