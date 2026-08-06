"""Backtest engine: mismo código, mismo contexto."""
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from kernel.contrato import ActivoInfo, Estrategia, Contexto
from kernel.feeds.datafeed import DataFeed
from kernel.feeds.csv import CSVFeed
from kernel.tiempo import ServicioTiempo
from kernel.señales import Latch, _floor_to_timeframe


@dataclass
class BacktestResult:
    senales: list
    n_senales: int
    winrate: float
    profit_factor: float
    drawdown_max: float
    drawdown_max_pct: float
    sharpe: float
    equity: list
    senales_por_mes: dict
    metricas_por_etiqueta: dict


class Backtest:
    def __init__(self, activo: ActivoInfo, estrategia: Estrategia,
                 fuente: CSVFeed, desde: datetime, hasta: datetime):
        self.activo = activo
        self.estrategia = estrategia
        self.fuente = fuente
        self.desde = desde
        self.hasta = hasta
        self.senales: list = []
        self.equity: list = [(desde, 0.0)]
        self.latch = Latch()
        self._pnl = 0.0
        self._wins = 0
        self._losses = 0
        self._max_equity = 0.0
        self._drawdown_max = 0.0

    def run(self) -> BacktestResult:
        self.fuente.conectar()
        df_base = self.fuente.get_candles(self.estrategia.timeframes[0], 5000)
        if len(df_base) == 0:
            return BacktestResult([], 0, 0.0, 0.0, 0.0, 0.0, 0.0, [], {}, {})
        mask = (df_base.index >= self.desde) & (df_base.index <= self.hasta)
        df_base = df_base.loc[mask]
        if len(df_base) == 0:
            return BacktestResult([], 0, 0.0, 0.0, 0.0, 0.0, 0.0, [], {}, {})

        feed = DataFeed(self.activo, self.fuente, max_bars=5000)
        for tf in self.activo.timeframes:
            df_tf = self.fuente.get_candles(tf, 5000)
            feed._velas[tf] = df_tf[df_tf.index <= self.desde].tail(5000)

        tiempo_svc = ServicioTiempo(self.activo.horario_broker_utc)
        self.estrategia.setup({}, self.activo)

        for i in range(len(df_base)):
            row = df_base.iloc[i]
            ts = df_base.index[i]
            if not isinstance(ts, datetime):
                ts = pd.Timestamp(ts).to_pydatetime()
            tf_base = self.estrategia.timeframes[0]

            feed.on_candle_close(tf_base, row)

            if "candle_close" not in self.estrategia.eventos:
                continue

            ctx = Contexto(
                activo=self.activo,
                velas=feed.snapshot(),
                precio=float(row["close"]),
                tiempo=ts,
                evento="candle_close",
                session=tiempo_svc.get_session(ts),
                kill_zone=tiempo_svc.get_kill_zone(ts)
            )
            ctx.indicador = feed.get_indicador

            try:
                senales = self.estrategia.detectar(ctx)
            except Exception:
                continue

            for sig in senales:
                sig.simbolo = self.activo.simbolo
                sig.nivel_clave = self.estrategia.nivel_clave(sig)
                vela_ts = _floor_to_timeframe(ts, tf_base)
                if not self.latch.check(sig.estrategia, sig.simbolo, sig.direccion,
                                        sig.nivel_clave, vela_ts, self.activo.point):
                    continue

                futuro = df_base.iloc[i+1:i+1+sig.expiracion_velas]
                if len(futuro) < sig.expiracion_velas:
                    continue
                precio_final = float(futuro.iloc[-1]["close"])
                win = (precio_final - sig.precio) * sig.direccion > 0
                retorno = (precio_final - sig.precio) * sig.direccion / self.activo.point

                self.senales.append(sig)
                self._pnl += retorno
                if win:
                    self._wins += 1
                else:
                    self._losses += 1
                self.equity.append((ts, self._pnl))
                self._max_equity = max(self._max_equity, self._pnl)
                dd = self._max_equity - self._pnl
                self._drawdown_max = max(self._drawdown_max, dd)

        n = len(self.senales)
        winrate = self._wins / n if n > 0 else 0.0
        profit_factor = self._wins / self._losses if self._losses > 0 else float('inf')
        returns = [self.equity[i][1] - self.equity[i-1][1] for i in range(1, len(self.equity))]
        avg_r = sum(returns) / len(returns) if returns else 0.0
        std_r = (sum((r - avg_r) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1.0
        sharpe = avg_r / std_r if std_r > 0 else 0.0

        return BacktestResult(
            senales=self.senales,
            n_senales=n,
            winrate=winrate,
            profit_factor=profit_factor,
            drawdown_max=self._drawdown_max,
            drawdown_max_pct=0.0,
            sharpe=sharpe,
            equity=self.equity,
            senales_por_mes={},
            metricas_por_etiqueta={}
        )
