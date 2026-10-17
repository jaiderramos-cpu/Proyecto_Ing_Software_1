"""Páginas web del Módulo de Tickets. Solo traducen la petición web a una operación del servicio."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..autenticacion import login_requerido
from ..db import obtener_bd
from . import reglas as r
from . import repositorio as repo
from . import servicio

bp = Blueprint("tickets", __name__, url_prefix="/tickets")


@bp.app_errorhandler(r.ErrorPermiso)
def sin_permiso(error):
    return render_template("error.html", titulo="Acceso no permitido", mensaje=str(error)), 403


@bp.app_errorhandler(r.ErrorNoEncontrado)
def no_existe(error):
    return render_template("error.html", titulo="No encontrado", mensaje=str(error)), 404


def _ejecutar(ticket_id, operacion, mensaje_ok, *args):
    """Ejecuta una operación sobre el ticket y vuelve al detalle con un mensaje claro."""
    try:
        operacion(obtener_bd(), g.usuario, ticket_id, *args)
        flash(mensaje_ok, "ok")
    except r.ErrorValidacion as error:
        flash(str(error), "error")
    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@bp.route("/")
@login_requerido
def listar():
    filtros = {k: request.args.get(k, "") for k in ("estado", "categoria", "prioridad", "desde", "hasta", "mios")}
    try:
        filas, total = servicio.listar(obtener_bd(), g.usuario, filtros, request.args.get("pagina", 1))
    except r.ErrorValidacion as error:
        flash(str(error), "error")
        filas, total = [], 0
    pagina = max(1, request.args.get("pagina", 1, type=int) or 1)
    return render_template("tickets/lista.html", tickets=filas, total=total, filtros=filtros, pagina=pagina,
                           paginas=max(1, -(-total // repo.POR_PAGINA)), reglas=r)


@bp.route("/nuevo", methods=("GET", "POST"))
@login_requerido
def nuevo():
    datos = {"asunto": "", "descripcion": "", "categoria": "", "prioridad": "Media"}
    if request.method == "POST":
        datos = {k: request.form.get(k, "") for k in datos}
        try:
            ticket_id = servicio.crear(obtener_bd(), g.usuario, datos)
            flash(f"Ticket TK-{ticket_id:06d} registrado correctamente.", "ok")
            return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
        except r.ErrorValidacion as error:
            flash(str(error), "error")
            return render_template("tickets/nuevo.html", datos=datos, reglas=r), 400
    return render_template("tickets/nuevo.html", datos=datos, reglas=r)


@bp.route("/<int:ticket_id>")
@login_requerido
def detalle(ticket_id):
    con = obtener_bd()
    ticket, historial = servicio.consultar(con, g.usuario, ticket_id)
    return render_template("tickets/detalle.html", t=ticket, historial=historial, reglas=r,
                           tecnicos=repo.tecnicos_activos(con), servicio=servicio)


@bp.route("/<int:ticket_id>/asignar", methods=("POST",))
@login_requerido
def asignar(ticket_id):
    return _ejecutar(ticket_id, servicio.asignar, "Ticket asignado.", request.form.get("tecnico_id"))


@bp.route("/<int:ticket_id>/estado", methods=("POST",))
@login_requerido
def cambiar_estado(ticket_id):
    return _ejecutar(ticket_id, servicio.cambiar_estado, "Estado actualizado.",
                     request.form.get("estado"), request.form.get("texto", ""))


@bp.route("/<int:ticket_id>/comentario", methods=("POST",))
@login_requerido
def comentar(ticket_id):
    return _ejecutar(ticket_id, servicio.comentar, "Comentario registrado.", request.form.get("texto"))


@bp.route("/<int:ticket_id>/complemento", methods=("POST",))
@login_requerido
def complementar(ticket_id):
    return _ejecutar(ticket_id, servicio.complementar, "Información agregada.", request.form.get("texto"))


@bp.route("/<int:ticket_id>/cancelar", methods=("POST",))
@login_requerido
def cancelar(ticket_id):
    return _ejecutar(ticket_id, servicio.cancelar, "Ticket cancelado.", request.form.get("motivo"))


@bp.route("/<int:ticket_id>/reabrir", methods=("POST",))
@login_requerido
def reabrir(ticket_id):
    return _ejecutar(ticket_id, servicio.reabrir, "Ticket reabierto.", request.form.get("motivo"))


@bp.route("/<int:ticket_id>/cerrar", methods=("POST",))
@login_requerido
def cerrar(ticket_id):
    return _ejecutar(ticket_id, servicio.cerrar, "Ticket cerrado.")
