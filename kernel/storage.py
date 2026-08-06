"""SQLite + escritor async por cola."""
import queue
import sqlite3
import threading
import time
import json
from kernel.contrato import Señal


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activos (
    simbolo TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    point REAL NOT NULL,
    decimales INTEGER NOT NULL,
    pip REAL NOT NULL,
    fuente_tipo TEXT NOT NULL,
    fuente_config TEXT NOT NULL,
    timeframes TEXT NOT NULL,
    horario_broker_utc INTEGER NOT NULL,
    max_bars INTEGER DEFAULT 5000
);

CREATE TABLE IF NOT EXISTS senales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    asset TEXT NOT NULL,
    estrategia TEXT NOT NULL,
    etiqueta TEXT,
    direccion INTEGER NOT NULL CHECK(direccion IN (1, -1)),
    precio REAL NOT NULL,
    expiracion_velas INTEGER NOT NULL CHECK(expiracion_velas >= 1),
    conf_min INTEGER NOT NULL CHECK(conf_min BETWEEN 0 AND 100),
    conf_max INTEGER NOT NULL CHECK(conf_max BETWEEN 0 AND 100),
    objetivo REAL,
    invalidacion REAL,
    narrativa TEXT,
    metricas TEXT,
    overlays TEXT,
    payload TEXT,
    nivel_clave REAL,
    estado TEXT NOT NULL DEFAULT 'pending' CHECK(estado IN ('pending', 'completada')),
    FOREIGN KEY (asset) REFERENCES activos(simbolo)
);
CREATE INDEX IF NOT EXISTS idx_senales_asset_ts ON senales(asset, ts DESC);
CREATE INDEX IF NOT EXISTS idx_senales_estrategia ON senales(estrategia, asset);

CREATE TABLE IF NOT EXISTS mediciones (
    signal_id INTEGER NOT NULL,
    offset INTEGER NOT NULL,
    retorno REAL NOT NULL,
    mfe REAL NOT NULL,
    mae REAL NOT NULL,
    PRIMARY KEY (signal_id, offset),
    FOREIGN KEY (signal_id) REFERENCES senales(id)
);

CREATE TABLE IF NOT EXISTS resultados (
    signal_id INTEGER PRIMARY KEY,
    win INTEGER NOT NULL CHECK(win IN (0, 1)),
    retorno_final REAL NOT NULL,
    medido_ts INTEGER NOT NULL,
    FOREIGN KEY (signal_id) REFERENCES senales(id)
);

CREATE TABLE IF NOT EXISTS config (
    asset TEXT NOT NULL,
    estrategia TEXT NOT NULL,
    clave TEXT NOT NULL,
    valor TEXT NOT NULL,
    activa INTEGER NOT NULL DEFAULT 1 CHECK(activa IN (0, 1)),
    PRIMARY KEY (asset, estrategia, clave),
    FOREIGN KEY (asset) REFERENCES activos(simbolo)
);

CREATE TABLE IF NOT EXISTS calibraciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT NOT NULL,
    asset TEXT NOT NULL,
    estrategia TEXT NOT NULL,
    etiqueta TEXT,
    n_senales INTEGER NOT NULL,
    winrate REAL,
    profit_factor REAL,
    drawdown_max REAL,
    sharpe REAL,
    params TEXT,
    FOREIGN KEY (asset) REFERENCES activos(simbolo)
);
CREATE INDEX IF NOT EXISTS idx_calibraciones_asset_estrategia ON calibraciones(asset, estrategia);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    level TEXT NOT NULL CHECK(level IN ('DEBUG', 'INFO', 'WARN', 'ERROR')),
    asset TEXT,
    estrategia TEXT,
    categoria TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    contexto TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_asset_ts ON logs(asset, ts DESC);
