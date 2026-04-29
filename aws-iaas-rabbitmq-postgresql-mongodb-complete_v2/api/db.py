import psycopg2                          # Driver de Python para conectarse a PostgreSQL
from psycopg2.extras import RealDictCursor  # Cursor especial que devuelve filas como diccionarios {columna: valor}

from settings import settings            # Importa la configuración centralizada (host, port, user, etc.)


def get_connection():
    """
    Crea y devuelve una conexión nueva a PostgreSQL.
    Se usa como context manager con 'with get_connection() as conn:'
    para que la conexión se cierre automáticamente al salir del bloque.

    RealDictCursor hace que cursor.fetchone() devuelva:
        {"order_id": 1, "description": "test", ...}
    en lugar de una tupla:
        (1, "test", ...)
    lo que facilita acceder a los campos por nombre.
    """
    return psycopg2.connect(
        host=settings.db_host,       # IP del servidor PostgreSQL (EC2 postgres)
        port=settings.db_port,       # Puerto 5432
        dbname=settings.db_name,     # Nombre de la BD: mydb
        user=settings.db_user,       # Usuario: admin
        password=settings.db_password,  # Contraseña
        cursor_factory=RealDictCursor,  # Todas las consultas devuelven dicts en lugar de tuplas
    )
