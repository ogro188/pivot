# -*- coding: utf-8 -*-
"""Mide con ticks si la reversión del minuto de emisión se captura a segundos.

``scripts/medir_horizontes.py`` encontró un único desvío real sobre 16.857
casos: en el minuto de emisión la alerta acierta ~47% (52,9% invertida), es
decir, el precio se mueve en contra de la alerta justo después de emitirse.
Ese efecto desaparece a los 2 minutos.

Este script comprueba si esos ~3 puntos existen a escala de segundos y si son
capturables: recorre el retardo de entrada (0 a 120 s después de la emisión) y
la duración de la operación (10 s a 5 min) usando los ticks reales guardados
por el colector, en lugar de velas M1.

Reglas:

- Reloj anclado en ``created_at`` (emisión), nunca en ``entry_time``.
- Entrada y salida son el último tick conocido en ese instante, con una
  tolerancia máxima de hueco (``--tolerancia``): si el colector estaba caído,
  el caso se descarta en vez de inventar precio.
- Precio usado: ``price`` (medio). El spread observado es de 0,1 pip en
  EURUSD-OTC y despreciable en XAUUSD-OTC.
- Se informa el par contra el control invertido y el intervalo de Wilson.
- La referencia de rentabilidad es el breakeven del bróker: 52,6% con payout
  del 90%, 55,6% con el 80%.

Resultado del 14 nov 2026 (1.664 señales completas, 80 celdas): ninguna celda
supera el breakeven. La mejor con la alerta es 52,0% y la mejor invertida es
54,6% (EURUSD, entrada +20 s y salida +10 s, IC [51,58]); el contraste de
permutación da p=0,11–0,19, es decir, el máximo esperable de 80 celdas de puro
ruido (media 52,6%, p95 53,8%). La reversión del minuto de emisión existe
(~48,5% con la alerta) pero es demasiado pequeña para pagar el payout.

Uso:
    python scripts/medir_ticks.py \\
        --ticks /opt/pivot/pivotradar_data/iq_public/iq_public.db \\
        --db /opt/pivot/pivotradar_data/eurusd-otc/pivot_core.db \\
        --db /opt/pivot/pivotradar_data/xauusd-otc/pivot_core.db
"""
from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

OFFSETS = (0, 10, 20, 30, 45, 60, 90, 120)
HORIZONTES = (10, 15, 20, 30, 45, 60, 90, 120, 180, 300)
BREAKEVEN = 52.63  # payout 90%


def _clave(simbolo: str) -> str:
    return str(simbolo or "").upper().replace("_", "-").replace(" ", "").replace("-OTC", "")


def cargar_senales(rutas: Iterable[Path]) -> List[dict]:
    filas: List[dict] = []
    for ruta in rutas:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            for f in con.execute(
                "select symbol, direction, created_at from senales_core "
                "where created_at is not null"
            ):
                filas.append(dict(f))
        finally:
            con.close()
    return filas


