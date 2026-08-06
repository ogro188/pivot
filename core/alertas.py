#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alertas: NTFY, cola, deduplicación, cooldown."""
import hashlib
import math
import requests
from datetime import datetime
from typing import List
from core.estructuras import Signal, AlertEntry


class AlertasEngine:
    def __init__(self, ntfy_topic: str = "", ntfy_server: str = "https://ntfy.sh",
                 symbol: str = "", point: float = 0.00001):
        self.ntfy_topic = ntfy_topic
        self.ntfy_server = ntfy_server.rstrip("/")
        self.symbol = symbol
        self.point = point
        self.g_last_alert_time = datetime(1970, 1, 1)
        self.g_last_ntfy_time = datetime(1970, 1, 1)
        self.g_alert_queue: List[AlertEntry] = []
        self.MAX_ALERT_QUEUE = 50

    def _fmt_price(self, value: float) -> str:
        digits = max(0, int(round(-math.log10(self.point)))) if self.point > 0 else 5
        return f"{value:.{digits}f}"

    def build_alert_text(self, sig: Signal) -> str:
        dir_text = "CALL" if sig.direction == 1 else "PUT"
        dir_emoji = "🟢" if sig.direction == 1 else "🔴"
        sep = "━━━━━━━━━━━━━━━━━━━━"
        msg = sep + "\n"
        msg += f"{dir_emoji} {dir_text} — {sig.symbol} — {sig.detector}"
        if sig.tipo:
            msg += f" · {sig.tipo}"
        msg += "\n" + sep + "\n"
        et = sig.entry_time
        hora = f"{et.hour:02d}:{et.minute:02d}" if et else "00:00"
        msg += f"⚡ {hora} {sig.session}"
        if sig.kill_zone != "NONE":
            msg += f" · {sig.kill_zone}"
        msg += "\n" + sep + "\n"

        msg += "🔮 HIPÓTESIS\n" + sep + "\n"
        msg += sig.hipotesis_causa + "\n"
        msg += sig.hipotesis_efecto + "\n"
        msg += sig.hipotesis_razon + "\n"
        msg += sig.hipotesis_invalidez + "\n" + sep + "\n"

        confirms = ""
        if sig.detector == "D1":
            if sig.br > 0.70: confirms += "Cuerpo fuerte · "
            if sig.bs > 0.80: confirms += "Penetración profunda · "
            if sig.kill_zone != "NONE": confirms += "Kill Zone · "
        elif sig.detector in ("D2", "D2_ANTICIPACION"):
            if sig.equal_hl_detected: confirms += "Nivel igual · "
            if sig.hipotesis_zona != "NEUTRO": confirms += sig.hipotesis_zona + " · "
            if sig.sweep_volume_ratio > 1.5: confirms += "Volumen alto · "
            if sig.kill_zone != "NONE": confirms += "Kill Zone · "
            if sig.displacement_post_sweep: confirms += "Displacement ✓ · "
            if sig.toques_nivel >= 3: confirms += f"{sig.toques_nivel} toques · "
        elif sig.detector in ("D3", "D3_DEF"):
            if sig.detector == "D3_DEF": confirms += "FVG defendido · "
            if sig.hipotesis_zona != "NEUTRO": confirms += sig.hipotesis_zona + " · "
            if sig.mss_aligned: confirms += "MSS H4 · "
            if sig.kill_zone != "NONE": confirms += "Kill Zone · "
        elif sig.detector == "D4":
            if sig.ob_impulse_atr > 1.5: confirms += "Impulso fuerte · "
            if sig.kill_zone != "NONE": confirms += "Kill Zone · "
        elif sig.detector == "D5":
            confirms += f"MSS H4 {sig.mss_direction} · "
            if sig.kill_zone != "NONE": confirms += "Kill Zone · "
            if sig.displacement_post_sweep: confirms += "Displacement ✓ · "

        if len(confirms) > 2:
            confirms = confirms[:-3]
        msg += "✅ CONFIRMACIONES\n" + sep + "\n" + confirms + "\n" + sep + "\n"

        msg += "🔍 DIAGNÓSTICO\n" + sep + "\n"
        if sig.velocidad_aproximacion >= 70:
            vel_txt = "RÁPIDA"
        elif sig.velocidad_aproximacion >= 50:
            vel_txt = "NORMAL"
        else:
            vel_txt = "LENTA"
        msg += f"⚡ Velocidad aprox: {vel_txt} ({sig.velocidad_aproximacion:.0f}/100)\n"
        msg += f"🌊 Régimen: {sig.regimen_volatilidad}\n"
        msg += sep + "\n"

        msg += f"⏱️ VENCIMIENTO: {sig.hipotesis_expiry_velas} vela(s) M15 ({sig.hipotesis_expiry_minutos} min)\n" + sep + "\n"
        msg += f"💰 REFERENCIA: {self._fmt_price(sig.entry_price)} | Objetivo: {self._fmt_price(sig.hipotesis_objetivo)}\n" + sep + "\n"
        msg += f"📊 PROBABILIDAD: {sig.hipotesis_prob_min}-{sig.hipotesis_prob_max}%\n"
        conv_emoji = {"ALTA": "🔥", "MEDIA": "⚡", "BAJA": "💤"}.get(sig.conviccion, "⚡")
        msg += f"{conv_emoji} CONVICCIÓN: {sig.conviccion}\n" + sep + "\n"
        msg += "📍 Dato para evaluar, no una orden."
        return msg

    def send_ntfy_message(self, text: str) -> bool:
        if not self.ntfy_topic:
            return False
        if (datetime.now() - self.g_last_ntfy_time).total_seconds() < 5:
            return False
        url = f"{self.ntfy_server}/{self.ntfy_topic}"
        headers = {"Content-Type": "text/plain"}
        try:
            resp = requests.post(url, data=text.encode("utf-8"), headers=headers, timeout=3)
            if resp.status_code == 200:
                self.g_last_ntfy_time = datetime.now()
                return True
            return False
        except Exception:
            return False

    def queue_alert(self, text: str):
        if len(self.g_alert_queue) >= self.MAX_ALERT_QUEUE:
            self.g_alert_queue.pop(0)
        hash_val = hashlib.md5(text.encode("utf-8")).hexdigest()
        for a in self.g_alert_queue:
            if a.content_hash == hash_val:
                return
        entry = AlertEntry()
        entry.text = text
        entry.content_hash = hash_val
        entry.retry_count = 0
        entry.last_retry = datetime(1970, 1, 1)
        entry.created_at = datetime.now()
        self.g_alert_queue.append(entry)

    def process_alert_queue(self):
        if not self.g_alert_queue:
            return
        now = datetime.now()
        keep = []
        for alert in self.g_alert_queue:
            backoff = (2 ** min(alert.retry_count, 6)) * 5
            if alert.retry_count > 0 and (now - alert.last_retry).total_seconds() < backoff:
                keep.append(alert)
                continue
            if self.send_ntfy_message(alert.text):
                print("Alerta encolada enviada")
            else:
                alert.retry_count += 1
                alert.last_retry = now
                if alert.retry_count >= 3:
                    print("Alerta descartada")
                else:
                    keep.append(alert)
        self.g_alert_queue = keep

    def flush_alert_queue(self):
        max_flush = min(len(self.g_alert_queue), 3)
        sent_indices = []
        for i in range(max_flush):
            if self.send_ntfy_message(self.g_alert_queue[i].text):
                sent_indices.append(i)
        for i in sorted(sent_indices, reverse=True):
            self.g_alert_queue.pop(i)
