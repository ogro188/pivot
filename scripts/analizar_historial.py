# -*- coding: utf-8 -*-
"""Mide el acierto real de las operaciones manuales contra el breakeven del bróker.

Es el único dato que evalúa la decisión discrecional del operador: cuándo entra,
en qué dirección y con qué duración. No usa señales ni velas, solo el historial
de operaciones que exporta el bróker.

Entrada admitida
----------------

CSV con cabecera (coma, punto y coma o tabulador) y nombres de columna en
español o inglés. Se reconocen, en cualquier orden:

- activo: ``activo``, ``asset``, ``symbol``, ``par``, ``ticker``, ``mercado``
- fecha:  ``hora``, ``fecha``, ``open time``, ``hora de apertura``, ``apertura``
- dirección: ``direccion``, ``direction``, ``tipo``, ``type``, ``lado``, ``side``
- resultado: ``resultado``, ``result``, ``ganancia``, ``profit``, ``p/l``, ``neto``
- inversión (opcional): ``inversion``, ``stake``, ``investment``, ``monto``
- payout (opcional): ``payout``, ``pago``, ``rentabilidad``

El resultado vale por su signo (positivo = ganada, negativo = perdida, 0 =
empate) o por su texto (win/ganada/call... vs loss/perdida...). La dirección
acepta call/put, compra/venta, alcista/bajista, up/down, long/short.

También vale pegar las filas por la entrada estándar y guardarlas así:

    activo,fecha,direccion,resultado
    EURUSD-OTC,2026-11-14 22:30,put,ganada
    XAUUSD-OTC,2026-11-14 23:05,call,-1.00

Si el CSV viene sin cabecera, usa ``--sin-cabecera`` indicando el orden:

    --sin-cabecera activo,fecha,direccion,resultado

Cruce con las alertas (opcional, pero es la parte que importa)
---------------------------------------------------------------

Con ``--alertas senales.csv`` se busca, para cada operación, la última alerta
PIVOT del mismo activo emitida antes de la entrada (ventana ``--ventana``,
15 min por defecto). Cada operación queda marcada como:

- **con la alerta**: entró en la misma dirección que la señal;
- **contra la alerta**: entró en la dirección contraria;
- **sin alerta**: no había ninguna señal reciente de ese activo.

Así se separa tu timing de la calidad de PIVOT: si "con la alerta" no supera el
breakeven pero "contra la alerta" sí, el problema es la dirección de la señal,
no tus entradas. El CSV de alertas lleva ``activo, fecha, direccion`` (misma
detección de columnas que el historial; ``resultado`` no hace falta). También
se puede pasar la base de datos: ``--alertas iq_public.db --tabla alertas``.

Salida
------

- acierto con intervalo de Wilson frente al breakeven (1/(1+payout));
- p-valor binomial exacto de una cola: probabilidad de acertar tanto o más si
  la tasa real fuera justo el breakeven;
- desglose por activo, por dirección y por mitades temporales;
- si hay alertas: desglose con/contra/sin alerta y retraso mediano de entrada;
- dinero: inversión total, neto, ROI y esperanza por operación (si hay importes);
- payout implícito del historial (mediana de ganancia / inversión) y cuántas
  operaciones harían falta para demostrar la ventaja observada.

Uso:
    python scripts/analizar_historial.py historial.csv
    pbpaste | python scripts/analizar_historial.py -
    python scripts/analizar_historial.py historial.csv --payout 0.87
    python scripts/analizar_historial.py historial.csv --alertas senales.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

# Breakeven del bróker por defecto: payout 90% (IQ Option, EURUSD a 5 min).
PAYOUT_DEFECTO = 0.90
Z_ALFA = 1.645  # una cola, 5%
Z_POTENCIA = 0.84  # 80% de potencia

ALIAS: Dict[str, Tuple[str, ...]] = {
    "activo": ("activo", "asset", "symbol", "simbolo", "instrumento", "par",
               "ticker", "mercado", "underlying"),
    "fecha": ("hora", "fecha", "date", "time", "hora de apertura", "apertura",
              "open time", "open_time", "opening time", "hora apertura",
              "datetime", "fecha y hora", "close time", "hora de cierre",
              "hora de cierre (utc)", "hora de apertura (utc)", "hora (utc)",
              "entry time", "created at", "emision", "emitida"),
    "direccion": ("direccion", "direction", "dir", "tipo", "type", "lado", "side",
                  "sentido", "operacion", "trade", "accion", "action"),
    "resultado": ("resultado", "result", "ganancia", "profit", "beneficio",
                  "p/l", "pl", "pyl", "neto", "net profit", "win", "amount",
                  "importe", "payout amount"),
    "inversion": ("inversion", "stake", "investment", "monto", "cantidad",
                  "importe invertido", "invested", "tamano", "size", "volume"),
    "payout": ("payout", "pago", "rentabilidad", "retorno", "porcentaje"),
}

_COLUMNAS = ("activo", "fecha", "direccion", "resultado")

_POSITIVO = re.compile(r"\b(win|won|ganad[ao]|ganancia|acierto|positiv[ao]|"
                       r"call|compra|alcista|up|long|buy|arriba)\b")
_NEGATIVO = re.compile(r"\b(loss|lost|perdid[ao]|perdida|fallo|negativ[ao]|"
                       r"put|venta|bajista|down|short|sell|abajo)\b")
_EMPATE = re.compile(r"\b(empate|tie|draw|nulo|anulad[ao]|refund|reembolso)\b")
_SOLO_NUMERO = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


def _normalizar(texto: str) -> str:
    """minúsculas, sin acentos, sin guiones bajos ni espacios repetidos."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"[_\-/]+", " ", sin_acentos.lower())
    return re.sub(r"\s+", " ", limpio).strip()


