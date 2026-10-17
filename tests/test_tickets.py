"""Casos de prueba CP-01 a CP-18 del Módulo de Tickets.

Cada prueba indica en su descripción el requisito o la regla que verifica.
"""
import sqlite3
from datetime import datetime, timedelta

import pytest

from app.tickets import reglas as r
from app.tickets import repositorio, servicio
from conftest import DATOS_VALIDOS, estado_de, nuevo_ticket

AHORA = datetime(2026, 10, 1, 9, 0, 0)


def _ticket_en_progreso(con, u):
    tid = nuevo_ticket(con, u["ana"])
    servicio.asignar(con, u["coordinador"], tid, u["tecnico1"]["id"])
    servicio.cambiar_estado(con, u["tecnico1"], tid, r.EN_PROGRESO, "Revisando el equipo.")
    return tid


def _ticket_resuelto(con, u, cuando=AHORA):
    tid = _ticket_en_progreso(con, u)
    servicio.cambiar_estado(con, u["tecnico1"], tid, r.RESUELTO, "Se reemplazó el cable de red.", ahora=cuando)
    return tid


def test_cp01_crear_ticket_valido(con, u):
    """CP-01 · RF-03, RF-04, RN-01: un ticket válido queda en estado Nuevo con código único."""
    t1 = nuevo_ticket(con, u["ana"], ahora=None)
    t2 = nuevo_ticket(con, u["luis"])
    fila = repositorio.buscar_por_id(con, t1)
    assert fila["estado"] == r.NUEVO
    assert fila["codigo"] == f"TK-{t1:06d}"
    assert fila["codigo"] != repositorio.buscar_por_id(con, t2)["codigo"]
    assert fila["solicitante_id"] == u["ana"]["id"] and fila["fecha_creacion"]


@pytest.mark.parametrize("campo,valor", [("asunto", ""), ("asunto", "   "), ("descripcion", ""), ("descripcion", "\n\t ")])
def test_cp02_asunto_y_descripcion_obligatorios(con, u, campo, valor):
    """CP-02 · RN-02, RNF-10: no se aceptan asunto ni descripción vacíos o con solo espacios."""
    with pytest.raises(r.ErrorValidacion):
        nuevo_ticket(con, u["ana"], **{campo: valor})
    assert con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0


@pytest.mark.parametrize("campo,valor", [("prioridad", "Urgente"), ("prioridad", ""), ("categoria", "Cafetería")])
def test_cp03_prioridad_y_categoria_validas(con, u, campo, valor):
    """CP-03 · RN-03, RNF-10: solo se aceptan las prioridades Baja, Media, Alta, Crítica y categorías de la lista."""
    with pytest.raises(r.ErrorValidacion):
        nuevo_ticket(con, u["ana"], **{campo: valor})


def test_cp04_limite_longitud_asunto(con, u):
    """CP-04 · RNF-10 (valor límite): 150 caracteres se aceptan, 151 se rechazan."""
    assert nuevo_ticket(con, u["ana"], asunto="A" * 150)
    with pytest.raises(r.ErrorValidacion):
        nuevo_ticket(con, u["ana"], asunto="A" * 151)


def test_cp05_coordinador_asigna_a_tecnico_activo(con, u):
    """CP-05 · RF-06, RN-06: el coordinador asigna un ticket Nuevo a un técnico activo."""
    tid = nuevo_ticket(con, u["ana"])
    servicio.asignar(con, u["coordinador"], tid, u["tecnico1"]["id"])
    fila = repositorio.buscar_por_id(con, tid)
    assert fila["estado"] == r.ASIGNADO and fila["tecnico_id"] == u["tecnico1"]["id"]


@pytest.mark.parametrize("destino", ["tecnico3", "ana"])
def test_cp06_no_asignar_a_inactivo_ni_a_no_tecnico(con, u, destino):
    """CP-06 · RN-06: no se asigna a técnicos inactivos ni a usuarios que no son técnicos."""
    tid = nuevo_ticket(con, u["ana"])
    with pytest.raises(r.ErrorValidacion):
        servicio.asignar(con, u["admin"], tid, u[destino]["id"])
    assert estado_de(con, tid) == r.NUEVO


@pytest.mark.parametrize("quien", ["ana", "tecnico1"])
def test_cp07_usuario_sin_privilegios_no_asigna(con, u, cliente, iniciar_sesion, quien):
    """CP-07 · RN-06, RNF-04, SC-01: aunque se envíe la petición directa al servidor, solo admin/coordinador asignan."""
    tid = nuevo_ticket(con, u["ana"])
    iniciar_sesion(u[quien]["correo"])
    respuesta = cliente.post(f"/tickets/{tid}/asignar", data={"tecnico_id": u["tecnico1"]["id"]})
    assert respuesta.status_code == 403
    assert estado_de(con, tid) == r.NUEVO


