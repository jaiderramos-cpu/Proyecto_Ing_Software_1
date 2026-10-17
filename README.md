# Sistema de gestión de solicitudes de soporte técnico

Proyecto de Ingeniería de Software I. Aplicación web para registrar, asignar, atender y consultar
solicitudes de soporte (tickets).

De todos los módulos propuestos en el informe, **solo se implementa el Módulo de Tickets**
(registro, consulta, filtros, asignación, cambios de estado, comentarios, cancelación, resolución,
reapertura y cierre). Para poder usarlo existe un inicio de sesión básico con usuarios de ejemplo;
la administración completa de cuentas y los reportes quedan documentados, pero no implementados.

## Requisitos previos

- Python 3.11 o superior
- Git
- Navegador actual: Google Chrome, Microsoft Edge o Mozilla Firefox

## Instalación

```bash
git clone <enlace-del-repositorio>
cd soporte-ti
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

La aplicación lee dos variables de entorno (ambas opcionales):

| Variable | Para qué sirve | Valor por defecto |
|---|---|---|
| `SOPORTE_SECRET_KEY` | Clave para firmar la sesión. En un entorno real debe cambiarse. | `cambiar-esta-clave` |
| `SOPORTE_DB` | Ruta del archivo de base de datos SQLite. | `instance/soporte.db` |

## Ejecución

```bash
flask --app app iniciar-bd      # crea las tablas y los usuarios de ejemplo (solo la primera vez)
flask --app app run             # abre http://127.0.0.1:5000
```

Usuarios de ejemplo (contraseña para todos: `Soporte2026*`):

| Correo | Rol |
|---|---|
| admin@soporte.local | Administrador |
| coordinador@soporte.local | Coordinador |
| tecnico1@soporte.local | Técnico (activo) |
| tecnico2@soporte.local | Técnico (activo) |
| tecnico3@soporte.local | Técnico (inactivo) |
| ana@soporte.local | Solicitante |
| luis@soporte.local | Solicitante |

## Pruebas

```bash
python -m pytest -v
```

Para revisar el tiempo de respuesta con el volumen pedido (30.000 tickets y 500 usuarios):

```bash
python scripts/medir_rendimiento.py
```

## Respaldo y restauración de datos

```bash
flask --app app respaldar-bd    # crea una copia en respaldos/soporte_AAAAMMDD_HHMMSS.db
```

Para restaurar, detenga la aplicación y copie el respaldo elegido sobre `instance/soporte.db`.

## Estructura

```
app/
  __init__.py          arranque de la aplicación
  db.py                conexión y tablas de la base de datos
  autenticacion.py     inicio y cierre de sesión (apoyo mínimo)
  datos_iniciales.py   comandos: iniciar-bd, cargar-volumen, respaldar-bd
  tickets/
    reglas.py          reglas de negocio (estados, transiciones, validaciones)
    repositorio.py     consultas SQL de tickets
    servicio.py        operaciones del módulo y control de permisos
    rutas.py           páginas web del módulo
  templates/           páginas HTML en español
tests/                 casos de prueba automatizados (CP-01 a CP-18)
scripts/               medición de rendimiento
docs/                  informe, casos de prueba y guía de defensa
```
