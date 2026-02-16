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
        # INIZIALIZZAZIONE VARIABILI (Evita UnboundLocalError)
        meaningful_keywords = []
        if search_params.keywords:
            meaningful_keywords = [kw.lower().strip() for kw in search_params.keywords if len(kw.strip()) > 0]

        try:
            logger.info(f"Ricerca prodotti per cliente {cod_cli} - keywords: {meaningful_keywords}")
            
            effective_limit = search_params.limit or 50
            conditions = []
            params = []
            
            # 1. Filtro Assortimento (Postgres friendly)
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
            
            # 3. Keyword matching (OR logic)
            if meaningful_keywords:
                keyword_conditions = []
                for keyword in meaningful_keywords:
                    keyword_conditions.append("(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s)")
                    params.extend([f"%{keyword}%", f"%{keyword}%"])
                
                conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            # 4. Filtro Categoria
            if search_params.categoria:
                conditions.append("(LOWER(linea) LIKE %s OR LOWER(settore) LIKE %s OR LOWER(famiglia) LIKE %s)")
                cat = f"%{search_params.categoria.lower()}%"
                params.extend([cat, cat, cat])
            
            where_clause = " AND ".join(conditions)
            query = f"""
                SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato, linea, settore, famiglia, sottofamiglia
                FROM anaart
                WHERE {where_clause}
                ORDER BY des_art ASC LIMIT %s
            """
            params.append(effective_limit)
            
            results = db.execute_query(query, tuple(params))
            
            # Se non trovo nulla con la categoria, riprovo senza categoria (Fallback)
            if len(results) == 0 and search_params.categoria and meaningful_keywords:
                logger.info("Nessun risultato con categoria, provo fallback solo su keywords")
                # (Qui potresti ripetere una query semplificata se necessario)

            products = [Product(**row) for row in results]
            logger.info(f"Trovati {len(products)} prodotti per cliente {cod_cli}")
            return products
            
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