"""Модуль для управления конфигурациями поставщиков (Postgres)"""
from typing import Dict, Optional, List

from app.core.db import Database


class SupplierConfigManager:
    """Менеджер конфигураций поставщиков (через Postgres)"""

    def __init__(self):
        self.db = Database.get_instance()
    
    def get_supplier_config(self, supplier_name: str) -> Optional[Dict]:
        return self.db.suppliers_get_config(supplier_name)
    
    def set_supplier_config(self, supplier_name: str, config: Dict):
        self.db.suppliers_set_config(supplier_name, config)
    
    def list_suppliers(self) -> List[str]:
        return self.db.suppliers_list()
    
    def delete_supplier(self, supplier_name: str) -> bool:
        return self.db.suppliers_delete(supplier_name)
    
    def get_default_config(self) -> Dict:
        return {
            'price_list': {
                'start_row': 2,
                'article_col': 0,
                'price_col': 4,
                'quantity_col': 9,
                'sum_col': 10,
            },
            'warehouse_order': {
                'article_col': 0,
                'quantity_col': 9,
                'start_row': 2,
            },
            'preorders': {
                'article_col': 2,
                'article_col2': 5,
                'quantity_col': 4,
                'start_row': 2,
            },
            'price_file': None
        }


