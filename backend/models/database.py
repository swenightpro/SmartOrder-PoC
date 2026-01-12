import mysql.connector
from mysql.connector import Error, pooling
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import logging

from backend.config import settings

logger = logging.getLogger(__name__)


class ReadOnlyDatabase:
    def __init__(self):
        self.pool: Optional[pooling.MySQLConnectionPool] = None
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="readonly_pool",
                pool_size=5,
                pool_reset_session=True,
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
                autocommit=False,
                raise_on_warnings=False,
            )
            logger.info("Database connection pool inizializzato")
        except Error as e:
            logger.error(f"Errore inizializzazione database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.close()
            yield conn
        except Error as e:
            logger.error(f"Errore connessione database: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise ValueError(
                f"Query non permessa in modalità READ-ONLY: {query[:50]}..."
            )
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, params or ())
                results = cursor.fetchall()
                cursor.close()
                return results
        except Error as e:
            logger.error(f"Errore esecuzione query: {e}")
            raise


db = ReadOnlyDatabase()
