"""Consultas SQL del Módulo de Tickets. Solo lee y escribe; no aplica reglas."""

POR_PAGINA = 25

_SELECT_TICKET = """
    SELECT t.*, s.nombre AS solicitante_nombre, tec.nombre AS tecnico_nombre
    FROM tickets t
    JOIN usuarios s ON s.id = t.solicitante_id
    LEFT JOIN usuarios tec ON tec.id = t.tecnico_id
"""


def insertar_ticket(con, solicitante_id, datos, fecha):
    cursor = con.execute(
        "INSERT INTO tickets (solicitante_id, asunto, descripcion, categoria, prioridad, estado, fecha_creacion) "
        "VALUES (?, ?, ?, ?, ?, 'Nuevo', ?)",
        (solicitante_id, datos["asunto"], datos["descripcion"], datos["categoria"], datos["prioridad"], fecha),
    )
    ticket_id = cursor.lastrowid
    con.execute("UPDATE tickets SET codigo = ? WHERE id = ?", (f"TK-{ticket_id:06d}", ticket_id))
    return ticket_id


def buscar_por_id(con, ticket_id):
    return con.execute(_SELECT_TICKET + " WHERE t.id = ?", (ticket_id,)).fetchone()


def buscar_usuario(con, usuario_id):
    return con.execute("SELECT id, nombre, rol, activo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()


def tecnicos_activos(con):
    return con.execute(
        "SELECT id, nombre FROM usuarios WHERE rol = 'tecnico' AND activo = 1 ORDER BY nombre"
    ).fetchall()


def listar(con, filtros, pagina=1):
    """Devuelve (filas, total) aplicando los filtros recibidos."""
    condiciones, valores = [], []
    for campo in ("estado", "categoria", "prioridad", "solicitante_id", "tecnico_id"):
        if filtros.get(campo) not in (None, ""):
            condiciones.append(f"t.{campo} = ?")
            valores.append(filtros[campo])
    if filtros.get("desde"):
        condiciones.append("t.fecha_creacion >= ?")
        valores.append(filtros["desde"] + " 00:00:00")
    if filtros.get("hasta"):
        condiciones.append("t.fecha_creacion <= ?")
        valores.append(filtros["hasta"] + " 23:59:59")
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    total = con.execute("SELECT COUNT(*) FROM tickets t" + donde, valores).fetchone()[0]
    filas = con.execute(
        _SELECT_TICKET + donde + " ORDER BY t.fecha_creacion DESC, t.id DESC LIMIT ? OFFSET ?",
        valores + [POR_PAGINA, (pagina - 1) * POR_PAGINA],
    ).fetchall()
    return filas, total


def actualizar(con, ticket_id, **campos):
    asignaciones = ", ".join(f"{nombre} = ?" for nombre in campos)
    con.execute(f"UPDATE tickets SET {asignaciones} WHERE id = ?", list(campos.values()) + [ticket_id])


def registrar_historial(con, ticket_id, usuario_id, tipo, texto, fecha, estado_anterior=None, estado_nuevo=None):
    con.execute(
        "INSERT INTO historial (ticket_id, usuario_id, tipo, estado_anterior, estado_nuevo, texto, fecha) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, usuario_id, tipo, estado_anterior, estado_nuevo, texto, fecha),
    )


def historial(con, ticket_id):
    return con.execute(
        "SELECT h.*, u.nombre AS usuario_nombre FROM historial h JOIN usuarios u ON u.id = h.usuario_id "
        "WHERE h.ticket_id = ? ORDER BY h.fecha, h.id",
        (ticket_id,),
    ).fetchall()
