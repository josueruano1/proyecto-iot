import psycopg2                          # Driver de Python para conectarse a PostgreSQL
from psycopg2.extras import RealDictCursor  # Cursor que devuelve filas como dicts {columna: valor}

from settings import settings            # Configuración centralizada del worker


def get_connection():
    """
    Crea y devuelve una conexión nueva a PostgreSQL para el worker.
    Idéntico a api/db.py — cada componente (API y worker) maneja sus propias conexiones.

    El worker crea una conexión por mensaje procesado (dentro del 'with get_connection()').
    Esto garantiza que errores en un mensaje no afecten el procesamiento de otros mensajes.

    RealDictCursor hace que cursor.fetchone() devuelva:
        {"order_id": 1, "description": "test", ...}
    en lugar de una tupla posicional, facilita acceder a los campos por nombre.
    """
    return psycopg2.connect(
        host=settings.db_host,           # IP del servidor PostgreSQL
        port=settings.db_port,           # Puerto 5432
        dbname=settings.db_name,         # Nombre de la BD: mydb
        user=settings.db_user,           # Usuario: admin
        password=settings.db_password,   # Contraseña
        cursor_factory=RealDictCursor,   # Todas las consultas devuelven dicts
    )
