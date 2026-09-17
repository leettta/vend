import datetime
import uuid
from database.db import get_db
from database.models import User, ChargeRequest, Transaction, SystemSetting
from services.log_service import send_discord_log

class ChargeService:
    @staticmethod
    def get_bank_info():
        with get_db() as session:
            bank = session.query(SystemSetting).filter_by(key="bank_name").first()
            account = session.query(SystemSetting).filter_by(key="bank_account").first()
            holder = session.query(SystemSetting).filter_by(key="bank_holder").first()
            return {
                "bank": bank.value if bank else "미등록 은행",
                "account": account.value if account else "000-000-000000",
                "holder": holder.value if holder else "관리자"
            }

    @staticmethod
    def create_request(discord_id: int, username: str, amount: int):
        if amount < 1000:
            return False, "최소 충전 금액은 1,000원 이상이어야 합니다.", None

        with get_db() as session:
            user = session.query(User).filter_by(discord_id=discord_id).first()
            if not user:
                user = User(discord_id=discord_id, username=username, balance=0)
                session.add(user)
                session.flush()

            if user.is_banned:
                return False, "이용 제한된 계정입니다.", None

            # 대기 중인 신청이 이미 있는지 확인 (중복 방지)
            pending = session.query(ChargeRequest).filter_by(user_id=user.id, status="WAITING").first()
            if pending:
                return False, f"이미 대기 중인 충전 신청이 있습니다. (신청번호: {pending.request_number})", None

            req_no = f"CHG-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            req = ChargeRequest(
                request_number=req_no,
                user_id=user.id,
                discord_id=discord_id,
                amount=amount,
                status="WAITING"
            )
            session.add(req)

        # Discord 신청 로그 전송
        send_discord_log(
            log_type="charge_request",
            title="💳 충전 신청 접수",
            fields={
                "신청자": f"{username} (<@{discord_id}>)",
                "신청 금액": f"{amount:,}원",
                "신청 번호": req_no,
                "상태": "대기 중(WAITING)"
            },
            color=0xFEE75C
        )

        return True, "충전 신청이 완료되었습니다.", req_no

    @staticmethod
    def attach_receipt_image(discord_id: int, image_filename: str):
        with get_db() as session:
            user = session.query(User).filter_by(discord_id=discord_id).first()
            if not user:
                return None
            req = session.query(ChargeRequest).filter_by(user_id=user.id, status="WAITING").order_by(ChargeRequest.id.desc()).first()
            if req:
                req.receipt_image = image_filename
                return req.request_number
        return None

    @staticmethod
    def approve_charge(request_id: int, admin_name: str):
        with get_db() as session:
            # Row Lock을 통한 동시 다중 승인 방지
            req = session.query(ChargeRequest).filter_by(id=request_id).with_for_update().first()
            if not req:
                return False, "해당 충전 신청을 찾을 수 없습니다."

            if req.status != "WAITING":
                return False, f"이미 처리된 충전 신청입니다. (현재 상태: {req.status})"

            user = session.query(User).filter_by(id=req.user_id).with_for_update().first()
            if not user:
                return False, "사용자 정보를 찾을 수 없습니다."

            balance_before = user.balance
            user.balance += req.amount
            user.total_charged += req.amount
            balance_after = user.balance

            req.status = "APPROVED"
            req.processed_by = admin_name
            req.processed_at = datetime.datetime.utcnow()

            tx = Transaction(
                user_id=user.id,
                discord_id=user.discord_id,
                type="CHARGE",
                amount=req.amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=req.request_number
            )
            session.add(tx)

            res_info = {
                "discord_id": user.discord_id,
                "amount": req.amount,
                "balance_after": balance_after,
                "request_number": req.request_number
            }

        send_discord_log(
            log_type="charge_approve",
            title="✅ 충전 승인 완료",
            fields={
                "신청자 ID": f"<@{res_info['discord_id']}>",
                "승인 금액": f"{res_info['amount']:,}원",
                "현재 잔액": f"{res_info['balance_after']:,}원",
                "신청 번호": res_info['request_number'],
                "승인 관리자": admin_name
            },
            color=0x57F287
        )

        return True, res_info

    @staticmethod
    def reject_charge(request_id: int, reason: str, admin_name: str):
        with get_db() as session:
            req = session.query(ChargeRequest).filter_by(id=request_id).with_for_update().first()
            if not req:
                return False, "충전 신청을 찾을 수 없습니다."

            if req.status != "WAITING":
                return False, f"이미 처리된 상태입니다. (현재 상태: {req.status})"

            req.status = "REJECTED"
            req.rejection_reason = reason or "관리자 사유 미기재"
            req.processed_by = admin_name
            req.processed_at = datetime.datetime.utcnow()

            user = session.query(User).filter_by(id=req.user_id).first()
            res_info = {
                "discord_id": user.discord_id,
                "amount": req.amount,
                "reason": req.rejection_reason,
                "balance": user.balance if user else 0,
                "request_number": req.request_number
            }

        send_discord_log(
            log_type="charge_reject",
            title="❌ 충전 신청 거절",
            fields={
                "신청자 ID": f"<@{res_info['discord_id']}>",
                "신청 금액": f"{res_info['amount']:,}원",
                "거절 사유": res_info['reason'],
                "신청 번호": res_info['request_number'],
                "담당 관리자": admin_name
            },
            color=0xED4245
        )

        return True, res_info