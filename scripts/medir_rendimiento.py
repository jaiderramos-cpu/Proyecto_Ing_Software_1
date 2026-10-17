"""Mide el tiempo de las consultas habituales en el escenario de RNF-06.

Escenario: 30.000 tickets históricos, 500 usuarios y 10 usuarios consultando al mismo tiempo.
Uso: python scripts/medir_rendimiento.py
"""
import os
import random
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import conectar, crear_esquema  # noqa: E402
from app.datos_iniciales import cargar_volumen  # noqa: E402
from app.tickets import reglas as r  # noqa: E402
from app.tickets import servicio  # noqa: E402

USUARIOS_CONCURRENTES = 10
CONSULTAS_POR_USUARIO = 20
LIMITE_SEGUNDOS = 3.0


def sesion_de_usuario(ruta, numero):
    """Simula a una persona que filtra la lista y abre tickets."""
    azar = random.Random(numero)
    con = conectar(ruta)
    tecnico = dict(con.execute("SELECT id, rol FROM usuarios WHERE rol = 'tecnico' LIMIT 1").fetchone())
    solicitante = dict(con.execute("SELECT id, rol FROM usuarios WHERE rol = 'solicitante' LIMIT 1 OFFSET ?",
                                   (numero,)).fetchone())
    tiempos = []
    for _ in range(CONSULTAS_POR_USUARIO):
        consulta = azar.choice(("filtro", "fechas", "mis_tickets", "detalle"))
        inicio = time.perf_counter()
        if consulta == "filtro":
            servicio.listar(con, tecnico, {"estado": azar.choice(r.ESTADOS), "categoria": azar.choice(r.CATEGORIAS),
                                           "prioridad": azar.choice(r.PRIORIDADES)}, pagina=azar.randint(1, 3))
        elif consulta == "fechas":
            servicio.listar(con, tecnico, {"desde": "2024-06-01", "hasta": "2024-12-31"}, pagina=azar.randint(1, 50))
        elif consulta == "mis_tickets":
            servicio.listar(con, solicitante, {})
        else:
            servicio.consultar(con, tecnico, azar.randint(1, 30000))
        tiempos.append(time.perf_counter() - inicio)
    con.close()
    return tiempos


def main():
    carpeta = tempfile.mkdtemp(prefix="rendimiento_")
    ruta = os.path.join(carpeta, "volumen.db")
    con = conectar(ruta)
    crear_esquema(con)
    print("Cargando escenario de prueba (500 usuarios, 30.000 tickets)...")
    cargar_volumen(con)
    print(f"  usuarios: {con.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]}")
    print(f"  tickets:  {con.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]}")
    con.close()

    print(f"Ejecutando {USUARIOS_CONCURRENTES} usuarios concurrentes x {CONSULTAS_POR_USUARIO} consultas...")
    with ThreadPoolExecutor(max_workers=USUARIOS_CONCURRENTES) as grupo:
        resultados = list(grupo.map(lambda n: sesion_de_usuario(ruta, n), range(USUARIOS_CONCURRENTES)))
    tiempos = sorted(t for lista in resultados for t in lista)
    p95 = tiempos[int(len(tiempos) * 0.95) - 1]
    print(f"  consultas realizadas: {len(tiempos)}")
    print(f"  tiempo promedio:      {statistics.mean(tiempos):.3f} s")
    print(f"  percentil 95:         {p95:.3f} s")
    print(f"  tiempo máximo:        {tiempos[-1]:.3f} s")
    cumple = tiempos[-1] <= LIMITE_SEGUNDOS
    print(f"Resultado RNF-06 (máximo {LIMITE_SEGUNDOS:.0f} s): {'CUMPLE' if cumple else 'NO CUMPLE'}")
    return 0 if cumple else 1


if __name__ == "__main__":
    sys.exit(main())
