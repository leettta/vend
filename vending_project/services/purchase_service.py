import datetime
import uuid
from database.db import get_db
from database.models import User, Product, Inventory, Order, Transaction
from services.log_service import send_discord_log

class PurchaseService:
    @staticmethod
    def process_purchase(discord_id: int, username: str, product_id: int, quantity: int):
        """
        구매 처리 (단일 트랜잭션 보장: 잔액 검증, 재고 확인, 잔액 차감, 재고 차감, 주문 생성)
        """
        if quantity <= 0:
            return False, "수량은 1개 이상이어야 합니다.", None

        with get_db() as session:
            # 1. 사용자 확인 및 밴 여부
            user = session.query(User).filter_by(discord_id=discord_id).with_for_update().first()
            if not user:
                user = User(discord_id=discord_id, username=username, balance=0)
                session.add(user)
                session.flush()

            if user.is_banned:
                return False, "이용이 제한된 사용자입니다. 관리자에게 문의하세요.", None

            # 2. 제품 확인
            product = session.query(Product).filter_by(id=product_id, is_active=True).first()
            if not product:
                return False, "현재 판매 중이지 않은 제품입니다.", None

            total_amount = product.price * quantity

            # 3. 잔액 확인
            if user.balance < total_amount:
                return False, f"잔액이 부족합니다. (필요: {total_amount:,}원 / 보유: {user.balance:,}원)", None

            # 4. 재고 확인 및 선점
            available_items = session.query(Inventory).filter_by(
                product_id=product.id, is_used=False
            ).with_for_update().limit(quantity).all()

            if len(available_items) < quantity:
                return False, f"재고가 부족합니다. (현재 남은 재고: {len(available_items)}개)", None

            # 5. 재고 차감 및 지급 데이터 수집
            now = datetime.datetime.utcnow()
            delivered_codes = []
            for item in available_items:
                item.is_used = True
                item.used_by = discord_id
                item.used_at = now
                delivered_codes.append(item.delivery_data)

            delivery_content = "\n".join(delivered_codes)

            # 6. 잔액 차감
            balance_before = user.balance
            user.balance -= total_amount
            user.total_spent += total_amount
            balance_after = user.balance

            # 7. 주문 생성
            order_no = f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            order = Order(
                order_number=order_no,
                user_id=user.id,
                discord_id=discord_id,
                product_name=product.name,
                quantity=quantity,
                total_amount=total_amount,
                delivery_content=delivery_content,
                status="COMPLETED"
            )
            session.add(order)

            # 8. 거래 로그 생성
            tx = Transaction(
                user_id=user.id,
                discord_id=discord_id,
                type="PURCHASE",
                amount=total_amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=order_no
            )
            session.add(tx)

        # 9. Discord 로그 채널 전송
        send_discord_log(
            log_type="purchase",
            title="🛒 상품 구매 완료",
            fields={
                "구매자": f"{username} (<@{discord_id}>)",
                "제품명": product.name,
                "구매 수량": f"{quantity}개",
                "결제 금액": f"{total_amount:,}원",
                "주문 번호": order_no,
                "남은 잔액": f"{balance_after:,}원"
            },
            color=0x57F287
        )

        return True, "구매가 성공적으로 완료되었습니다.", {
            "order_number": order_no,
            "product_name": product.name,
            "quantity": quantity,
            "total_amount": total_amount,
            "balance_after": balance_after,
            "delivery_content": delivery_content
        }