"""Модуль для сопоставления товаров и генерации заказов"""
from typing import Dict, Optional
from app.excel.excel_processor import ExcelProcessor


class OrderGenerator:
    def __init__(self, price_config: Dict):
        self.price_config = price_config

    def read_price_list(self, file_path: str) -> Dict[str, Dict]:
        processor = ExcelProcessor(file_path)
        processor.read_file()
        data = processor.get_all_data()
        price_items = {}
        start_row = self.price_config.get('start_row', 2)
        article_col = self.price_config.get('article_col', 0)
        for row_idx in range(start_row, len(data)):
            row = data[row_idx]
            if article_col < len(row) and row[article_col]:
                article = str(row[article_col]).strip()
                if article:
                    price_items[article] = {'row': row_idx, 'data': row}
        processor.close()
        return price_items

    def read_warehouse_order(self, file_path: str, config: Dict) -> Dict[str, float]:
        processor = ExcelProcessor(file_path)
        processor.read_file()
        data = processor.get_all_data()
        quantities = {}
        start_row = config.get('start_row', 2)
        article_col = config.get('article_col', 0)
        quantity_col = config.get('quantity_col', 9)
        for row_idx in range(start_row, len(data)):
            row = data[row_idx]
            if article_col < len(row) and row[article_col]:
                article = str(row[article_col]).strip()
                if article:
                    qty = 0
                    if quantity_col < len(row) and row[quantity_col]:
                        try:
                            qty = float(row[quantity_col])
                        except (ValueError, TypeError):
                            qty = 0
                    if qty > 0:
                        quantities[article] = qty
        processor.close()
        return quantities

    def read_preorders(self, file_path: str, config: Dict) -> Dict[str, float]:
        processor = ExcelProcessor(file_path)
        processor.read_file()
        data = processor.get_all_data()
        quantities = {}
        start_row = config.get('start_row', 2)
        article_col = config.get('article_col', 2)
        article_col2 = config.get('article_col2', 5)
        quantity_col = config.get('quantity_col', 4)
        for row_idx in range(start_row, len(data)):
            row = data[row_idx]
            if not row or len(row) == 0:
                continue
            article = None
            if article_col2 < len(row) and row[article_col2]:
                article = str(row[article_col2]).strip()
            if not article and article_col < len(row) and row[article_col]:
                article = str(row[article_col]).strip()
            if article:
                qty = 0
                if quantity_col < len(row) and row[quantity_col]:
                    try:
                        qty = float(row[quantity_col])
                    except (ValueError, TypeError):
                        qty = 0
                if qty > 0:
                    if article in quantities:
                        quantities[article] += qty
                    else:
                        quantities[article] = qty
        processor.close()
        return quantities

    def generate_order(self, price_file: str, warehouse_file: str, preorders_file: str,
                      output_file: str, warehouse_config: Dict, preorders_config: Dict,
                      price_template: Optional[str] = None):
        price_items = self.read_price_list(price_file)
        warehouse_quantities = self.read_warehouse_order(warehouse_file, warehouse_config)
        preorder_quantities = self.read_preorders(preorders_file, preorders_config)
        final_quantities: Dict[str, float] = {}
        all_articles = set(list(warehouse_quantities.keys()) + list(preorder_quantities.keys()))
        for article in all_articles:
            warehouse_qty = warehouse_quantities.get(article, 0)
            preorder_qty = preorder_quantities.get(article, 0)
            if warehouse_qty == 0:
                final_qty = preorder_qty
            elif preorder_qty == 0:
                final_qty = warehouse_qty
            else:
                final_qty = warehouse_qty + preorder_qty
            if final_qty > 0:
                final_quantities[article] = final_qty
        processor = ExcelProcessor(price_file)
        processor.read_file()
        data = processor.get_all_data()
        quantity_col = self.price_config.get('quantity_col', 9)
        article_col = self.price_config.get('article_col', 0)
        price_col = self.price_config.get('price_col')
        sum_col = self.price_config.get('sum_col')
        start_row = self.price_config.get('start_row', 2)
        total_row = None
        total_count_enabled = False
        # Для сохранения форматирования используем исходный шаблон, если он есть
        template = price_template or price_file
        processor.write_file(output_file, data, quantity_col, final_quantities,
                             article_col, start_row, price_col, sum_col, template, total_row, total_count_enabled)
        processor.close()
        return final_quantities