def _numero(valor: str) -> Optional[float]:
    """Convierte importes con separadores de miles o coma decimal."""
    limpio = re.sub(r"[^\d,.\-+]", "", str(valor))
    if not limpio or not re.search(r"\d", limpio):
        return None
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def _direccion(valor: str) -> Optional[int]:
    texto = _normalizar(valor)
    if _SOLO_NUMERO.match(str(valor).strip()):
        numero = _numero(valor)
        if numero:
            return 1 if numero > 0 else -1
    positivo, negativo = bool(_POSITIVO.search(texto)), bool(_NEGATIVO.search(texto))
    if positivo and not negativo:
        return 1
    if negativo and not positivo:
        return -1
    return None


def _resultado(valor: str) -> Optional[int]:
    """1 ganada, 0 empate, -1 perdida, None si no se entiende."""
    texto = _normalizar(valor)
    if _EMPATE.search(texto):
        return 0
    if _SOLO_NUMERO.match(str(valor).strip()):
        numero = _numero(valor)
        if numero is None:
            return None
        return 1 if numero > 0 else (-1 if numero < 0 else 0)
    numero = _numero(valor)
    if numero is not None and not _POSITIVO.search(texto) and not _NEGATIVO.search(texto):
        return 1 if numero > 0 else (-1 if numero < 0 else 0)
    positivo, negativo = bool(_POSITIVO.search(texto)), bool(_NEGATIVO.search(texto))
    if positivo and not negativo:
        return 1
    if negativo and not positivo:
        return -1
    return None


def _leer_texto(ruta: str) -> str:
    if ruta == "-":
        return sys.stdin.read()
    return Path(ruta).read_text(encoding="utf-8-sig", errors="replace")


def _adivinar_separador(texto: str) -> str:
    muestra = "\n".join(linea for linea in texto.splitlines()[:20] if linea.strip())
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _mapear_columnas(cabecera: Sequence[str]) -> Dict[str, str]:
    """Asocia cada campo lógico con el nombre real de la columna."""
    mapa: Dict[str, str] = {}
    for columna in cabecera:
        normal = _normalizar(columna)
        for campo, alias in ALIAS.items():
            if campo in mapa:
                continue
            if normal in alias or any(normal.startswith(a) for a in alias):
                mapa[campo] = columna
                break
    return mapa


