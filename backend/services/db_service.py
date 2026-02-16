from typing import List, Optional
import logging

from models.database import db
from models.schemas import Product, OrderHistoryItem, ProductSearchParams

logger = logging.getLogger(__name__)

class DatabaseService:
    @staticmethod
    def search_products(
        cod_cli: int,
        search_params: ProductSearchParams
    ) -> List[Product]:
        meaningful_keywords = []
        if search_params.keywords:
            meaningful_keywords = [kw.lower().strip() for kw in search_params.keywords if len(kw.strip()) > 0]

        try:
            # LOG CRUCIALE: Vediamo cosa arriva dall'IA
            logger.info(f"Ricerca prodotti per cliente {cod_cli} - Keywords: {meaningful_keywords}")
            
            effective_limit = search_params.limit or 50
            conditions = []
            params = []
            
            # 1. Filtro Assortimento (Obbligatorio se esiste un assortimento per il cliente)
            assortment_condition = """
                (
                    NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                    OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
                )
            """
            conditions.append(assortment_condition)
            params.extend([cod_cli, cod_cli])
            
            # 2. Filtro Stato
            conditions.append("(stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))")
            
            # 3. Keyword matching - MODIFICATO: Se non ci sono keyword, NON aggiungiamo questa condizione
            # così la query restituirà tutto l'assortimento disponibile.
            if meaningful_keywords:
                keyword_conditions = []
                for keyword in meaningful_keywords:
                    keyword_conditions.append("(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s OR LOWER(linea) LIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                
                conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            where_clause = " AND ".join(conditions)
            query = f"""
                SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, 
                       stato, linea, settore, famiglia, sottofamiglia
                FROM anaart
                WHERE {where_clause}
                ORDER BY des_art ASC
                LIMIT %s
            """
            params.append(effective_limit)
            
            results = db.execute_query(query, tuple(params))
            logger.info(f"Risultati query database: {len(results)} righe trovate")
            
            return [Product(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Errore ricerca prodotti: {e}", exc_info=True)
            return []

    @staticmethod
    def get_order_history(cod_cli: int, limit: int = 10) -> List[OrderHistoryItem]:
        try:
            logger.info(f"Recupero storico ordini per cliente {cod_cli}")
            query = """
                SELECT o.cod_art, a.des_art, o.data_ord, o.qta_ordinata, a.des_um
                FROM ordclidet o
                LEFT JOIN anaart a ON o.cod_art = a.cod_art
                WHERE o.cod_cli = %s
                ORDER BY o.data_ord DESC, o.id DESC LIMIT %s
            """
            results = db.execute_query(query, (cod_cli, limit))
            return [OrderHistoryItem.from_db_row(row) for row in results]
        except Exception as e:
            logger.error(f"Errore recupero storico: {e}")
            return []