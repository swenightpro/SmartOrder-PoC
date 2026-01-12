from typing import List, Optional
import logging

from backend.models.database import db
from backend.models.schemas import Product, OrderHistoryItem, ProductSearchParams

logger = logging.getLogger(__name__)


class DatabaseService:
    @staticmethod
    def search_products(
        cod_cli: int,
        search_params: ProductSearchParams
    ) -> List[Product]:
        try:
            logger.info(f"Ricerca prodotti per cliente {cod_cli} - keywords: {search_params.keywords}")
            
            effective_limit = search_params.limit
            
            conditions = []
            params = []
            
            assortment_condition = """
                (
                    NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                    OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
                )
            """
            conditions.append(assortment_condition)
            params.extend([cod_cli, cod_cli])
            
            conditions.append("(stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))")
            
            if search_params.keywords:
                meaningful_keywords = [kw.lower().strip() for kw in search_params.keywords if len(kw.strip()) > 0]
                
                if meaningful_keywords:
                    keyword_conditions = []
                    for keyword in meaningful_keywords:
                        keyword_conditions.append(
                            "(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s)"
                        )
                        params.extend([f"%{keyword}%", f"%{keyword}%"])
                    
                    keyword_conditions_str = " OR ".join(keyword_conditions)
                    conditions.append(f"({keyword_conditions_str})")
            
            if search_params.categoria:
                categoria_condition = (
                    "(LOWER(linea) LIKE %s OR LOWER(settore) LIKE %s OR LOWER(famiglia) LIKE %s OR LOWER(sottofamiglia) LIKE %s)"
                )
                categoria_param = f"%{search_params.categoria.lower()}%"
                params.extend([categoria_param, categoria_param, categoria_param, categoria_param])
                conditions.append(categoria_condition)
            
            if search_params.tipo_um:
                conditions.append("tipo_um = %s")
                params.append(search_params.tipo_um.upper())
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT 
                    cod_art, des_art, des_um, pezzi_conf, des_tipo_um, 
                    stato, linea, settore, famiglia, sottofamiglia
                FROM anaart
                WHERE {where_clause}
                ORDER BY des_art ASC
                LIMIT %s
            """
            params.append(effective_limit)
            
            results = db.execute_query(query, tuple(params))
            logger.info(f"Risultati query: {len(results)} righe")
            
            if len(results) > 20 and len(meaningful_keywords) >= 2:
                logger.info(f"Troppi risultati ({len(results)}), provo ricerca più precisa (AND)")
                
                conditions_refined = []
                params_refined = []
                
                conditions_refined.append(assortment_condition)
                params_refined.extend([cod_cli, cod_cli])
                conditions_refined.append("(stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))")
                
                keyword_conditions_refined = []
                for keyword in meaningful_keywords:
                    keyword_conditions_refined.append(
                        "(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s)"
                    )
                    params_refined.extend([f"%{keyword}%", f"%{keyword}%"])
                
                keyword_conditions_str_refined = " AND ".join(keyword_conditions_refined)
                conditions_refined.append(f"({keyword_conditions_str_refined})")
                
                if search_params.categoria:
                    categoria_condition_refined = (
                        "(LOWER(linea) LIKE %s OR LOWER(settore) LIKE %s OR LOWER(famiglia) LIKE %s OR LOWER(sottofamiglia) LIKE %s)"
                    )
                    categoria_param_refined = f"%{search_params.categoria.lower()}%"
                    params_refined.extend([categoria_param_refined, categoria_param_refined, categoria_param_refined, categoria_param_refined])
                    conditions_refined.append(categoria_condition_refined)
                
                where_clause_refined = " AND ".join(conditions_refined)
                query_refined = f"""
                    SELECT 
                        cod_art, des_art, des_um, pezzi_conf, des_tipo_um, 
                        stato, linea, settore, famiglia, sottofamiglia
                    FROM anaart
                    WHERE {where_clause_refined}
                    ORDER BY des_art ASC
                    LIMIT %s
                """
                params_refined.append(effective_limit)
                
                results_refined = db.execute_query(query_refined, tuple(params_refined))
                logger.info(f"Risultati ricerca raffinata (AND): {len(results_refined)} righe")
                
                if len(results_refined) > 0:
                    results = results_refined
                    logger.info("Usando risultati raffinati")
            
            if len(results) == 0 and search_params.categoria:
                keywords_for_fallback = meaningful_keywords if len(meaningful_keywords) > 0 else [
                    kw.lower().strip() 
                    for kw in search_params.keywords 
                    if len(kw.strip()) > 0
                ]
                
                if len(keywords_for_fallback) > 0:
                    logger.info(f"Nessun risultato con categoria, riprovo senza filtro categoria")
                    
                    conditions_fallback = []
                    params_fallback = []
                    
                    conditions_fallback.append(assortment_condition)
                    params_fallback.extend([cod_cli, cod_cli])
                    conditions_fallback.append("(stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))")
                    
                    keyword_conditions_fallback = []
                    for keyword in keywords_for_fallback:
                        keyword_conditions_fallback.append(
                            "(LOWER(des_art) LIKE %s OR LOWER(cod_art) LIKE %s)"
                        )
                        params_fallback.extend([f"%{keyword}%", f"%{keyword}%"])
                    keyword_conditions_str_fallback = " AND ".join(keyword_conditions_fallback)
                    conditions_fallback.append(f"({keyword_conditions_str_fallback})")
                    
                    where_clause_fallback = " AND ".join(conditions_fallback)
                    query_fallback = f"""
                        SELECT 
                            cod_art, des_art, des_um, pezzi_conf, des_tipo_um, 
                            stato, linea, settore, famiglia, sottofamiglia
                        FROM anaart
                        WHERE {where_clause_fallback}
                        ORDER BY des_art ASC
                        LIMIT %s
                    """
                    params_fallback.append(effective_limit)
                    
                    results = db.execute_query(query_fallback, tuple(params_fallback))
                    logger.info(f"Risultati query fallback: {len(results)} righe")
            
            if len(results) == 0 and len(meaningful_keywords) > 0:
                logger.info("Nessun risultato con ricerca esatta, provo fuzzy matching")
                fuzzy_results = DatabaseService._search_fuzzy(
                    cod_cli, meaningful_keywords, effective_limit
                )
                if fuzzy_results:
                    results = fuzzy_results
                    logger.info(f"Fuzzy matching trovato {len(results)} risultati")
            
            products = [Product(**row) for row in results]
            logger.info(f"Trovati {len(products)} prodotti per cliente {cod_cli}")
            return products
            
        except Exception as e:
            logger.error(f"Errore ricerca prodotti: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _search_fuzzy(
        cod_cli: int,
        keywords: List[str],
        limit: int = 10
    ) -> List[dict]:
        try:
            if not keywords:
                return []
            
            significant_keywords_sorted = sorted(keywords, key=len, reverse=True)
            
            for keyword in significant_keywords_sorted:
                query = """
                    SELECT 
                        cod_art, des_art, des_um, pezzi_conf, des_tipo_um, 
                        stato, linea, settore, famiglia, sottofamiglia
                    FROM anaart
                    WHERE 
                        (
                            NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                            OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
                        )
                        AND (stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))
                        AND SOUNDEX(LOWER(des_art)) = SOUNDEX(%s)
                    ORDER BY des_art ASC
                    LIMIT %s
                """
                
                params = (cod_cli, cod_cli, keyword, limit)
                fuzzy_results = db.execute_query(query, params)
                
                if fuzzy_results:
                    logger.info(f"Fuzzy matching trovato {len(fuzzy_results)} risultati per '{keyword}'")
                    return fuzzy_results
            
            return []
            
        except Exception as e:
            logger.error(f"Errore fuzzy matching: {e}", exc_info=True)
            return []
    
    @staticmethod
    def get_order_history(cod_cli: int, limit: int = 10) -> List[OrderHistoryItem]:
        try:
            logger.info(f"Recupero storico ordini per cliente {cod_cli}")
            
            query = """
                SELECT 
                    o.cod_art,
                    a.des_art,
                    o.data_ord,
                    o.qta_ordinata,
                    a.des_um
                FROM ordclidet o
                LEFT JOIN anaart a ON o.cod_art = a.cod_art
                WHERE o.cod_cli = %s
                ORDER BY o.data_ord DESC, o.id DESC
                LIMIT %s
            """
            
            results = db.execute_query(query, (cod_cli, limit))
            logger.info(f"Storico ordini trovati: {len(results)} righe")
            
            history = [OrderHistoryItem.from_db_row(row) for row in results]
            return history
            
        except Exception as e:
            logger.error(f"Errore recupero storico ordini: {e}", exc_info=True)
            return []