def _es_iso(valores: pd.Series) -> bool:
    """True si todas las fechas legibles empiezan por el año (AAAA-MM-DD)."""
    patron = re.compile(r"^\s*\d{4}-\d{1,2}-\d{1,2}")
    legibles = [str(v) for v in valores.dropna().head(200)]
    return bool(legibles) and all(patron.match(v) for v in legibles)


def _dia_primero(valores: pd.Series) -> Tuple[bool, bool]:
    """Detecta exportaciones DD/MM/AAAA y avisa si el orden es ambiguo.

    Devuelve ``(es_dia_primero, ambiguo)``: ambiguo significa que ninguna fecha
    tiene el primer grupo mayor que 12, así que día y mes son indistinguibles.
    """
    patron = re.compile(r"^\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})")
    revisadas = 0
    for valor in valores.head(500):
        texto = str(valor)
        if re.match(r"^\s*\d{4}-\d{1,2}-\d{1,2}", texto):
            continue  # ISO 8601: año primero, no hay ambigüedad
        encontrado = patron.match(texto)
        if not encontrado:
            continue
        revisadas += 1
        if int(encontrado.group(1)) > 12:
            return True, False
    return False, revisadas > 0


def cargar(ruta: str, sin_cabecera: Optional[str], separador: Optional[str],
           forzar: Dict[str, str], dia_primero: Optional[bool] = None
           ) -> Tuple[pd.DataFrame, List[str]]:
    """Devuelve el histórico normalizado y la lista de avisos."""
    avisos: List[str] = []
    texto = _leer_texto(ruta)
    if not texto.strip():
        raise SystemExit("la entrada está vacía")

    sep = separador or _adivinar_separador(texto)
    cabecera = next(csv.reader(io.StringIO(texto), delimiter=sep), [])

    if sin_cabecera:
        campos = [c.strip() for c in sin_cabecera.split(",")]
        crudo = pd.read_csv(io.StringIO(texto), sep=sep, header=None,
                            names=campos, dtype=str, engine="python")
        mapa = {c: c for c in campos}
    else:
        crudo = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, engine="python")
        mapa = _mapear_columnas(list(crudo.columns))

    mapa.update({k: v for k, v in forzar.items() if v})

    faltan = [c for c in _COLUMNAS if c not in mapa]
    if faltan:
        raise SystemExit(
            f"no reconozco las columnas {faltan}; cabecera leída: {list(crudo.columns)}\n"
            "indícalas a mano con --col-activo/--col-fecha/--col-direccion/--col-resultado"
        )

    if dia_primero is None:
        dia_primero, ambiguo = _dia_primero(crudo[mapa["fecha"]])
        if ambiguo:
            avisos.append("fechas ambiguas: se asumió mes/día; si son DD/MM usa --dia-primero")
    elif _es_iso(crudo[mapa["fecha"]]):
        dia_primero = False  # --dia-primero no aplica a AAAA-MM-DD
    else:
        avisos.append(f"orden de fecha forzado a {'día/mes' if dia_primero else 'mes/día'}")
    try:
        fechas = pd.to_datetime(crudo[mapa["fecha"]], errors="coerce", dayfirst=dia_primero,
                                format="mixed")
    except ValueError:
        fechas = pd.to_datetime(crudo[mapa["fecha"]], errors="coerce", dayfirst=True,
                                format="mixed")
    if fechas.dt.tz is None:
        fechas = fechas.dt.tz_localize("UTC")

    datos = pd.DataFrame({
        "activo": crudo[mapa["activo"]].astype(str).str.strip(),
        "fecha": fechas,
        "direccion": crudo[mapa["direccion"]].map(_direccion),
        "resultado": crudo[mapa["resultado"]].map(_resultado),
    })
    datos["inversion"] = pd.to_numeric(
        crudo[mapa["inversion"]].map(_numero) if "inversion" in mapa else float("nan"),
        errors="coerce",
    )
    datos["resultado_importe"] = pd.to_numeric(
        crudo[mapa["resultado"]].map(_numero), errors="coerce"
    )
    datos["payout_col"] = pd.to_numeric(
        crudo[mapa["payout"]].map(_numero) if "payout" in mapa else float("nan"),
        errors="coerce",
    )

    antes = len(datos)
    datos = datos.dropna(subset=["resultado", "direccion"]).reset_index(drop=True)
    if len(datos) < antes:
        avisos.append(f"{antes - len(datos)} filas descartadas: dirección o resultado ilegible")

    duplicados = datos.duplicated(subset=["activo", "fecha", "direccion", "resultado",
                                          "inversion"], keep="first").sum()
    if duplicados:
        datos = datos.drop_duplicates(subset=["activo", "fecha", "direccion", "resultado",
                                              "inversion"], keep="first")
        avisos.append(f"{duplicados} filas duplicadas eliminadas")

    return datos.reset_index(drop=True), avisos


