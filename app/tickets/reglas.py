"""Reglas de negocio del Módulo de Tickets.

Este archivo no conoce la base de datos ni la web: solo decide qué está
permitido. Así las reglas se prueban de forma aislada y se cambian en un único lugar.
"""

PRIORIDADES = ("Baja", "Media", "Alta", "Crítica")                     # RN-03
CATEGORIAS = ("Hardware", "Software", "Red", "Accesos", "Correo", "Otro")

NUEVO = "Nuevo"
ASIGNADO = "Asignado"
EN_PROGRESO = "En progreso"
PENDIENTE = "Pendiente del solicitante"
RESUELTO = "Resuelto"
CERRADO = "Cerrado"
CANCELADO = "Cancelado"
ESTADOS = (NUEVO, ASIGNADO, EN_PROGRESO, PENDIENTE, RESUELTO, CERRADO, CANCELADO)  # RN-04

ESTADOS_FINALES = (CERRADO, CANCELADO)                                  # RN-10
ESTADOS_ABIERTOS = (NUEVO, ASIGNADO, EN_PROGRESO, PENDIENTE)

# RN-05: a qué estados se puede pasar desde cada estado
TRANSICIONES = {
    NUEVO: (ASIGNADO, CANCELADO),
    ASIGNADO: (EN_PROGRESO,),
    EN_PROGRESO: (PENDIENTE, RESUELTO),
    PENDIENTE: (EN_PROGRESO, RESUELTO),
    RESUELTO: (CERRADO, EN_PROGRESO),
    CERRADO: (),
    CANCELADO: (),
}

DIAS_REAPERTURA = 5                                                     # RN-09
MAX_ASUNTO = 150
MAX_DESCRIPCION = 4000
MAX_TEXTO = 2000


class ErrorValidacion(Exception):
    """Datos inválidos o transición no permitida. El ticket no cambia."""


class ErrorPermiso(Exception):
    """El usuario no tiene permiso para la operación (RN-12, RNF-04)."""


class ErrorNoEncontrado(Exception):
    """El ticket o el usuario solicitado no existe."""


def transicion_permitida(actual, nuevo):
    return nuevo in TRANSICIONES.get(actual, ())


def validar_texto(valor, campo, maximo):
    """Valida un texto obligatorio y su longitud máxima (RN-02, RNF-10)."""
    if not isinstance(valor, str) or valor == "":
        raise ErrorValidacion(f"El campo «{campo}» es obligatorio.")
    if len(valor) > maximo:
        raise ErrorValidacion(f"El campo «{campo}» admite máximo {maximo} caracteres.")
    return valor


def validar_opcion(valor, campo, opciones):
    if valor not in opciones:
        raise ErrorValidacion(f"El valor de «{campo}» no es válido. Opciones: {', '.join(opciones)}.")
    return valor


def validar_datos_ticket(datos):
    """Revisa los datos de un ticket nuevo y devuelve los valores limpios."""
    return {
        "asunto": validar_texto(datos.get("asunto"), "Asunto", MAX_ASUNTO),
        "descripcion": validar_texto(datos.get("descripcion"), "Descripción", MAX_DESCRIPCION),
        "categoria": validar_opcion(datos.get("categoria"), "Categoría", CATEGORIAS),
        "prioridad": validar_opcion(datos.get("prioridad"), "Prioridad", PRIORIDADES),
    }


def puede_reabrir(fecha_resolucion, ahora):
    """RN-09: se puede reabrir durante los cinco días calendario siguientes a la resolución."""
    dias = (ahora.date() - fecha_resolucion.date()).days
    return 0 <= dias < DIAS_REAPERTURA
