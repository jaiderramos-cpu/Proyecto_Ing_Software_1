"""Inicio y cierre de sesión.

Es un apoyo mínimo para poder usar el Módulo de Tickets: no incluye la
administración de cuentas (RF-02), que está documentada pero no implementada.
"""
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import obtener_bd

bp = Blueprint("autenticacion", __name__)

MENSAJE_LOGIN_FALLIDO = "Correo o contraseña incorrectos."


def autenticar(con, correo, contrasena):
    """Devuelve el usuario si las credenciales son válidas y la cuenta está activa."""
    fila = con.execute(
        "SELECT * FROM usuarios WHERE correo = ?", ((correo or "").strip().lower(),)
    ).fetchone()
    if fila is None or not fila["activo"]:
        return None
    if not check_password_hash(fila["hash_contrasena"], contrasena or ""):
        return None
    return fila


@bp.before_app_request
def cargar_usuario():
    usuario_id = session.get("usuario_id")
    g.usuario = None
    if usuario_id is not None:
        fila = obtener_bd().execute(
            "SELECT id, nombre, correo, rol, activo FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if fila is not None and fila["activo"]:
            g.usuario = dict(fila)
        else:
            session.clear()


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.usuario is None:
            flash("Debe iniciar sesión para continuar.", "aviso")
            return redirect(url_for("autenticacion.login"))
        return vista(*args, **kwargs)

    return envoltura


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        usuario = autenticar(obtener_bd(), request.form.get("correo"), request.form.get("contrasena"))
        if usuario is None:
            flash(MENSAJE_LOGIN_FALLIDO, "error")
            return render_template("login.html", correo=request.form.get("correo", "")), 401
        session.clear()
        session["usuario_id"] = usuario["id"]
        return redirect(url_for("tickets.listar"))
    return render_template("login.html", correo="")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "ok")
    return redirect(url_for("autenticacion.login"))