def _clave_activo(nombre: str) -> str:
    """EURUSD-OTC, eurusd_otc y 'EURUSD OTC' son el mismo activo."""
    limpio = _normalizar(nombre).upper()
    return re.sub(r"[\s\-_]*OTC$", "", limpio).strip()


def _leer_crudo(ruta: str, tabla: Optional[str],
                separador: Optional[str]) -> pd.DataFrame:
    """Lee un CSV o una tabla SQLite sin interpretar nada todavía."""
    if ruta.lower().endswith((".db", ".sqlite", ".sqlite3")):
        import sqlite3

        con = sqlite3.connect(f"file:{Path(ruta).resolve()}?mode=ro", uri=True)
        try:
            if tabla:
                return pd.read_sql_query(f'SELECT * FROM "{tabla}"', con, dtype=str)
            tablas = [f[0] for f in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for candidata in tablas:
                columnas = [f[1] for f in con.execute(
                    f'PRAGMA table_info("{candidata}")').fetchall()]
                mapa = _mapear_columnas(columnas)
                if all(c in mapa for c in ("activo", "fecha", "direccion")):
                    print(f"aviso: alertas leídas de la tabla '{candidata}'")
                    return pd.read_sql_query(f'SELECT * FROM "{candidata}"', con, dtype=str)
        finally:
            con.close()
        raise SystemExit(f"no encuentro en {ruta} una tabla con activo, fecha y dirección"
                         "; indícala con --tabla")

    texto = _leer_texto(ruta)
    if not texto.strip():
        raise SystemExit("el archivo de alertas está vacío")
    sep = separador or _adivinar_separador(texto)
    return pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, engine="python")


def cargar_alertas(ruta: str, tabla: Optional[str], separador: Optional[str],
                   dia_primero: Optional[bool] = None) -> pd.DataFrame:
    """Alertas PIVOT normalizadas. Ancla en la emisión, no en la apertura."""
    crudo = _leer_crudo(ruta, tabla, separador)
    mapa = _mapear_columnas(list(crudo.columns))
    faltan = [c for c in ("activo", "fecha", "direccion") if c not in mapa]
    if faltan:
        raise SystemExit(f"al archivo de alertas le faltan {faltan}; "
                         f"cabecera leída: {list(crudo.columns)}")

    # senales_core guarda entry_time (apertura de la vela, ~15 min tarde) y
    # created_at (emisión real). Si existe created_at, manda created_at.
    emision = next((c for c in crudo.columns
                    if _normalizar(c).replace(" ", "_") in ("created_at", "emision")), None)
    columna_fecha = emision or mapa["fecha"]

    if dia_primero is None:
        dia_primero, ambiguo = _dia_primero(crudo[columna_fecha])
        if ambiguo:
            print("aviso: fechas de alerta ambiguas; se asumió mes/día"
                  " (usa --dia-primero si son DD/MM)")
    elif _es_iso(crudo[columna_fecha]):
        dia_primero = False  # --dia-primero no aplica a AAAA-MM-DD
    try:
        fechas = pd.to_datetime(crudo[columna_fecha], errors="coerce",
                                dayfirst=dia_primero, format="mixed")
    except ValueError:
        fechas = pd.to_datetime(crudo[columna_fecha], errors="coerce",
                                dayfirst=True, format="mixed")
    if fechas.dt.tz is None:
        fechas = fechas.dt.tz_localize("UTC")

    alertas = pd.DataFrame({
        "activo": crudo[mapa["activo"]].map(_clave_activo),
        "fecha_alerta": fechas,
        "dir_alerta": crudo[mapa["direccion"]].map(_direccion),
    }).dropna().reset_index(drop=True)
    if alertas.empty:
        raise SystemExit("no se pudo leer ninguna alerta con activo, fecha y dirección")
    if emision:
        print(f"aviso: alertas fechadas por '{emision}' (emisión, no apertura de vela)")
    return alertas.sort_values("fecha_alerta").reset_index(drop=True)


