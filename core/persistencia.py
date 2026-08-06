#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistencia: CSV, pending signals, locks."""
import os
import time
import math
from datetime import datetime
from typing import List, Set
from core.estructuras import Signal


class Persistencia:
    def __init__(self, data_dir: str, symbol: str, cola_senales_file: str = "Cola_Senales_v78.csv",
                 lock_timeout_ms: int = 5000, lock_stale_sec: int = 5):
        self.data_dir = data_dir
        self.symbol = symbol
        self.cola_senales_file = cola_senales_file
        self.lock_timeout_ms = lock_timeout_ms
        self.lock_stale_sec = lock_stale_sec
        os.makedirs(data_dir, exist_ok=True)

        suffix = "_v78_" + symbol
        self.csv_filename = os.path.join(data_dir, "Micro_v78" + suffix + ".csv")
        self.pending_filename = os.path.join(data_dir, "Pending_v78" + suffix + ".csv")
        self.lock_filename = os.path.join(data_dir, cola_senales_file + ".lock")

    def fmt_price(self, value: float, point: float) -> str:
        digits = max(0, int(round(-math.log10(point)))) if point > 0 else 5
        return f"{value:.{digits}f}"

    def write_signal_to_csv(self, sig: Signal, point: float):
        try:
            exists = os.path.exists(self.csv_filename)
            with open(self.csv_filename, "a", encoding="utf-8") as f:
                if not exists:
                    f.write("id;entry_time;symbol;direction;entry_price;detector;tipo;prob_min;prob_max;expiry_velas;conviccion;regimen\n")
                line = (
                    f"{sig.id};{sig.entry_time.strftime('%Y.%m.%d %H:%M:%S')};"
                    f"{sig.symbol};{sig.direction};{self.fmt_price(sig.entry_price, point)};"
                    f"{sig.detector};{sig.tipo};{sig.hipotesis_prob_min};"
                    f"{sig.hipotesis_prob_max};{sig.hipotesis_expiry_velas};"
                    f"{sig.conviccion};{sig.regimen_volatilidad}\n"
                )
                f.write(line)
        except OSError as e:
            print(f"ERROR escribiendo CSV: {e}")

    def acquire_lock(self) -> bool:
        deadline = time.monotonic() + (self.lock_timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            if os.path.exists(self.lock_filename):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(self.lock_filename))
                    if (datetime.now() - mtime).total_seconds() > self.lock_stale_sec:
                        os.remove(self.lock_filename)
                    else:
                        time.sleep(0.01)
                        continue
                except Exception:
                    pass
            try:
                with open(self.lock_filename, "w") as f:
                    f.write(str(int(datetime.now().timestamp())))
                return True
            except Exception:
                time.sleep(0.01)
        return False

    def release_lock(self):
        try:
            if os.path.exists(self.lock_filename):
                os.remove(self.lock_filename)
        except Exception:
            pass

    def save_pending_signals(self, pending_signals: List[Signal]):
        try:
            with open(self.pending_filename, "w", encoding="utf-8") as f:
                f.write(f"{len(pending_signals)}\n")
                for s in pending_signals:
                    line = (
                        f"{s.id};{s.entry_time.strftime('%Y.%m.%d %H:%M:%S')};"
                        f"{s.direction};{s.entry_price};{s.detector};"
                        f"{s.tipo};{s.signal_age_bars};"
                        f"{'1' if s.completada else '0'};{s.hipotesis_expiry_velas};"
                        f"{s.conviccion}\n"
                    )
                    f.write(line)
        except OSError as e:
            print(f"ERROR guardando pending: {e}")

    def load_pending_signals(self) -> tuple:
        pending = []
        ids = set()
        if not os.path.exists(self.pending_filename):
            return pending, ids
        try:
            with open(self.pending_filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return pending, ids
            try:
                count = int(lines[0].strip())
            except ValueError:
                return pending, ids
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(";")
                if len(parts) < 9:
                    continue
                s = Signal()
                s.id = int(parts[0])
                s.entry_time = datetime.strptime(parts[1], "%Y.%m.%d %H:%M:%S")
                s.direction = int(parts[2])
                s.entry_price = float(parts[3])
                s.detector = parts[4]
                s.tipo = parts[5]
                s.signal_age_bars = int(parts[6])
                s.completada = parts[7] == "1"
                s.hipotesis_expiry_velas = int(parts[8])
                if len(parts) >= 10:
                    s.conviccion = parts[9]
                pending.append(s)
                ids.add(s.id)
        except OSError as e:
            print(f"ERROR cargando pending: {e}")
        return pending, ids