"""


class StorageWriter(threading.Thread):
    def __init__(self, db_path: str, q: queue.Queue):
        super().__init__(daemon=True)
        self.db_path = db_path
        self.queue = q
        self.batch_size = 50
        self.flush_interval_sec = 1.0

    def run(self) -> None:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.executescript(SCHEMA_SQL)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        while True:
            batch = []
            item = self.queue.get()
            if item is None:
                break
            batch.append(item)
            deadline = time.time() + self.flush_interval_sec
            while len(batch) < self.batch_size and time.time() < deadline:
                try:
                    batch.append(self.queue.get_nowait())
                except queue.Empty:
                    time.sleep(0.01)
            self._flush(conn, batch)
        conn.close()

    def _flush(self, conn: sqlite3.Connection, batch: list) -> None:
        for attempt in range(5):
            try:
                with conn:
                    for item in batch:
                        self._write_one(conn, item)
                return
            except sqlite3.OperationalError:
                time.sleep(0.1 * (2 ** attempt))

    def _write_one(self, conn: sqlite3.Connection, item) -> None:
        if isinstance(item, Señal):
            cmin, cmax = item.confianza
            conn.execute("""
                INSERT INTO senales (ts, asset, estrategia, etiqueta, direccion, precio,
                expiracion_velas, conf_min, conf_max, objetivo, invalidacion, narrativa,
                metricas, overlays, payload, nivel_clave, estado)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                int(item.tiempo.timestamp() * 1000), item.simbolo, item.estrategia,
                item.etiqueta, item.direccion, item.precio, item.expiracion_velas,
                cmin, cmax, item.objetivo, item.invalidacion, item.narrativa,
                json.dumps([{"label": m.label, "value": m.value, "max": m.max, "unit": m.unit} for m in item.metricas]),
                json.dumps([{"tipo": o.tipo, "color": o.color, "position": o.position, "shape": o.shape,
                             "text": o.text, "price": o.price, "line_type": o.line_type,
                             "style": o.style, "title": o.title, "top": o.top, "bottom": o.bottom, "label": o.label} for o in item.overlays]),
                json.dumps(item.payload),
                item.nivel_clave, item.estado
            ))
        elif isinstance(item, tuple) and item[0] == "resultado":
            _, sig_id, win, retorno = item
            conn.execute("""
                INSERT OR REPLACE INTO resultados (signal_id, win, retorno_final, medido_ts)
                VALUES (?,?,?,?)
            """, (sig_id, 1 if win else 0, retorno, int(time.time() * 1000)))
            conn.execute("UPDATE senales SET estado='completada' WHERE id=?", (sig_id,))
        elif isinstance(item, tuple) and item[0] == "log":
            _, ts, level, asset, estrategia, categoria, mensaje, contexto = item
            conn.execute("""
                INSERT INTO logs (ts, level, asset, estrategia, categoria, mensaje, contexto)
                VALUES (?,?,?,?,?,?,?)
            """, (ts, level, asset, estrategia, categoria, mensaje, json.dumps(contexto) if contexto else None))


class Storage:
    def __init__(self, db_path: str = "data/radar.db"):
        import os
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self.queue: queue.Queue = queue.Queue()
        self.writer = StorageWriter(db_path, self.queue)
        self.writer.start()

    def put_signal(self, sig: Señal) -> None:
        self.queue.put(sig)

    def put_result(self, sig_id: int, win: bool, retorno: float) -> None:
        self.queue.put(("resultado", sig_id, win, retorno))

    def put_log(self, ts: int, level: str, asset: str | None, estrategia: str | None,
                categoria: str, mensaje: str, contexto: dict | None) -> None:
        self.queue.put(("log", ts, level, asset, estrategia, categoria, mensaje, contexto))

    def query_signals(self, asset: str | None = None, limit: int = 50, estado: str | None = None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM senales WHERE 1=1"
        params = []
        if asset:
            sql += " AND asset=?"
            params.append(asset)
        if estado:
            sql += " AND estado=?"
            params.append(estado)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def query_logs(self, asset: str | None = None, limit: int = 200, level: str | None = None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM logs WHERE 1=1"
        params = []
        if asset:
            sql += " AND asset=?"
            params.append(asset)
        if level:
            sql += " AND level=?"
            params.append(level)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def query_history(self, asset: str, tf: str, count: int = 200):
        """Devuelve velas del activo. En v2.0, usa la tabla senales como proxy
        o requiere fuente directa. Para el endpoint /history, se sirve desde
        el DataFeed en memoria del runtime."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Placeholder: en producción, las velas se sirven del DataFeed
        conn.close()
        return []
