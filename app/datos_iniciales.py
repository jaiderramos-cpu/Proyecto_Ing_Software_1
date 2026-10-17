"""Comandos de consola: crear la base de datos, cargar volumen de prueba y respaldar."""
import os
import random
import sqlite3
from datetime import datetime, timedelta

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from .db import conectar, crear_esquema

CONTRASENA_DEMO = "Soporte2026*"

USUARIOS_DEMO = [
    ("Administrador General", "admin@soporte.local", "administrador", 1),
    ("Carla Coordinadora", "coordinador@soporte.local", "coordinador", 1),
    ("Pedro Técnico", "tecnico1@soporte.local", "tecnico", 1),
    ("Sofía Técnica", "tecnico2@soporte.local", "tecnico", 1),
    ("Mario Técnico (inactivo)", "tecnico3@soporte.local", "tecnico", 0),
    ("Ana Solicitante", "ana@soporte.local", "solicitante", 1),
    ("Luis Solicitante", "luis@soporte.local", "solicitante", 1),
]


def crear_usuarios_demo(con, hash_contrasena=None):
    hash_contrasena = hash_contrasena or generate_password_hash(CONTRASENA_DEMO)
    with con:
        for nombre, correo, rol, activo in USUARIOS_DEMO:
            con.execute(
                "INSERT OR IGNORE INTO usuarios (nombre, correo, hash_contrasena, rol, activo) "
                "VALUES (?, ?, ?, ?, ?)",
                (nombre, correo, hash_contrasena, rol, activo),
            )


def cargar_volumen(con, total_usuarios=500, total_tickets=30000, semilla=2026):
    """Llena la base con el escenario de RNF-06: 500 usuarios y 30.000 tickets históricos."""
    from .tickets import reglas

    azar = random.Random(semilla)
    hash_demo = generate_password_hash(CONTRASENA_DEMO)
    crear_usuarios_demo(con, hash_demo)
    existentes = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    with con:
        for i in range(existentes, total_usuarios):
            rol = "tecnico" if i % 25 == 0 else "solicitante"
            con.execute(
                "INSERT INTO usuarios (nombre, correo, hash_contrasena, rol, activo) VALUES (?, ?, ?, ?, 1)",
                (f"Usuario {i:03d}", f"usuario{i:03d}@soporte.local", hash_demo, rol),
            )
    solicitantes = [f["id"] for f in con.execute("SELECT id FROM usuarios WHERE rol = 'solicitante'")]
    tecnicos = [f["id"] for f in con.execute("SELECT id FROM usuarios WHERE rol = 'tecnico' AND activo = 1")]
    inicio = datetime(2024, 1, 1)
    filas = []
    for _ in range(total_tickets):
        fecha = inicio + timedelta(minutes=azar.randint(0, 60 * 24 * 650))
        estado = azar.choice(reglas.ESTADOS)
        tecnico = None if estado in (reglas.NUEVO, reglas.CANCELADO) else azar.choice(tecnicos)
        resuelto = estado in (reglas.RESUELTO, reglas.CERRADO)
        filas.append((
            azar.choice(solicitantes), tecnico,
            f"Solicitud de prueba {azar.randint(1, 9999)}", "Descripción generada para la prueba de volumen.",
            azar.choice(reglas.CATEGORIAS), azar.choice(reglas.PRIORIDADES), estado,
            fecha.strftime("%Y-%m-%d %H:%M:%S"),
            (fecha + timedelta(hours=azar.randint(1, 96))).strftime("%Y-%m-%d %H:%M:%S") if resuelto else None,
            "Solución de prueba." if resuelto else None,
        ))
    with con:
        con.executemany(
            "INSERT INTO tickets (solicitante_id, tecnico_id, asunto, descripcion, categoria, prioridad, "
            "estado, fecha_creacion, fecha_resolucion, solucion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        con.execute("UPDATE tickets SET codigo = printf('TK-%06d', id) WHERE codigo IS NULL")


def respaldar(ruta_bd, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, f"soporte_{datetime.now():%Y%m%d_%H%M%S}.db")
    origen = sqlite3.connect(ruta_bd)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    origen.close()
    copia.close()
    return destino


@click.command("iniciar-bd")
def iniciar_bd_cmd():
    """Crea las tablas y los usuarios de ejemplo."""
    con = conectar(current_app.config["DATABASE"])
    crear_esquema(con)
    crear_usuarios_demo(con)
    con.close()
    click.echo("Base de datos lista. Contraseña de los usuarios de ejemplo: " + CONTRASENA_DEMO)


@click.command("cargar-volumen")
def cargar_volumen_cmd():
    """Carga 500 usuarios y 30.000 tickets para pruebas de rendimiento."""
    con = conectar(current_app.config["DATABASE"])
    crear_esquema(con)
    cargar_volumen(con)
    con.close()
    click.echo("Volumen de prueba cargado.")


@click.command("respaldar-bd")
def respaldar_bd_cmd():
    """Genera una copia de seguridad de la base de datos."""
    carpeta = os.path.join(os.path.dirname(current_app.instance_path), "respaldos")
    click.echo("Respaldo creado en: " + respaldar(current_app.config["DATABASE"], carpeta))


def registrar_comandos(app):
    app.cli.add_command(iniciar_bd_cmd)
    app.cli.add_command(cargar_volumen_cmd)
    app.cli.add_command(respaldar_bd_cmd)