def test_cp08_flujo_completo_de_estados(con, u):
    """CP-08 · RN-05, RF-07, RF-10: recorrido normal Nuevo → … → Cerrado."""
    tid = _ticket_en_progreso(con, u)
    servicio.cambiar_estado(con, u["tecnico1"], tid, r.PENDIENTE, "¿Puede indicar el número de inventario?")
    servicio.complementar(con, u["ana"], tid, "Inventario 2024-0915")
    servicio.cambiar_estado(con, u["tecnico1"], tid, r.EN_PROGRESO)
    servicio.cambiar_estado(con, u["tecnico1"], tid, r.RESUELTO, "Se actualizó el controlador.")
    servicio.cerrar(con, u["ana"], tid)
    estados = [h["estado_nuevo"] for h in repositorio.historial(con, tid) if h["estado_nuevo"]]
    assert estados == [r.NUEVO, r.ASIGNADO, r.EN_PROGRESO, r.PENDIENTE, r.EN_PROGRESO, r.RESUELTO, r.CERRADO]


def test_cp09_transicion_invalida_no_cambia_ticket(con, u):
    """CP-09 · RN-05, RN-12: Asignado → Resuelto no está permitido; el ticket queda igual."""
    tid = nuevo_ticket(con, u["ana"])
    servicio.asignar(con, u["coordinador"], tid, u["tecnico1"]["id"])
    with pytest.raises(r.ErrorValidacion):
        servicio.cambiar_estado(con, u["tecnico1"], tid, r.RESUELTO, "Arreglado")
    with pytest.raises(r.ErrorValidacion):
        servicio.cambiar_estado(con, u["tecnico1"], tid, r.CERRADO)
    assert estado_de(con, tid) == r.ASIGNADO


def test_cp10_resolver_exige_solucion(con, u):
    """CP-10 · RN-08: para pasar a Resuelto hay que describir la solución."""
    tid = _ticket_en_progreso(con, u)
    with pytest.raises(r.ErrorValidacion):
        servicio.cambiar_estado(con, u["tecnico1"], tid, r.RESUELTO, "   ")
    assert estado_de(con, tid) == r.EN_PROGRESO


def test_cp11_cancelacion_por_el_solicitante(con, u):
    """CP-11 · RF-09, RN-07: se cancela solo en estado Nuevo, con motivo y por su dueño."""
    tid = nuevo_ticket(con, u["ana"])
    with pytest.raises(r.ErrorValidacion):
        servicio.cancelar(con, u["ana"], tid, "")
    with pytest.raises(r.ErrorPermiso):
        servicio.cancelar(con, u["luis"], tid, "No es mío")
    servicio.cancelar(con, u["ana"], tid, "Ya se solucionó solo")
    assert estado_de(con, tid) == r.CANCELADO

    otro = nuevo_ticket(con, u["ana"])
    servicio.asignar(con, u["coordinador"], otro, u["tecnico1"]["id"])
    with pytest.raises(r.ErrorValidacion):
        servicio.cancelar(con, u["ana"], otro, "Ya no lo necesito")
    assert estado_de(con, otro) == r.ASIGNADO


def test_cp12_solicitante_solo_ve_y_complementa_lo_suyo(con, u, cliente, iniciar_sesion):
    """CP-12 · RF-08, RN-07, RF-13: un solicitante no ve tickets ajenos ni complementa tickets cerrados."""
    de_luis = nuevo_ticket(con, u["luis"])
    iniciar_sesion(u["ana"]["correo"])
    assert cliente.get(f"/tickets/{de_luis}").status_code == 403
    with pytest.raises(r.ErrorPermiso):
        servicio.complementar(con, u["ana"], de_luis, "Dato extra")
    filas, total = servicio.listar(con, u["ana"], {})
    assert total == 0

    tid = _ticket_resuelto(con, u)
    servicio.cerrar(con, u["ana"], tid)
    with pytest.raises(r.ErrorValidacion):
        servicio.complementar(con, u["ana"], tid, "Otra cosa")


@pytest.mark.parametrize("dias,permitido", [(0, True), (5, True), (6, False)])
def test_cp13_plazo_de_reapertura(con, u, dias, permitido):
    """CP-13 · RF-11, RN-09 (valores límite): se reabre hasta el día 5 después de resolver; el día 6 no."""
    tid = _ticket_resuelto(con, u, cuando=AHORA)
    momento = AHORA + timedelta(days=dias, hours=8)
    if permitido:
        servicio.reabrir(con, u["ana"], tid, "Volvió a fallar", ahora=momento)
        assert estado_de(con, tid) == r.EN_PROGRESO
    else:
        with pytest.raises(r.ErrorValidacion):
            servicio.reabrir(con, u["ana"], tid, "Volvió a fallar", ahora=momento)
        assert estado_de(con, tid) == r.RESUELTO