def cruzar(datos: pd.DataFrame, alertas: pd.DataFrame, ventana_min: float) -> pd.DataFrame:
    """Marca cada operación con la última alerta previa del mismo activo."""
    ops = datos.copy()
    ops["activo"] = ops["activo"].map(_clave_activo)
    orden = ops["fecha"].argsort(kind="mergesort")
    ops = ops.iloc[orden].reset_index(drop=True)

    fusion = pd.merge_asof(
        ops, alertas, left_on="fecha", right_on="fecha_alerta", by="activo",
        direction="backward", tolerance=pd.Timedelta(minutes=ventana_min),
    )
    retraso = (fusion["fecha"] - fusion["fecha_alerta"]).dt.total_seconds() / 60
    fusion["retraso_min"] = retraso
    acorde = fusion["dir_alerta"] == fusion["direccion"]
    fusion["relacion"] = "sin alerta"
    fusion.loc[fusion["dir_alerta"].notna() & acorde, "relacion"] = "con la alerta"
    fusion.loc[fusion["dir_alerta"].notna() & ~acorde, "relacion"] = "contra la alerta"
    return fusion.sort_values("fecha").reset_index(drop=True)


def wilson(aciertos: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = aciertos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - medio), min(1.0, centro + medio))


def _logsumexp(valores: Iterable[float]) -> float:
    valores = list(valores)
    if not valores:
        return float("-inf")
    maximo = max(valores)
    return maximo + math.log(sum(math.exp(v - maximo) for v in valores))


def binom_una_cola(aciertos: int, n: int, p0: float) -> float:
    """P(X >= aciertos) con X ~ Binomial(n, p0). Exacta, sin scipy."""
    if n <= 0:
        return float("nan")
    p0 = min(max(p0, 1e-9), 1 - 1e-9)
    log_p, log_q = math.log(p0), math.log(1 - p0)
    terminos = (
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        + k * log_p + (n - k) * log_q
        for k in range(aciertos, n + 1)
    )
    return min(1.0, math.exp(_logsumexp(terminos)))


def n_necesario(p1: float, p0: float) -> Optional[int]:
    """Operaciones para demostrar la ventaja p1 frente a p0 (5% una cola, 80%)."""
    if p1 <= p0 or p1 >= 1:
        return None
    diferencia = p1 - p0
    numerador = (Z_ALFA * math.sqrt(p0 * (1 - p0)) + Z_POTENCIA * math.sqrt(p1 * (1 - p1))) ** 2
    return int(math.ceil(numerador / (diferencia ** 2)))


def _payout_implicito(datos: pd.DataFrame) -> Optional[float]:
    """Ganancia de las operaciones ganadas / inversión, mediana del historial."""
    ganadas = datos[datos["resultado"] > 0]
    valores = ganadas["payout_col"].dropna()
    if not valores.empty:
        # 87, 0.87 y 87% se refieren al mismo pago: normalizar fila a fila.
        normalizados = valores.map(lambda v: v / 100 if v > 1.5 else v)
        normalizados = normalizados[normalizados > 0]
        if not normalizados.empty:
            return float(normalizados.median())
    if datos["inversion"].isna().all():
        return None
    ganadas = ganadas[ganadas["inversion"].gt(0)]
    if ganadas.empty:
        return None
    ratio = ganadas["resultado_importe"].abs() / ganadas["inversion"]
    ratio = ratio.replace([math.inf, -math.inf], float("nan")).dropna()
    return float(ratio.median()) if not ratio.empty else None


def _breakeven_de(datos: pd.DataFrame, args) -> float:
    """Breakeven del grupo: payout forzado, del historial o el de referencia."""
    if args.breakeven is not None:
        return args.breakeven
    if args.payout is not None:
        return 100 / (1 + args.payout / 100)
    implicito = _payout_implicito(datos)
    payout = implicito if implicito is not None else PAYOUT_DEFECTO
    return 100 / (1 + payout)


