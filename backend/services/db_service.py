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
            # Pulizia e filtraggio keyword
            meaningful_keywords = [kw.lower().strip() for kw in search_params.keywords if len(kw.strip()) > 1]

        try:
            logger.info(f"Ricerca prodotti per cliente {cod_cli} - Keywords originali: {meaningful_keywords}")
            
            effective_limit = search_params.limit or 50
            conditions = []
            params = []
            
            # 1. Filtro Assortimento
            assortment_condition = """
                (
                    NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                    OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
                )
            """
            conditions.append(assortment_condition)
            params.extend([cod_cli, cod_cli])
            
            # 2. Filtro Stato (Articoli attivi)
            conditions.append("(stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))")
            
            # 3. Keyword matching (MIGLIORATO)
            if meaningful_keywords:
                keyword_conditions = []
                for keyword in meaningful_keywords:
                    # Trasformiamo lo spazio in % per trovare "Acqua S. Pellegrino" anche se l'utente scrive "Acqua Pellegrino"
                    fuzzy_kw = f"%{keyword.replace(' ', '%')}%"
                    keyword_conditions.append("(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s OR LOWER(linea) LIKE %s)")
                    params.extend([fuzzy_kw, fuzzy_kw, fuzzy_kw])
                
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
            
            # Se la ricerca specifica non trova nulla, proviamo a restituire 
            # almeno l'assortimento base per non dare "catalogo vuoto" all'IA
            if len(results) == 0 and meaningful_keywords:
                logger.info("Nessun risultato specifico, restituisco assortimento generale del cliente")
                fallback_query = f"""
                    SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato, linea, settore, famiglia, sottofamiglia
                    FROM anaart
                    WHERE {assortment_condition}
                    AND (stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))
                    LIMIT 20
                """
                results = db.execute_query(fallback_query, (cod_cli, cod_cli))

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