import sys
from werkzeug.security import generate_password_hash
from database.db import init_database, get_db
from database.models import Admin, SystemSetting

def create_admin():
    init_database()
    print("=== [자판기 시스템] 최초 관리자 계정 생성 ===")
    username = input("생성할 관리자 아이디를 입력하세요 (기본: admin): ").strip() or "admin"
    password = input("비밀번호를 입력하세요: ").strip()

    if not password:
        print("[오류] 비밀번호는 비어 있을 수 없습니다.")
        return

    with get_db() as db:
        existing = db.query(Admin).filter_by(username=username).first()
        if existing:
            print(f"[경고] 이미 존재하는 아이디입니다. 비밀번호를 새로 갱신합니다.")
            existing.password_hash = generate_password_hash(password)
        else:
            admin = Admin(
                username=username,
                password_hash=generate_password_hash(password)
            )
            db.add(admin)

        # 기본 계좌 정보 초기화
        for k, v in [("bank_name", "토스뱅크"), ("bank_account", "000-0000-0000"), ("bank_holder", "관리자")]:
            if not db.query(SystemSetting).filter_by(key=k).first():
                db.add(SystemSetting(key=k, value=v))

    print(f"\n[성공] 관리자 계정({username})이 등록되었습니다!")
    print("이제 'python run.py'를 실행하여 봇과 웹사이트를 시작할 수 있습니다.")

if __name__ == "__main__":
    create_admin()