def _bloque(titulo: str, datos: pd.DataFrame, breakeven: float) -> None:
    aciertos = int((datos["resultado"] > 0).sum())
    perdidas = int((datos["resultado"] < 0).sum())
    empates = int((datos["resultado"] == 0).sum())
    # Los empates devuelven la inversión: no cuentan ni como acierto ni como fallo.
    n = aciertos + perdidas
    if n == 0:
        return
    tasa = aciertos / n
    lo, hi = wilson(aciertos, n)
    p = binom_una_cola(aciertos, n, breakeven / 100)
    print(f"\n### {titulo}")
    referencia = f"operaciones={n}" if not empates else f"operaciones={n + empates} válidas={n}"
    print(f"  {referencia}  ganadas={aciertos}  perdidas={perdidas}  empates={empates}")
    print(f"  acierto={tasa * 100:.2f}%  IC95=[{lo * 100:.2f}%, {hi * 100:.2f}%]"
          f"  breakeven={breakeven:.2f}% (payout {100 / breakeven * 100 - 100:.0f}%)")
    if lo * 100 > breakeven:
        veredicto = "ventaja real: todo el IC queda por encima del breakeven"
    elif hi * 100 < breakeven:
        veredicto = "pérdida real: todo el IC queda por debajo del breakeven"
    else:
        veredicto = "no concluyente: el IC contiene el breakeven"
    print(f"  p-valor (una cola, H0 = breakeven)={p:.3f} → {veredicto}")

    if datos["inversion"].notna().any():
        inversion = float(datos["inversion"].fillna(0).sum())
        neto = float(datos["resultado_importe"].fillna(0).sum()) if datos[
            "resultado_importe"].notna().any() else float("nan")
        lineas = [f"  inversión total={inversion:.2f}"]
        if not math.isnan(neto):
            lineas.append(f"neto={neto:+.2f}")
            if inversion > 0:
                lineas.append(f"ROI={neto / inversion * 100:+.2f}%")
                lineas.append(f"esperanza={neto / max(len(datos), 1):+.4f}/op")
        print("  " + "  ".join(lineas))

    faltan = n_necesario(tasa, breakeven / 100)
    if faltan and tasa > breakeven / 100:
        print(f"  para demostrar ese {tasa * 100:.1f}% harían falta ~{faltan} operaciones"
              f" (llevas {n})")


