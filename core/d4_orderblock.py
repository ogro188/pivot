#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D4 — Order Block confluence (intravela)."""
from core.estructuras import Signal
from core.detectores.base import Contexto, Detector


class DetectorD4(Detector):
    nombre = "D4"

    def detectar(self, ctx: Contexto) -> Signal:
        close0 = ctx._i_close(ctx.df_m15, 0)
        if close0 == 0:
            return None
        atr14 = ctx.g_atr14_buffer[0] if ctx.g_atr14_buffer else 0.0
        if atr14 <= 0:
            return None

        ob_bar = -1
        ob_dir = 0
        ob_high = 0.0
        ob_low = 0.0
        ob_impulse = 0.0
        ob_vol = 0.0

        for i in range(2, 5):
            oi = ctx._i_open(ctx.df_m15, i)
            ci = ctx._i_close(ctx.df_m15, i)
            hi = ctx._i_high(ctx.df_m15, i)
            li = ctx._i_low(ctx.df_m15, i)
            ri = hi - li
            if ri <= 0 or hi == 0 or li == 0:
                continue
            if abs(ci - oi) / ri < ctx.inp_ob_body_min:
                continue
            di = 1 if ci > oi else -1
            nc = ctx._i_close(ctx.df_m15, i - 1)
            imp = abs(nc - ci) / atr14
            imp_dir_ok = (di == -1 and nc > ci) or (di == 1 and nc < ci)
            if imp < ctx.inp_ob_impulse_min or not imp_dir_ok:
                continue

            tested = False
            for j in range(i - 1, 0, -1):
                hj = ctx._i_high(ctx.df_m15, j)
                lj = ctx._i_low(ctx.df_m15, j)
                if hj == 0 or lj == 0:
                    break
                if hj >= li and lj <= hi:
                    tested = True
                    break
            if tested:
                continue

            ob_bar = i
            ob_dir = di
            ob_high = hi
            ob_low = li
            ob_impulse = imp
            ob_vol = ctx.get_volume_ratio(i, ctx.inp_ob_lookback)
            break

        if ob_bar == -1 or ob_bar > 4:
            return None

        entering = (ob_dir == 1 and close0 <= ob_high and close0 >= ob_low) or                    (ob_dir == -1 and close0 >= ob_low and close0 <= ob_high)
        if not entering:
            return None

        centro = (ob_high + ob_low) / 2.0
        if abs(close0 - centro) > atr14 * 2.0:
            return None

        sig = Signal()
        sig.entry_time = ctx._i_time(ctx.df_m15, 0)
        sig.entry_bar_shift = 0
        sig.direction = ob_dir
        sig.entry_price = close0
        sig.detector = self.nombre
        sig.es_intravela = True
        sig.ob_high = ob_high
        sig.ob_low = ob_low
        sig.ob_bars_ago = ob_bar
        sig.ob_impulse_atr = ob_impulse
        sig._ob_volume_ratio = ob_vol
        sig.ob_confluence = True
        sig.atr14 = atr14 / ctx.point
        sig.session = ctx.session
        sig.kill_zone = ctx.kill_zone
        sig.estructura_direccion = ctx.estructura.dir_estructura if ctx.estructura else "NEUTRO"
        sig.g1_compresion = ctx.g1
        sig.g2_persistencia = ctx.g2
        sig.regimen_volatilidad = ctx.regimen_vol
        sig.tipo = self.clasificar(sig, ctx, ob_impulse, ob_vol, ob_bar)
        return sig

    def clasificar(self, sig: Signal, ctx: Contexto, impulso: float = None, vol: float = None, ob_bars: int = None) -> str:
        if impulso is None:
            impulso = sig.ob_impulse_atr
        if vol is None:
            vol = getattr(sig, '_ob_volume_ratio', 1.0)
        if ob_bars is None:
            ob_bars = sig.ob_bars_ago
        if impulso > 1.80 and vol > 1.50 and ob_bars <= 6:
            return "A"
        if impulso > 1.40 and vol > 1.20:
            return "B"
        if impulso >= ctx.inp_ob_impulse_min:
            return "C"
        return "D"
