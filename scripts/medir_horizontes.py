# -*- coding: utf-8 -*-
"""Mide el acierto de las señales según el minuto de entrada y el horizonte.

Responde dos preguntas que no dependen de ticks, solo de velas M1 cerradas:

- ¿El momento de entrada dentro de la ventana del operador (0 a 8 minutos
  después de la emisión) cambia la probabilidad de acierto?
- ¿Los horizontes largos que el sistema dice predecir (M15/M30) tienen
  ventaja, o el acierto se agota en los primeros minutos?

Reglas de medición:

- El reloj se ancla en ``created_at`` (emisión real), nunca en ``entry_time``
  (apertura de la vela, que llega ~15 min tarde).
- La entrada es el cierre de la última vela M1 ya cerrada en ese instante.
- La salida es el cierre de la vela M1 que termina ``h`` minutos después.
- Se informa siempre el par contra el control invertido: si invertir no
  empeora, no hay información direccional.
- El filtro de tendencia M15 usa velas etiquetadas por su **cierre**
  (``index + 15 min``). Etiquetarlas por apertura deja leer la vela en curso
  ya completa, es decir, el futuro.

Uso:
    python scripts/medir_horizontes.py \\
        --senales senales.json \\
        --m1 eurusd-otc=data/iq_public/export/eurusd-otc_m1.csv \\
        --m1 xauusd-otc=data/iq_public/export/xauusd-otc_m1.csv
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

HORIZONTES = (1, 2, 3, 5, 10, 15, 20, 30)
OFFSETS = tuple(range(0, 9))
VELA_M1 = pd.Timedelta(minutes=1)


def _normalizar(simbolo: str) -> str:
    return str(simbolo or "").upper().replace("_", "-").replace(" ", "")


def _clave(simbolo: str) -> str:
    """Clave laxa: ``EURUSD-OTC`` y ``eurusd`` caen en la misma familia."""
    return _normalizar(simbolo).replace("-OTC", "")


def cargar_velas(rutas: Dict[str, Path]) -> Dict[str, pd.Series]:
    """Devuelve ``{clave: serie de cierres indexada por apertura UTC}``."""
    series: Dict[str, pd.Series] = {}
    for simbolo, ruta in rutas.items():
        df = pd.read_csv(ruta)
        cols = {c.lower().strip(): c for c in df.columns}
        if "timestamp" in cols:
            ts = pd.to_datetime(df[cols["timestamp"]], utc=True, errors="coerce")
        elif "open_time" in cols:
            ts = pd.to_datetime(df[cols["open_time"]], unit="s", utc=True, errors="coerce")
        else:
            raise SystemExit(f"{ruta}: falta columna timestamp/open_time")
        close = pd.to_numeric(df[cols["close"]], errors="coerce")
        velas = pd.DataFrame({"ts": ts, "close": close}).dropna()
        velas = velas.drop_duplicates("ts").set_index("ts").sort_index()["close"]
        series[_clave(simbolo)] = velas
    return series


def cargar_senales(ruta: Optional[Path], db: Optional[Path]) -> List[dict]:
    if ruta:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            datos = datos.get("senales", datos.get("signals", []))
        return list(datos)
    if db:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "select symbol, direction, entry_price, detector, created_at "
            "from senales_core where created_at is not null"
        ).fetchall()
        return [dict(f) for f in filas]
    raise SystemExit("falta --senales o --db")


def _ts(valor) -> Optional[pd.Timestamp]:
    if valor in (None, ""):
        return None
    try:
        t = pd.to_datetime(valor, utc=True)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(t) else t


def preparar(senales: Iterable[dict], velas: Dict[str, pd.Series]) -> pd.DataFrame:
    filas = []
    for s in senales:
        clave = _clave(s.get("symbol") or s.get("activo") or "")
        serie = velas.get(clave)
        if serie is None or serie.empty:
            continue
        emision = _ts(s.get("created_at") or s.get("emitida"))
        direccion = s.get("direction") or s.get("direccion")
        try:
            direccion = int(np.sign(float(direccion)))
        except (TypeError, ValueError):
            continue
        if emision is None or direccion == 0:
            continue
        filas.append(
            {
                "clave": clave,
                "emision": emision,
                "direccion": direccion,
                "detector": s.get("detector") or "?",
                "precio_senal": float(s.get("entry_price") or np.nan),
            }
        )
    return pd.DataFrame(filas)


def _sma20_m15(serie: pd.Series) -> pd.Series:
    m15 = serie.resample("15min").last().dropna()
    # Etiqueta = cierre de la vela. Sin este desplazamiento el asof() devuelve
    # la vela en curso ya completa y el filtro ve el futuro.
    m15.index = m15.index + pd.Timedelta(minutes=15)
    return m15.rolling(20).mean()


def medir(
    senales: pd.DataFrame,
    velas: Dict[str, pd.Series],
    offsets: Sequence[int],
    horizontes: Sequence[int],
) -> pd.DataFrame:
    smas = {k: _sma20_m15(v) for k, v in velas.items()}
    registros = []
    for clave, grupo in senales.groupby("clave"):
        serie = velas[clave]
        cierres = serie.to_numpy(dtype=float)
        aperturas = serie.index
        # índice del cierre de cada vela, para buscar "última vela cerrada"
        cierres_ts = aperturas + VELA_M1
        sma = smas[clave]
        sma_idx = sma.index
        sma_val = sma.to_numpy(dtype=float)
        for fila in grupo.itertuples(index=False):
            for k in offsets:
                instante = fila.emision + pd.Timedelta(minutes=int(k))
                i = int(np.searchsorted(cierres_ts.values, instante.to_datetime64(), side="right") - 1)
                if i < 0 or i + max(horizontes) >= len(cierres):
                    continue
                entrada = cierres[i]
                if not math.isfinite(entrada) or entrada <= 0:
                    continue
                # filtro de tendencia: última vela M15 cerrada antes del instante
                alineado = None
                if len(sma_idx):
                    j = int(np.searchsorted(sma_idx.values, instante.to_datetime64(), side="right") - 1)
                    if j >= 0 and math.isfinite(sma_val[j]):
                        ref = cierres[np.searchsorted(cierres_ts.values, sma_idx[j].to_datetime64(), side="right") - 1]
                        alineado = bool(np.sign(ref - sma_val[j]) == fila.direccion)
                registro = {
                    "clave": clave,
                    "detector": fila.detector,
                    "offset": int(k),
                    "entrada": entrada,
                    "direccion": fila.direccion,
                    "alineado": alineado,
                }
                for h in horizontes:
                    salida = cierres[i + h]
                    movimiento = (salida - entrada) * fila.direccion
                    registro[f"mov_{h}"] = movimiento
                registros.append(registro)
    return pd.DataFrame(registros)


def wilson(aciertos: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = aciertos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - medio), min(1.0, centro + medio))


def _tasa(serie: pd.Series, horizonte: int, invertido: bool = False) -> str:
    mov = serie[f"mov_{horizonte}"].to_numpy(dtype=float)
    mov = mov[np.isfinite(mov)]
    if mov.size == 0:
        return "     -    "
    direccion = -1 if invertido else 1
    aciertos = int(np.sum(mov * direccion > 0))
    empates = int(np.sum(mov == 0))
    n = mov.size - empates
    if n == 0:
        return "     -    "
    tasa = aciertos / n
    lo, hi = wilson(aciertos, n)
    return f"{tasa * 100:4.1f}%[{lo * 100:2.0f},{hi * 100:2.0f}]"


def tabla(datos: pd.DataFrame, horizontes: Sequence[int], titulo: str) -> None:
    print(f"\n### {titulo}  (n={len(datos)})")
    if datos.empty:
        print("  sin casos")
        return
    cabecera = "  offset  n     " + "".join(f"+{h}m{'':<10}" for h in horizontes)
    print(cabecera)
    for k, grupo in datos.groupby("offset"):
        celdas = "".join(f"{_tasa(grupo, h):<14}" for h in horizontes)
        print(f"  +{k:<6} {len(grupo):<6}{celdas}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--senales", type=Path, help="JSON con las señales exportadas")
    ap.add_argument("--db", type=Path, help="sqlite con tabla senales_core")
    ap.add_argument("--m1", action="append", default=[], metavar="SIMBOLO=RUTA",
                    help="CSV M1 por activo (repetible)")
    ap.add_argument("--horizontes", default=",".join(map(str, HORIZONTES)))
    ap.add_argument("--offsets", default=",".join(map(str, OFFSETS)))
    args = ap.parse_args()

    rutas: Dict[str, Path] = {}
    for item in args.m1:
        if "=" not in item:
            raise SystemExit(f"--m1 espera SIMBOLO=RUTA, recibí {item!r}")
        simbolo, ruta = item.split("=", 1)
        rutas[simbolo] = Path(ruta)
    if not rutas:
        raise SystemExit("falta al menos un --m1")

    horizontes = [int(x) for x in args.horizontes.split(",") if x.strip()]
    offsets = [int(x) for x in args.offsets.split(",") if x.strip()]

    velas = cargar_velas(rutas)
    senales = preparar(cargar_senales(args.senales, args.db), velas)
    if senales.empty:
        raise SystemExit("ninguna señal coincide con las velas cargadas")

    datos = medir(senales, velas, offsets, horizontes)
    print(f"señales={len(senales)}  casos={len(datos)}  activos={sorted(velas)}")

    tabla(datos, horizontes, "con la alerta, todo el conjunto")
    for clave, grupo in datos.groupby("clave"):
        tabla(grupo, horizontes, f"con la alerta · {clave}")
    alineado = datos[datos["alineado"] == True]  # noqa: E712
    if not alineado.empty:
        tabla(alineado, horizontes, "con la alerta · tendencia M15 alineada")

    print("\n### control invertido (todo el conjunto)")
    for k, grupo in datos.groupby("offset"):
        celdas = "".join(f"{_tasa(grupo, h, invertido=True):<14}" for h in horizontes)
        print(f"  +{k:<6} {len(grupo):<6}{celdas}")

    print("\n### mejor offset por horizonte (con la alerta)")
    for h in horizontes:
        tasas = []
        for k, grupo in datos.groupby("offset"):
            mov = grupo[f"mov_{h}"].to_numpy(dtype=float)
            mov = mov[np.isfinite(mov)]
            n = int(np.sum(mov != 0))
            if n:
                tasas.append((float(np.sum(mov > 0)) / n, int(k), n))
        if not tasas:
            continue
        tasa, k, n = max(tasas)
        print(f"  +{h:>2}m  mejor offset +{k} min → {tasa * 100:.1f}% (n={n})")


if __name__ == "__main__":
    main()
