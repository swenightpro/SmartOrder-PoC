import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging
from config import settings

logger = logging.getLogger(__name__)

class ReadOnlyDatabase:
    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name
            )
            logger.info("PostgreSQL connection pool inizializzato")
        except Exception as e:
            logger.error(f"Errore inizializzazione Postgres pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        # Trasforma i placeholder %s (se usati) in sintassi Postgres
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params or ())
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Errore esecuzione query: {e}")
            raise

db = ReadOnlyDatabase()