def cargar_ticks(ruta: Path, claves: Sequence[str]) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Devuelve ``{clave: (ts_epoch, precio)}`` ordenado por tiempo."""
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    salida: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    try:
        nombres = [
            r[0]
            for r in con.execute("select distinct provider_name from ticks")
            if _clave(r[0]) in claves
        ]
        for nombre in nombres:
            df = pd.read_sql_query(
                "select ts, price from ticks where provider_name = ? "
                "and price is not null and price > 0 order by ts",
                con,
                params=(nombre,),
            )
            salida[_clave(nombre)] = (
                df["ts"].to_numpy(dtype=float),
                df["price"].to_numpy(dtype=float),
            )
    finally:
        con.close()
    return salida


def _precio_en(ts: np.ndarray, px: np.ndarray, instante: float, tolerancia: float) -> Optional[float]:
    i = int(np.searchsorted(ts, instante, side="right") - 1)
    if i < 0 or instante - ts[i] > tolerancia:
        return None
    return float(px[i])


def preparar(senales: Iterable[dict], ticks: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> pd.DataFrame:
    filas = []
    for s in senales:
        clave = _clave(s.get("symbol") or "")
        if clave not in ticks:
            continue
        try:
            direccion = int(np.sign(float(s.get("direction"))))
        except (TypeError, ValueError):
            continue
        emision = pd.to_datetime(s.get("created_at"), utc=True, errors="coerce")
        if pd.isna(emision) or direccion == 0:
            continue
        filas.append(
            {"clave": clave, "emision": float(emision.timestamp()), "direccion": direccion}
        )
    return pd.DataFrame(filas)


def medir(
    senales: pd.DataFrame,
    ticks: Dict[str, Tuple[np.ndarray, np.ndarray]],
    offsets: Sequence[int],
    horizontes: Sequence[int],
    tolerancia: float,
) -> pd.DataFrame:
    registros = []
    for clave, grupo in senales.groupby("clave"):
        ts, px = ticks[clave]
        for fila in grupo.itertuples(index=False):
            registro = {"clave": clave, "direccion": fila.direccion}
            valido = True
            for k in offsets:
                entrada = _precio_en(ts, px, fila.emision + k, tolerancia)
                if entrada is None:
                    valido = False
                    break
                registro[f"px_{k}"] = entrada
            if not valido:
                continue
            for k in offsets:
                for h in horizontes:
                    salida = _precio_en(ts, px, fila.emision + k + h, tolerancia)
                    registro[f"mov_{k}_{h}"] = (
                        np.nan if salida is None else (salida - registro[f"px_{k}"]) * fila.direccion
                    )
            registro["emision"] = fila.emision
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


def _celda(mov: np.ndarray, invertido: bool = False) -> str:
    mov = mov[np.isfinite(mov)]
    mov = mov[mov != 0]
    if mov.size == 0:
        return "     -      "
    aciertos = int(np.sum((mov < 0) if invertido else (mov > 0)))
    tasa = aciertos / mov.size
    lo, hi = wilson(aciertos, mov.size)
    marca = "*" if (not invertido and lo * 100 > BREAKEVEN) else " "
    return f"{tasa * 100:4.1f}%[{lo * 100:2.0f},{hi * 100:2.0f}]{marca}"


def _tabla(datos: pd.DataFrame, offsets: Sequence[int], horizontes: Sequence[int],
           titulo: str, invertido: bool = False) -> None:
    print(f"\n### {titulo}  (señales={len(datos)})")
    if datos.empty:
        print("  sin casos")
        return
    print("  entrada\\salida" + "".join(f"+{h:>3}s{'':<8}" for h in horizontes))
    for k in offsets:
        celdas = "".join(
            f"{_celda(datos[f'mov_{k}_{h}'].to_numpy(dtype=float), invertido):<14}"
            for h in horizontes
        )
        n = int(np.isfinite(datos[f"mov_{k}_{horizontes[-1]}"]).sum())
        print(f"  +{k:>4}s (n={n:<5}){celdas}")


def _matriz(datos: pd.DataFrame, offsets: Sequence[int], horizontes: Sequence[int]):
    """Matriz de signos (señales x celdas) y máscara de celdas válidas."""
    celdas = [(k, h) for k in offsets for h in horizontes]
    signos = np.empty((len(datos), len(celdas)))
    valido = np.empty((len(datos), len(celdas)), dtype=bool)
    for j, (k, h) in enumerate(celdas):
        mov = datos[f"mov_{k}_{h}"].to_numpy(dtype=float)
        valido[:, j] = np.isfinite(mov) & (mov != 0)
        signos[:, j] = np.where(valido[:, j], np.sign(np.nan_to_num(mov)), 0.0)
    return celdas, signos, valido


def _tasas_celdas(signos: np.ndarray, valido: np.ndarray) -> np.ndarray:
    aciertos = np.sum((signos > 0) & valido, axis=0)
    n = valido.sum(axis=0)
    return np.where(n > 0, aciertos / np.maximum(n, 1), np.nan)


def permutacion(datos: pd.DataFrame, offsets: Sequence[int], horizontes: Sequence[int],
                n: int = 2000, semilla: int = 7, invertido: bool = False) -> None:
    """¿El mejor de los 80 valores es un efecto o el máximo esperable del ruido?

    Bajo la hipótesis nula (la alerta no dice nada) cada señal equivale a
    lanzar una moneda sobre su propio movimiento: se invierte el signo al azar
    en la mitad de las señales y se vuelve a calcular el máximo de la rejilla.
    """
    celdas, signos, valido = _matriz(datos, offsets, horizontes)
    if invertido:
        signos = -signos
    tasas = _tasas_celdas(signos, valido)
    observado = float(np.nanmax(tasas))
    j_obs = int(np.nanargmax(tasas))
    rng = np.random.default_rng(semilla)
    maximos = []
    for _ in range(n):
        giro = rng.choice((-1.0, 1.0), size=(signos.shape[0], 1))
        maximos.append(float(np.nanmax(_tasas_celdas(signos * giro, valido))))
    maximos = np.array(maximos)
    p = float(np.mean(maximos >= observado))
    etiqueta = "control invertido" if invertido else "con la alerta"
    print(f"\n### prueba de permutación · {etiqueta} ({n} giros aleatorios de signo)")
    print(f"  observado: mejor celda {observado * 100:.1f}% (entrada +{celdas[j_obs][0]}s, salida +{celdas[j_obs][1]}s)")
    print(f"  bajo la nula: medio {maximos.mean() * 100:.1f}%  p95 {np.percentile(maximos, 95) * 100:.1f}%"
          f"  p99 {np.percentile(maximos, 99) * 100:.1f}%")
    print(f"  p-valor del mejor valor = {p:.3f} → {'compatible con ruido' if p > 0.05 else 'efecto real'}")


def estabilidad(datos: pd.DataFrame, offsets: Sequence[int], horizontes: Sequence[int],
                top: int = 5, invertido: bool = False) -> None:
    """Repite el mejor valor en dos mitades temporales: un efecto real se sostiene."""
    if datos.empty or "emision" not in datos.columns:
        return
    mitad = float(np.median(datos["emision"].to_numpy(dtype=float)))
    celdas, signos, valido = _matriz(datos, offsets, horizontes)
    if invertido:
        signos = -signos
    tasas = _tasas_celdas(signos, valido)
    primera = datos["emision"].to_numpy(dtype=float) < mitad
    t1 = _tasas_celdas(signos[primera], valido[primera])
    t2 = _tasas_celdas(signos[~primera], valido[~primera])
    print(f"\n### estabilidad temporal de las {top} mejores celdas"
          f" · {'control invertido' if invertido else 'con la alerta'}")
    print("  entrada  salida   total   1ª mitad  2ª mitad")
    for j in np.argsort(-np.nan_to_num(tasas, nan=-1))[:top]:
        k, h = celdas[j]
        print(f"  +{k:>4}s  +{h:>4}s  {tasas[j] * 100:5.1f}%  {t1[j] * 100:7.1f}%  {t2[j] * 100:7.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticks", type=Path, required=True, help="sqlite con la tabla ticks")
    ap.add_argument("--db", action="append", default=[], type=Path,
                    help="sqlite con senales_core (repetible)")
    ap.add_argument("--offsets", default=",".join(map(str, OFFSETS)))
    ap.add_argument("--horizontes", default=",".join(map(str, HORIZONTES)))
    ap.add_argument("--tolerancia", type=float, default=5.0,
                    help="hueco máximo tolerado entre el instante pedido y el tick usado")
    ap.add_argument("--permutaciones", type=int, default=2000,
                    help="giros aleatorios de signo para el contraste de la mejor celda")
    args = ap.parse_args()
    if not args.db:
        raise SystemExit("falta al menos un --db")

    offsets = [int(x) for x in args.offsets.split(",") if x.strip()]
    horizontes = [int(x) for x in args.horizontes.split(",") if x.strip()]

    senales = cargar_senales(args.db)
    claves = sorted({_clave(s.get("symbol")) for s in senales})
    ticks = cargar_ticks(args.ticks, claves)
    print(f"señales leídas={len(senales)}  activos con ticks={sorted(ticks)}")

    datos = medir(preparar(senales, ticks), ticks, offsets, horizontes, args.tolerancia)
    if datos.empty:
        raise SystemExit("ningún caso quedó completo con esos offsets")
    print(f"señales con cobertura completa={len(datos)}  breakeven={BREAKEVEN:.2f}% (payout 90%)")

    _tabla(datos, offsets, horizontes, "con la alerta")
    _tabla(datos, offsets, horizontes, "control invertido", invertido=True)
    for clave, grupo in datos.groupby("clave"):
        _tabla(grupo, offsets, horizontes, f"con la alerta · {clave}")

    for clave, grupo in datos.groupby("clave"):
        _tabla(grupo, offsets, horizontes, f"control invertido · {clave}", invertido=True)

    permutacion(datos, offsets, horizontes, args.permutaciones)
    permutacion(datos, offsets, horizontes, args.permutaciones, invertido=True)
    for clave, grupo in datos.groupby("clave"):
        permutacion(grupo, offsets, horizontes, args.permutaciones // 2, invertido=True)
    estabilidad(datos, offsets, horizontes)
    estabilidad(datos, offsets, horizontes, invertido=True)

    print("\n### tamaño del movimiento por activo (mediana de |mov|, entrada en la emisión)")
    print("  salida" + "".join(f"{k:>14}" for k in sorted(datos["clave"].unique())))
    for h in horizontes:
        celdas = []
        for clave in sorted(datos["clave"].unique()):
            mov = datos.loc[datos["clave"] == clave, f"mov_0_{h}"].to_numpy(dtype=float)
            mov = mov[np.isfinite(mov)]
            celdas.append(f"{np.median(np.abs(mov)):14.5f}" if mov.size else f"{'-':>14}")
        print(f"  +{h:>4}s" + "".join(celdas))


if __name__ == "__main__":
    main()
