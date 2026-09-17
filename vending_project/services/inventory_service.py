from database.db import get_db
from database.models import Product, Inventory

class InventoryService:
    @staticmethod
    def get_active_products():
        with get_db() as session:
            products = session.query(Product).filter_by(is_active=True).all()
            res = []
            for p in products:
                stock_count = session.query(Inventory).filter_by(product_id=p.id, is_used=False).count()
                res.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": p.price,
                    "image_url": p.image_url,
                    "stock": stock_count,
                    "is_active": p.is_active
                })
            return res

    @staticmethod
    def get_product_details(product_id: int):
        with get_db() as session:
            p = session.query(Product).filter_by(id=product_id).first()
            if not p:
                return None
            stock_count = session.query(Inventory).filter_by(product_id=p.id, is_used=False).count()
            return {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": p.price,
                "image_url": p.image_url,
                "stock": stock_count,
                "is_active": p.is_active
            }

    @staticmethod
    def add_bulk_stock(product_id: int, items_text: str):
        lines = [line.strip() for line in items_text.splitlines() if line.strip()]
        if not lines:
            return 0
        with get_db() as session:
            for item in lines:
                inv = Inventory(product_id=product_id, delivery_data=item, is_used=False)
                session.add(inv)
        return len(lines)