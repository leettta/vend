import threading
import time
from database.db import init_database
from bot.main import run_discord_bot
from web.app import app
from config import WEB_PORT

def start_web_server():
    print(f"[Web Admin] Starting at http://127.0.0.1:{WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)

def main():
    print("==================================================")
    print("      Discord Vending Machine System 2026         ")
    print("==================================================")
    # 1. 데이터베이스 테이블 초기화
    init_database()
    print("[Database] SQLite Tables verified & ready.")

    # 2. Flask 웹 관리자 패널 백그라운드 스레드 시작
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(1)

    # 3. 메인 스레드에서 Discord Bot 실행
    print("[Discord Bot] Connecting to Discord Gateway...")
    run_discord_bot()

if __name__ == "__main__":
    main()