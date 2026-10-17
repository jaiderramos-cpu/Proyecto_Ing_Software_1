"""Operaciones del Módulo de Tickets.

Cada operación: (1) carga el ticket, (2) revisa permisos según el rol,
(3) revisa las reglas de negocio y (4) guarda el cambio y su historial dentro
de una sola transacción. Si algo falla, el ticket queda como estaba (RNF-05, RN-12).
"""
from datetime import datetime

from . import reglas as r
from . import repositorio as repo

ROLES_GESTION = ("administrador", "coordinador")
ESTADOS_TECNICO = (r.EN_PROGRESO, r.PENDIENTE, r.RESUELTO)
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora(ahora=None):
    return (ahora or datetime.now()).replace(microsecond=0)


def _texto_fecha(fecha):
    return fecha.strftime(FORMATO_FECHA)


def _entero(valor, campo):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise r.ErrorValidacion(f"El campo «{campo}» debe ser un número.") from None


def _cargar(con, ticket_id):
    ticket = repo.buscar_por_id(con, _entero(ticket_id, "Ticket"))
    if ticket is None:
        raise r.ErrorNoEncontrado("El ticket solicitado no existe.")
    return ticket


def _es_gestor(usuario):
    return usuario["rol"] in ROLES_GESTION


def _es_dueno(usuario, ticket):
    return usuario["rol"] == "solicitante" and ticket["solicitante_id"] == usuario["id"]


def _es_tecnico_asignado(usuario, ticket):
    return usuario["rol"] == "tecnico" and ticket["tecnico_id"] == usuario["id"]


def _cambiar_estado(con, usuario, ticket, nuevo, texto, fecha, **otros_campos):
    """Guarda el nuevo estado y su registro de historial en una sola transacción."""
    if not r.transicion_permitida(ticket["estado"], nuevo):
        raise r.ErrorValidacion(f"No se puede pasar de «{ticket['estado']}» a «{nuevo}».")
    with con:
        repo.actualizar(con, ticket["id"], estado=nuevo, **otros_campos)
        repo.registrar_historial(con, ticket["id"], usuario["id"], "cambio_estado", texto,
                                 _texto_fecha(fecha), ticket["estado"], nuevo)


# ---------------------------------------------------------------- consultas

def puede_ver(usuario, ticket):
    """RN-07: el solicitante solo ve sus tickets; técnicos y gestores ven todos (RF-05)."""
    return usuario["rol"] != "solicitante" or ticket["solicitante_id"] == usuario["id"]


def consultar(con, usuario, ticket_id):
    ticket = _cargar(con, ticket_id)
    if not puede_ver(usuario, ticket):
        raise r.ErrorPermiso("Solo puede consultar sus propios tickets.")
    return ticket, repo.historial(con, ticket["id"])


def listar(con, usuario, filtros, pagina=1):
    """RF-05 y RF-08: lista con filtros por estado, categoría, prioridad y fecha."""
    limpios = {}
    for campo, opciones in (("estado", r.ESTADOS), ("categoria", r.CATEGORIAS), ("prioridad", r.PRIORIDADES)):
        valor = (filtros.get(campo) or "").strip()
        if valor:
            limpios[campo] = r.validar_opcion(valor, campo.capitalize(), opciones)
    for campo in ("desde", "hasta"):
        valor = (filtros.get(campo) or "").strip()
        if valor:
            try:
                datetime.strptime(valor, "%Y-%m-%d")
            except ValueError:
                raise r.ErrorValidacion("Las fechas deben tener el formato AAAA-MM-DD.") from None
            limpios[campo] = valor
    if usuario["rol"] == "solicitante":
        limpios["solicitante_id"] = usuario["id"]
    elif filtros.get("mios") and usuario["rol"] == "tecnico":
        limpios["tecnico_id"] = usuario["id"]
    pagina = max(1, _entero(pagina or 1, "Página"))
    return repo.listar(con, limpios, pagina)


# ---------------------------------------------------------------- operaciones

def crear(con, usuario, datos, ahora=None):
    """RF-03, RF-04, RN-01, RN-02: registra un ticket en estado Nuevo."""
    limpios = r.validar_datos_ticket(datos)
    fecha = _texto_fecha(_ahora(ahora))
    with con:
        ticket_id = repo.insertar_ticket(con, usuario["id"], limpios, fecha)
        repo.registrar_historial(con, ticket_id, usuario["id"], "creacion", "Ticket registrado.",
                                 fecha, None, r.NUEVO)
    return ticket_id


def asignar(con, usuario, ticket_id, tecnico_id, ahora=None):
    """RF-06, RN-06: asigna un ticket Nuevo a un técnico activo."""
    ticket = _cargar(con, ticket_id)
    tecnico = repo.buscar_usuario(con, _entero(tecnico_id, "Técnico"))
    if tecnico is None or tecnico["rol"] != "tecnico" or not tecnico["activo"]:
        raise r.ErrorValidacion("Solo se puede asignar el ticket a un técnico activo.")
    fecha = _ahora(ahora)
    _cambiar_estado(con, usuario, ticket, r.ASIGNADO, f"Asignado a {tecnico['nombre']}.", fecha,
                    tecnico_id=tecnico["id"])


