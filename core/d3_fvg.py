#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D3 — Fair Value Gap (intravela)."""
from core.estructuras import Signal
from core.detectores.base import Contexto, Detector


class DetectorD3(Detector):
    nombre = "D3"

    def detectar(self, ctx: Contexto) -> Signal:
        ha = ctx._i_high(ctx.df_m15, 2)
        la = ctx._i_low(ctx.df_m15, 2)
        hb = ctx._i_high(ctx.df_m15, 1)
        lb = ctx._i_low(ctx.df_m15, 1)
        cb = ctx._i_close(ctx.df_m15, 1)
        ob = ctx._i_open(ctx.df_m15, 1)
        hc = ctx._i_high(ctx.df_m15, 0)
        lc2 = ctx._i_low(ctx.df_m15, 0)
        if ha == 0 or la == 0 or hb == 0 or lb == 0 or hc == 0 or lc2 == 0:
            return None
        atr14 = ctx.g_atr14_buffer[0] if ctx.g_atr14_buffer else 0.0
        if atr14 <= 0:
            return None

        fvg_alcista = ha < lc2
        fvg_bajista = la > hc
        if not fvg_alcista and not fvg_bajista:
            return None

        fvg_size = 0.0
        fvg_top = 0.0
        fvg_bottom = 0.0
        direction = 0
        if fvg_alcista:
            fvg_size = lc2 - ha
            fvg_top = lc2
            fvg_bottom = ha
            direction = 1
        else:
            fvg_size = la - hc
            fvg_top = la
            fvg_bottom = hc
            direction = -1

        if fvg_size <= 0:
            return None
        fvg_size_atr = fvg_size / atr14
        br_b = abs(cb - ob) / (hb - lb) if (hb - lb) > 0 else 0
        dir_ok = (fvg_alcista and cb > ob) or (fvg_bajista and cb < ob)
        if fvg_size_atr < ctx.inp_fvg_min_size_atr or br_b < ctx.inp_fvg_body_ratio or not dir_ok:
            return None

        mit_level = fvg_bottom + (fvg_top - fvg_bottom) * ctx.inp_fvg_mitig_umbral
        price0 = ctx._i_close(ctx.df_m15, 0)
        mitigado = (direction == 1 and price0 <= mit_level) or (direction == -1 and price0 >= mit_level)

        defendido = False
        if direction == 1 and price0 > fvg_top:
            defendido = True
        if direction == -1 and price0 < fvg_bottom:
            defendido = True

        det = "D3_DEF" if defendido else "D3"

        sig = Signal()
        sig.entry_time = ctx._i_time(ctx.df_m15, 0)
        sig.entry_bar_shift = 0
        sig.direction = direction
        sig.entry_price = price0
        sig.detector = det
        sig.es_intravela = True
        sig.fvg_top = fvg_top
        sig.fvg_bottom = fvg_bottom
        sig.fvg_size_atr = fvg_size_atr
        sig.fvg_mitigated = mitigado
        sig._fvg_br = br_b
        sig.atr14 = atr14 / ctx.point
        sig.session = ctx.session
        sig.kill_zone = ctx.kill_zone
        sig.estructura_direccion = ctx.estructura.dir_estructura if ctx.estructura else "NEUTRO"
        sig.regimen_volatilidad = ctx.regimen_vol

        ok_mss, mss_bars, mss_dir, mss_level = ctx.detect_mss_h4()
        sig.mss_aligned = ok_mss
        sig.mss_bars_ago_h4 = mss_bars
        sig.mss_direction = mss_dir
        sig.mss_level = mss_level

        sig.g1_compresion = ctx.g1
        sig.g2_persistencia = ctx.g2
        sig.g4_agotamiento = ctx.g4

        slope = (ctx.g_ema21_buffer[0] - ctx.g_ema21_buffer[3]) / atr14 if len(ctx.g_ema21_buffer) > 3 else 0.0
        sig.tipo = self.clasificar(sig, ctx, fvg_size_atr, br_b, slope)
        return sig

    def _get_trend_velas(self, ctx: Contexto) -> int:
        if len(ctx.g_ema21_buffer) < 2 or len(ctx.g_ema50_buffer) < 2:
            return 0
        up = ctx.g_ema21_buffer[1] > ctx.g_ema50_buffer[1]
        down = ctx.g_ema21_buffer[1] < ctx.g_ema50_buffer[1]
        if not up and not down:
            return 0
        count = 0
        max_i = min(55, len(ctx.g_ema21_buffer), len(ctx.g_ema50_buffer))
        for i in range(1, max_i):
            u = ctx.g_ema21_buffer[i] > ctx.g_ema50_buffer[i]
            d = ctx.g_ema21_buffer[i] < ctx.g_ema50_buffer[i]
            if not u and not d:
                continue
            if up and not u:
                break
            if down and not d:
                break
            count += 1
        return count

    def clasificar(self, sig: Signal, ctx: Contexto, fvg_size: float = None, br: float = None, slope: float = None) -> str:
        if fvg_size is None:
            fvg_size = sig.fvg_size_atr
        if br is None:
            br = getattr(sig, '_fvg_br', 0.0)
        trend = self._get_trend_velas(ctx)
        if fvg_size > 0.50 and br > 0.70 and trend >= 3:
            return "A"
        if fvg_size > 0.35 and br > 0.60:
            return "B"
        if fvg_size > ctx.inp_fvg_min_size_atr and br > ctx.inp_fvg_body_ratio:
            return "C"
        return "D"