def test_cp14_estados_finales_no_cambian(con, u):
    """CP-14 · RN-10, RN-12: Cerrado y Cancelado son finales y el historial se conserva."""
    cerrado = _ticket_resuelto(con, u)
    servicio.cerrar(con, u["ana"], cerrado)
    cancelado = nuevo_ticket(con, u["ana"])
    servicio.cancelar(con, u["ana"], cancelado, "Duplicado")
    for tid, estado in ((cerrado, r.CERRADO), (cancelado, r.CANCELADO)):
        for intento in (
            lambda: servicio.reabrir(con, u["ana"], tid, "otra vez"),
            lambda: servicio.comentar(con, u["admin"], tid, "nota"),
            lambda: servicio.asignar(con, u["admin"], tid, u["tecnico1"]["id"]),
        ):
            with pytest.raises(r.ErrorValidacion):
                intento()
        assert estado_de(con, tid) == estado
        assert len(repositorio.historial(con, tid)) >= 2


def test_cp15_operacion_atomica_ante_error(con, u, monkeypatch):
    """CP-15 · RNF-05: si falla el registro del historial, el cambio de estado se deshace."""
    tid = nuevo_ticket(con, u["ana"])

    def falla(*_a, **_k):
        raise sqlite3.OperationalError("disco lleno (simulado)")

    monkeypatch.setattr(repositorio, "registrar_historial", falla)
    with pytest.raises(sqlite3.OperationalError):
        servicio.asignar(con, u["coordinador"], tid, u["tecnico1"]["id"])
    fila = repositorio.buscar_por_id(con, tid)
    assert fila["estado"] == r.NUEVO and fila["tecnico_id"] is None


def test_cp16_tecnico_no_asignado_no_modifica(con, u):
    """CP-16 · RF-07, RN-11, RF-13: un técnico solo cambia estado y comenta tickets que tiene asignados."""
    tid = nuevo_ticket(con, u["ana"])
    servicio.asignar(con, u["coordinador"], tid, u["tecnico1"]["id"])
    with pytest.raises(r.ErrorPermiso):
        servicio.cambiar_estado(con, u["tecnico2"], tid, r.EN_PROGRESO)
    with pytest.raises(r.ErrorPermiso):
        servicio.comentar(con, u["tecnico2"], tid, "Yo lo reviso")
    assert estado_de(con, tid) == r.ASIGNADO


def test_cp17_filtros_de_consulta(con, u):
    """CP-17 · RF-05: filtrar por estado, categoría, prioridad y rango de fechas."""
    nuevo_ticket(con, u["ana"], categoria="Red", prioridad="Alta", ahora=datetime(2026, 9, 10, 8))
    nuevo_ticket(con, u["luis"], categoria="Red", prioridad="Baja", ahora=datetime(2026, 9, 20, 8))
    nuevo_ticket(con, u["luis"], categoria="Software", prioridad="Alta", ahora=datetime(2026, 9, 25, 8))
    tecnico = u["tecnico1"]
    assert servicio.listar(con, tecnico, {"categoria": "Red"})[1] == 2
    assert servicio.listar(con, tecnico, {"prioridad": "Alta"})[1] == 2
    assert servicio.listar(con, tecnico, {"estado": "Nuevo", "categoria": "Red", "prioridad": "Alta"})[1] == 1
    assert servicio.listar(con, tecnico, {"desde": "2026-09-15", "hasta": "2026-09-25"})[1] == 2
    with pytest.raises(r.ErrorValidacion):
        servicio.listar(con, tecnico, {"desde": "15/09/2026"})
    with pytest.raises(r.ErrorValidacion):
        servicio.listar(con, tecnico, {"estado": "Perdido"})


def test_cp18_inicio_de_sesion_y_contrasenas(con, u, cliente, iniciar_sesion):
    """CP-18 · RF-01, RNF-03, RNF-07: login correcto e incorrecto, contraseñas con hash y mensajes sin detalles internos."""
    malo = iniciar_sesion("ana@soporte.local", "clave-equivocada")
    assert malo.status_code == 401
    assert "Correo o contraseña incorrectos." in malo.get_data(as_text=True)
    assert iniciar_sesion("tecnico3@soporte.local").status_code == 401   # cuenta inactiva
    hash_guardado = con.execute("SELECT hash_contrasena FROM usuarios WHERE correo = 'ana@soporte.local'").fetchone()[0]
    assert "Soporte2026*" not in hash_guardado and hash_guardado.startswith(("scrypt:", "pbkdf2:"))

    assert iniciar_sesion("ana@soporte.local").status_code == 302
    pagina = cliente.get("/tickets/999999")
    texto = pagina.get_data(as_text=True)
    assert pagina.status_code == 404 and "SELECT" not in texto and "Traceback" not in texto
    cliente.post("/logout")
    assert cliente.get("/tickets/").status_code == 302
