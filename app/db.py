"""Conexión a la base de datos SQLite y definición de las tablas."""
import sqlite3

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    correo          TEXT    NOT NULL UNIQUE,
    hash_contrasena TEXT    NOT NULL,
    rol             TEXT    NOT NULL CHECK (rol IN ('administrador', 'coordinador', 'tecnico', 'solicitante')),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS tickets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo             TEXT    UNIQUE,
    solicitante_id     INTEGER NOT NULL REFERENCES usuarios(id),
    tecnico_id         INTEGER REFERENCES usuarios(id),
    asunto             TEXT    NOT NULL CHECK (length(trim(asunto)) > 0),
    descripcion        TEXT    NOT NULL CHECK (length(trim(descripcion)) > 0),
    categoria          TEXT    NOT NULL,
    prioridad          TEXT    NOT NULL CHECK (prioridad IN ('Baja', 'Media', 'Alta', 'Crítica')),
    estado             TEXT    NOT NULL CHECK (estado IN ('Nuevo', 'Asignado', 'En progreso',
                                   'Pendiente del solicitante', 'Resuelto', 'Cerrado', 'Cancelado')),
    fecha_creacion     TEXT    NOT NULL,
    fecha_resolucion   TEXT,
    fecha_cierre       TEXT,
    solucion           TEXT,
    motivo_cancelacion TEXT
);

-- Historial de atención: nunca se borra (RN-10)
CREATE TABLE IF NOT EXISTS historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id       INTEGER NOT NULL REFERENCES tickets(id),
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    tipo            TEXT    NOT NULL,
    estado_anterior TEXT,
    estado_nuevo    TEXT,
    texto           TEXT,
    fecha           TEXT    NOT NULL
);

-- Índices para que los filtros respondan rápido con 30.000 tickets (RNF-06)
CREATE INDEX IF NOT EXISTS ix_tickets_estado      ON tickets(estado);
CREATE INDEX IF NOT EXISTS ix_tickets_categoria   ON tickets(categoria);
CREATE INDEX IF NOT EXISTS ix_tickets_prioridad   ON tickets(prioridad);
CREATE INDEX IF NOT EXISTS ix_tickets_fecha       ON tickets(fecha_creacion);
CREATE INDEX IF NOT EXISTS ix_tickets_solicitante ON tickets(solicitante_id);
CREATE INDEX IF NOT EXISTS ix_tickets_tecnico     ON tickets(tecnico_id);
CREATE INDEX IF NOT EXISTS ix_historial_ticket    ON historial(ticket_id);
"""


def conectar(ruta):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def crear_esquema(con):
    con.executescript(ESQUEMA)


def obtener_bd():
    if "bd" not in g:
        g.bd = conectar(current_app.config["DATABASE"])
    return g.bd


def cerrar_bd(_error=None):
    con = g.pop("bd", None)
    if con is not None:
        con.close()


def registrar(app):
    app.teardown_appcontext(cerrar_bd)
