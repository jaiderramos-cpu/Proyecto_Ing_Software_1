import pytest

from app import create_app
from app.db import conectar, crear_esquema
from app.datos_iniciales import CONTRASENA_DEMO, crear_usuarios_demo
from app.tickets import servicio


@pytest.fixture
def app(tmp_path):
    ruta = tmp_path / "prueba.db"
    aplicacion = create_app({"TESTING": True, "DATABASE": str(ruta), "SECRET_KEY": "pruebas"})
    con = conectar(str(ruta))
    crear_esquema(con)
    crear_usuarios_demo(con)
    con.close()
    return aplicacion


@pytest.fixture
def con(app):
    conexion = conectar(app.config["DATABASE"])
    yield conexion
    conexion.close()


@pytest.fixture
def u(con):
    """Usuarios de ejemplo por nombre corto: admin, coordinador, tecnico1, tecnico3 (inactivo), ana, luis."""
    filas = con.execute("SELECT id, nombre, correo, rol, activo FROM usuarios").fetchall()
    return {f["correo"].split("@")[0]: dict(f) for f in filas}


@pytest.fixture
def cliente(app):
    return app.test_client()


@pytest.fixture
def iniciar_sesion(cliente):
    def _iniciar(correo, contrasena=CONTRASENA_DEMO):
        return cliente.post("/login", data={"correo": correo, "contrasena": contrasena})
    return _iniciar


DATOS_VALIDOS = {
    "asunto": "La impresora del piso 2 no imprime",
    "descripcion": "Desde esta mañana la impresora muestra 'papel atascado' aunque no hay papel.",
    "categoria": "Hardware",
    "prioridad": "Media",
}


def nuevo_ticket(con, usuario, ahora=None, **cambios):
    return servicio.crear(con, usuario, {**DATOS_VALIDOS, **cambios}, ahora=ahora)


def estado_de(con, ticket_id):
    return con.execute("SELECT estado FROM tickets WHERE id = ?", (ticket_id,)).fetchone()["estado"]