def _por_grupo(datos: pd.DataFrame, columna: str, args,
               convertir=lambda x: x) -> None:
    for clave, grupo in datos.groupby(columna, dropna=False):
        if len(grupo) < 10:
            continue
        _bloque(f"{convertir(clave)} ({len(grupo)})", grupo, _breakeven_de(grupo, args))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", nargs="?", default="-",
                    help="CSV del bróker, o '-' para pegar por stdin")
    ap.add_argument("--sep", help="separador de columnas (por defecto se detecta)")
    ap.add_argument("--sin-cabecera", metavar="CAMPOS",
                    help="el CSV no trae cabecera: 'activo,fecha,direccion,resultado'")
    ap.add_argument("--payout", type=float,
                    help="payout del bróker en porcentaje (por defecto, el del historial"
                         " o 90)")
    ap.add_argument("--breakeven", type=float, help="breakeven en %% (anula --payout)")
    ap.add_argument("--activo", action="append", help="filtrar por activo (repetible)")
    ap.add_argument("--dia-primero", action="store_true", default=None,
                    help="las fechas son DD/MM/AAAA (se autodetecta si algún día pasa de 12)")
    ap.add_argument("--desde", help="fecha mínima, p.ej. 2026-10-01")
    ap.add_argument("--hasta", help="fecha máxima")
    ap.add_argument("--alertas", metavar="RUTA",
                    help="CSV (o .db) de alertas PIVOT con activo, fecha y dirección")
    ap.add_argument("--tabla", help="tabla a leer si --alertas es una base SQLite")
    ap.add_argument("--ventana", type=float, default=15.0,
                    help="minutos hacia atrás para buscar la alerta que precede a la entrada "
                         "(por defecto 15)")
    for campo in _COLUMNAS:
        ap.add_argument(f"--col-{campo}", help=f"nombre real de la columna de {campo}")
    args = ap.parse_args()

    forzar = {c: getattr(args, f"col_{c}") for c in _COLUMNAS}
    datos, avisos = cargar(args.archivo, args.sin_cabecera, args.sep, forzar,
                           args.dia_primero)

    if args.activo:
        patron = "|".join(re.escape(a) for a in args.activo)
        datos = datos[datos["activo"].str.contains(patron, case=False, na=False)]
    if args.desde:
        datos = datos[datos["fecha"] >= pd.Timestamp(args.desde, tz="UTC")]
    if args.hasta:
        datos = datos[datos["fecha"] <= pd.Timestamp(args.hasta, tz="UTC") + pd.Timedelta(days=1)]
    datos = datos.reset_index(drop=True)

    if datos.empty:
        raise SystemExit("no queda ninguna operación tras los filtros")

    breakeven = _breakeven_de(datos, args)
    implicito = _payout_implicito(datos)
    if args.breakeven is None and args.payout is None and implicito is not None:
        avisos.append(f"payout medio del historial: {implicito * 100:.1f}%")

    print(f"operaciones leídas={len(datos)}")
    if datos["fecha"].notna().any():
        print(f"periodo={datos['fecha'].min():%Y-%m-%d %H:%M} → "
              f"{datos['fecha'].max():%Y-%m-%d %H:%M}")
        print("activos: " + ", ".join(
            f"{a} ({n})" for a, n in datos['activo'].value_counts().items()))
    for aviso in avisos:
        print(f"aviso: {aviso}")

    _bloque("total", datos, breakeven)
    _por_grupo(datos, "activo", args)
    _por_grupo(datos, "direccion", args, convertir=lambda d: "call" if d > 0 else "put")

    if args.alertas:
        alertas = cargar_alertas(args.alertas, args.tabla, args.sep, args.dia_primero)
        datos = cruzar(datos, alertas, args.ventana)
        sin = int((datos["relacion"] == "sin alerta").sum())
        con = int((datos["relacion"] == "con la alerta").sum())
        contra = int((datos["relacion"] == "contra la alerta").sum())
        print(f"\n## cruce con {len(alertas)} alertas (ventana {args.ventana:g} min)")
        print(f"  con la alerta={con}  contra la alerta={contra}  sin alerta={sin}")
        retrasos = datos["retraso_min"].dropna()
        if not retrasos.empty:
            print(f"  retraso de entrada: mediana={retrasos.median():.1f} min"
                  f"  p25={retrasos.quantile(0.25):.1f}  p75={retrasos.quantile(0.75):.1f}"
                  f"  máximo={retrasos.max():.1f}")
        if con + contra == 0:
            print("  ninguna operación cayó dentro de la ventana: revisa que los nombres de"
                  " activo\n  coincidan y que el historial venga en UTC")
        else:
            orden = ["con la alerta", "contra la alerta", "sin alerta"]
            datos["relacion"] = pd.Categorical(datos["relacion"], categories=orden, ordered=True)
            _por_grupo(datos, "relacion", args)

    if datos["fecha"].notna().sum() == len(datos) and len(datos) > 40:
        mitad = len(datos) // 2
        ordenado = datos.sort_values("fecha").reset_index(drop=True)
        _bloque("primera mitad temporal", ordenado.iloc[:mitad], breakeven)
        _bloque("segunda mitad temporal", ordenado.iloc[mitad:], breakeven)

    print("\nNota: el acierto del historial mezcla tu criterio de entrada con la calidad"
          "\nde las señales." if not args.alertas else
          "\nNota: 'con la alerta' mide la señal más tu timing; 'contra la alerta' mide"
          "\nsolo tu timing en contra de PIVOT. Si el segundo gana, la dirección de la"
          "\nalerta es el problema.")
    if not args.alertas:
        print("Para separar las dos cosas usa --alertas con las señales del mismo periodo.")


if __name__ == "__main__":
    main()
