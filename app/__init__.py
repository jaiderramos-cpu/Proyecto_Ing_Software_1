"""Arranque de la aplicación web de soporte técnico."""
import os

from flask import Flask, g, redirect, render_template, url_for

from . import db
from .datos_iniciales import registrar_comandos


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SOPORTE_SECRET_KEY", "cambiar-esta-clave"),
        DATABASE=os.environ.get("SOPORTE_DB", os.path.join(app.instance_path, "soporte.db")),
    )
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.registrar(app)
    registrar_comandos(app)

    from .autenticacion import bp as bp_autenticacion
    app.register_blueprint(bp_autenticacion)

    @app.route("/")
    def inicio():
        if g.usuario is None:
            return redirect(url_for("autenticacion.login"))
        return redirect(url_for("tickets.listar"))

    # Mensajes de error genéricos: nunca se muestran detalles internos (RNF-07)
    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template("error.html", titulo="Página no encontrada",
                               mensaje="La página o el ticket que busca no existe."), 404

    @app.errorhandler(500)
    def error_interno(_e):
        return render_template("error.html", titulo="Ocurrió un problema",
                               mensaje="No fue posible completar la operación. Intente de nuevo más tarde."), 500

    return app