def cambiar_estado(con, usuario, ticket_id, nuevo_estado, texto="", ahora=None):
    """RF-07, RF-10, RN-08: el técnico asignado avanza el trabajo del ticket."""
    ticket = _cargar(con, ticket_id)
    if not _es_tecnico_asignado(usuario, ticket):
        raise r.ErrorPermiso("Solo el técnico asignado puede cambiar el estado de este ticket.")
    if nuevo_estado not in ESTADOS_TECNICO or ticket["estado"] == r.RESUELTO:
        raise r.ErrorValidacion(f"No se puede pasar de «{ticket['estado']}» a «{nuevo_estado}».")
    texto = (texto or "").strip()
    fecha = _ahora(ahora)
    if nuevo_estado == r.RESUELTO:
        solucion = r.validar_texto(texto, "Descripción de la solución", r.MAX_TEXTO)
        _cambiar_estado(con, usuario, ticket, r.RESUELTO, solucion, fecha,
                        solucion=solucion, fecha_resolucion=_texto_fecha(fecha))
    else:
        if len(texto) > r.MAX_TEXTO:
            raise r.ErrorValidacion(f"El comentario admite máximo {r.MAX_TEXTO} caracteres.")
        _cambiar_estado(con, usuario, ticket, nuevo_estado, texto or None, fecha)


def comentar(con, usuario, ticket_id, texto, ahora=None):
    """RF-07: comentario de seguimiento del técnico asignado o de un gestor."""
    ticket = _cargar(con, ticket_id)
    if not (_es_tecnico_asignado(usuario, ticket) or _es_gestor(usuario)):
        raise r.ErrorPermiso("Solo el técnico asignado o un coordinador puede comentar este ticket.")
    if ticket["estado"] in r.ESTADOS_FINALES:
        raise r.ErrorValidacion("El ticket está en un estado final y no admite cambios.")
    texto = r.validar_texto(texto, "Comentario", r.MAX_TEXTO)
    with con:
        repo.registrar_historial(con, ticket["id"], usuario["id"], "comentario", texto,
                                 _texto_fecha(_ahora(ahora)))


def complementar(con, usuario, ticket_id, texto, ahora=None):
    """RF-08, RN-07: el solicitante agrega información a su ticket mientras está abierto."""
    ticket = _cargar(con, ticket_id)
    if not _es_dueno(usuario, ticket):
        raise r.ErrorPermiso("Solo el solicitante puede complementar su propio ticket.")
    if ticket["estado"] not in r.ESTADOS_ABIERTOS:
        raise r.ErrorValidacion("Solo se puede agregar información a tickets abiertos.")
    texto = r.validar_texto(texto, "Información complementaria", r.MAX_TEXTO)
    with con:
        repo.registrar_historial(con, ticket["id"], usuario["id"], "complemento", texto,
                                 _texto_fecha(_ahora(ahora)))


def cancelar(con, usuario, ticket_id, motivo, ahora=None):
    """RF-09, RN-07: el solicitante cancela su ticket solo si está Nuevo, indicando el motivo."""
    ticket = _cargar(con, ticket_id)
    if not _es_dueno(usuario, ticket):
        raise r.ErrorPermiso("Solo el solicitante puede cancelar su propio ticket.")
    if ticket["estado"] != r.NUEVO:
        raise r.ErrorValidacion("Solo se pueden cancelar tickets en estado «Nuevo».")
    motivo = r.validar_texto(motivo, "Motivo de cancelación", r.MAX_TEXTO)
    _cambiar_estado(con, usuario, ticket, r.CANCELADO, motivo, _ahora(ahora), motivo_cancelacion=motivo)


def reabrir(con, usuario, ticket_id, motivo, ahora=None):
    """RF-11, RN-09: reabre un ticket Resuelto dentro de los 5 días siguientes."""
    ticket = _cargar(con, ticket_id)
    if not (_es_dueno(usuario, ticket) or _es_gestor(usuario)):
        raise r.ErrorPermiso("Solo el solicitante o un coordinador puede reabrir este ticket.")
    if ticket["estado"] != r.RESUELTO:
        raise r.ErrorValidacion("Solo se pueden reabrir tickets en estado «Resuelto».")
    fecha = _ahora(ahora)
    resuelto_el = datetime.strptime(ticket["fecha_resolucion"], FORMATO_FECHA)
    if not r.puede_reabrir(resuelto_el, fecha):
        raise r.ErrorValidacion(
            f"El plazo de {r.DIAS_REAPERTURA} días para reabrir terminó. Registre un ticket nuevo.")
    motivo = r.validar_texto(motivo, "Motivo de reapertura", r.MAX_TEXTO)
    _cambiar_estado(con, usuario, ticket, r.EN_PROGRESO, "Reabierto: " + motivo, fecha,
                    fecha_resolucion=None)


def cerrar(con, usuario, ticket_id, ahora=None):
    """RN-05: el solicitante (o un gestor) confirma la solución y cierra el ticket."""
    ticket = _cargar(con, ticket_id)
    if not (_es_dueno(usuario, ticket) or _es_gestor(usuario)):
        raise r.ErrorPermiso("Solo el solicitante o un coordinador puede cerrar este ticket.")
    fecha = _ahora(ahora)
    _cambiar_estado(con, usuario, ticket, r.CERRADO, "Solución confirmada; ticket cerrado.", fecha,
                    fecha_cierre=_texto_fecha(fecha))
