import os
import asyncio
import functools
import discord
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
)
from werkzeug.security import check_password_hash
from config import SECRET_KEY, UPLOAD_FOLDER, WEB_PORT
from database.db import get_db
from database.models import (
    Admin, User, Product, Inventory, Order, ChargeRequest, LogSetting, SystemSetting, SystemLog
)
from services.charge_service import ChargeService
from services.inventory_service import InventoryService
from services.log_service import bot_instance, record_system_log, send_discord_log

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ----------------- 인증 데코레이터 -----------------
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

# ----------------- 인증 라우트 -----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        with get_db() as db:
            admin = db.query(Admin).filter_by(username=username).first()
            if admin and check_password_hash(admin.password_hash, password):
                session.clear()
                session["admin_id"] = admin.id
                session["admin_username"] = admin.username
                record_system_log("LOGIN", f"관리자 '{username}' 로그인", admin.username)
                return redirect(url_for("dashboard"))
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    name = session.get("admin_username", "Unknown")
    record_system_log("LOGOUT", f"관리자 '{name}' 로그아웃", name)
    session.clear()
    return redirect(url_for("login"))

# ----------------- 대시보드 -----------------
@app.route("/")
@login_required
def dashboard():
    with get_db() as db:
        total_users = db.query(User).count()
        total_products = db.query(Product).count()
        total_orders = db.query(Order).count()
        
        # 총 매출 계산
        orders = db.query(Order).all()
        total_sales = sum(o.total_amount for o in orders)

        waiting_charges = db.query(ChargeRequest).filter_by(status="WAITING").count()
        recent_charges = db.query(ChargeRequest).order_by(ChargeRequest.id.desc()).limit(5).all()
        recent_orders = db.query(Order).order_by(Order.id.desc()).limit(5).all()
        recent_logs = db.query(SystemLog).order_by(SystemLog.id.desc()).limit(5).all()

        return render_template(
            "dashboard.html",
            total_users=total_users,
            total_products=total_products,
            total_orders=total_orders,
            total_sales=total_sales,
            waiting_charges=waiting_charges,
            recent_charges=recent_charges,
            recent_orders=recent_orders,
            recent_logs=recent_logs
        )

# ----------------- 충전 관리 -----------------
@app.route("/charges")
@login_required
def charges():
    status = request.args.get("status", "ALL")
    with get_db() as db:
        query = db.query(ChargeRequest)
        if status != "ALL":
            query = query.filter_by(status=status)
        charge_list = query.order_by(ChargeRequest.id.desc()).all()
        return render_template("charges.html", charges=charge_list, current_status=status)

@app.route("/charges/<int:req_id>")
@login_required
def charge_detail(req_id):
    with get_db() as db:
        charge = db.query(ChargeRequest).filter_by(id=req_id).first()
        if not charge:
            flash("존재하지 않는 충전 신청입니다.", "danger")
            return redirect(url_for("charges"))
        return render_template("charge_detail.html", charge=charge)

@app.route("/charges/<int:req_id>/approve", methods=["POST"])
@login_required
def charge_approve(req_id):
    admin_name = session.get("admin_username", "Admin")
    success, info = ChargeService.approve_charge(req_id, admin_name)

    if not success:
        flash(f"승인 실패: {info}", "danger")
        return redirect(url_for("charge_detail", req_id=req_id))

    record_system_log("CHARGE_APPROVE", f"충전 승인 #{info['request_number']} 금액: {info['amount']:,}원", admin_name)

    # Discord DM 알림 발송
    if bot_instance and bot_instance.is_ready():
        async def _notify_user():
            try:
                user = await bot_instance.fetch_user(info["discord_id"])
                if user:
                    embed = discord.Embed(title="✅ 충전이 승인되었습니다", color=0x57F287)
                    embed.add_field(name="충전 금액", value=f"{info['amount']:,}원", inline=True)
                    embed.add_field(name="현재 잔액", value=f"{info['balance_after']:,}원", inline=True)
                    embed.add_field(name="신청 번호", value=info["request_number"], inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"[DM Error] {e}")
        asyncio.run_coroutine_threadsafe(_notify_user(), bot_instance.loop)

    flash("충전 신청이 성공적으로 승인되었습니다.", "success")
    return redirect(url_for("charges"))

@app.route("/charges/<int:req_id>/reject", methods=["POST"])
@login_required
def charge_reject(req_id):
    admin_name = session.get("admin_username", "Admin")
    reason = request.form.get("reason", "입금 내역 불일치").strip()
    success, info = ChargeService.reject_charge(req_id, reason, admin_name)

    if not success:
        flash(f"거절 실패: {info}", "danger")
        return redirect(url_for("charge_detail", req_id=req_id))

    record_system_log("CHARGE_REJECT", f"충전 거절 #{info['request_number']} 사유: {reason}", admin_name)

    if bot_instance and bot_instance.is_ready():
        async def _notify_user():
            try:
                user = await bot_instance.fetch_user(info["discord_id"])
                if user:
                    embed = discord.Embed(title="❌ 충전 신청이 거절되었습니다", color=0xED4245)
                    embed.add_field(name="신청 금액", value=f"{info['amount']:,}원", inline=True)
                    embed.add_field(name="현재 잔액", value=f"{info['balance']:,}원", inline=True)
                    embed.add_field(name="거절 사유", value=info["reason"], inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"[DM Error] {e}")
        asyncio.run_coroutine_threadsafe(_notify_user(), bot_instance.loop)

    flash("충전 신청이 거절 처리되었습니다.", "info")
    return redirect(url_for("charges"))

# ----------------- 제품 및 재고 관리 -----------------
@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description", "")
        price = int(request.form.get("price", 0))
        image_url = request.form.get("image_url", "")
        is_active = True if request.form.get("is_active") == "on" else False

        with get_db() as db:
            p = Product(name=name, description=description, price=price, image_url=image_url, is_active=is_active)
            db.add(p)
            db.flush()
            record_system_log("PRODUCT_ADD", f"상품 '{name}' 등록 (ID: {p.id})", session.get("admin_username"))
        flash("상품이 성공적으로 추가되었습니다.", "success")
        return redirect(url_for("products"))

    with get_db() as db:
        prods = db.query(Product).all()
        prod_data = []
        for p in prods:
            stock = db.query(Inventory).filter_by(product_id=p.id, is_used=False).count()
            prod_data.append({"p": p, "stock": stock})
        return render_template("products.html", products=prod_data)

@app.route("/products/<int:p_id>/edit", methods=["POST"])
@login_required
def product_edit(p_id):
    with get_db() as db:
        p = db.query(Product).filter_by(id=p_id).first()
        if not p:
            flash("상품을 찾을 수 없습니다.", "danger")
            return redirect(url_for("products"))

        p.name = request.form.get("name")
        p.description = request.form.get("description", "")
        p.price = int(request.form.get("price", 0))
        p.image_url = request.form.get("image_url", "")
        p.is_active = True if request.form.get("is_active") == "on" else False
        record_system_log("PRODUCT_EDIT", f"상품 '{p.name}' 정보 수정", session.get("admin_username"))

    flash("상품 정보가 수정되었습니다.", "success")
    return redirect(url_for("products"))

@app.route("/products/<int:p_id>/delete", methods=["POST"])
@login_required
def product_delete(p_id):
    with get_db() as db:
        p = db.query(Product).filter_by(id=p_id).first()
        if p:
            name = p.name
            db.delete(p)
            record_system_log("PRODUCT_DELETE", f"상품 '{name}' 삭제", session.get("admin_username"))
            flash("상품이 삭제되었습니다.", "success")
    return redirect(url_for("products"))

@app.route("/products/<int:p_id>/inventory", methods=["GET", "POST"])
@login_required
def inventory_manage(p_id):
    with get_db() as db:
        p = db.query(Product).filter_by(id=p_id).first()
        if not p:
            flash("상품을 찾을 수 없습니다.", "danger")
            return redirect(url_for("products"))

        if request.method == "POST":
            bulk_text = request.form.get("items_text", "")
            count = InventoryService.add_bulk_stock(p_id, bulk_text)
            record_system_log("STOCK_ADD", f"상품 '{p.name}' 재고 {count}개 추가", session.get("admin_username"))
            flash(f"총 {count}개의 재고가 등록되었습니다.", "success")
            return redirect(url_for("inventory_manage", p_id=p_id))

        unused_items = db.query(Inventory).filter_by(product_id=p_id, is_used=False).all()
        used_items = db.query(Inventory).filter_by(product_id=p_id, is_used=True).order_by(Inventory.used_at.desc()).limit(50).all()
        return render_template("inventory.html", product=p, unused_items=unused_items, used_items=used_items)

@app.route("/inventory/delete/<int:inv_id>", methods=["POST"])
@login_required
def inventory_delete(inv_id):
    with get_db() as db:
        inv = db.query(Inventory).filter_by(id=inv_id, is_used=False).first()
        if inv:
            p_id = inv.product_id
            db.delete(inv)
            flash("미사용 재고 데이터가 삭제되었습니다.", "info")
            return redirect(url_for("inventory_manage", p_id=p_id))
    flash("항목을 찾을 수 없거나 이미 사용되었습니다.", "danger")
    return redirect(url_for("products"))

# ----------------- 주문 / 회원 / 설정 라우트 -----------------
@app.route("/orders")
@login_required
def orders():
    with get_db() as db:
        order_list = db.query(Order).order_by(Order.id.desc()).all()
        return render_template("orders.html", orders=order_list)

@app.route("/users")
@login_required
def users():
    with get_db() as db:
        user_list = db.query(User).order_by(User.id.desc()).all()
        return render_template("users.html", users=user_list)

@app.route("/users/<int:u_id>/adjust", methods=["POST"])
@login_required
def user_adjust(u_id):
    amount = int(request.form.get("amount", 0))
    action = request.form.get("action")  # set, add, ban, unban
    with get_db() as db:
        user = db.query(User).filter_by(id=u_id).first()
        if not user:
            flash("사용자를 찾을 수 없습니다.", "danger")
            return redirect(url_for("users"))

        admin_name = session.get("admin_username")
        if action == "ban":
            user.is_banned = True
            record_system_log("USER_BAN", f"사용자 {user.username} 이용 제한", admin_name)
            flash("사용자가 이용 제한되었습니다.", "warning")
        elif action == "unban":
            user.is_banned = False
            record_system_log("USER_UNBAN", f"사용자 {user.username} 제한 해제", admin_name)
            flash("사용자 이용 제한이 해제되었습니다.", "success")
        elif action == "adjust":
            before = user.balance
            user.balance += amount
            record_system_log("BALANCE_ADJUST", f"사용자 {user.username} 잔액 조정: {before:,} -> {user.balance:,}", admin_name)
            flash(f"잔액이 조정되었습니다. (현재: {user.balance:,}원)", "success")

    return redirect(url_for("users"))

@app.route("/logs/settings", methods=["GET", "POST"])
@login_required
def log_settings():
    log_types = [
        ("charge_request", "충전 신청 로그"),
        ("charge_approve", "충전 승인 로그"),
        ("charge_reject", "충전 거절 로그"),
        ("purchase", "상품 구매 로그")
    ]
    with get_db() as db:
        if request.method == "POST":
            for lt, _ in log_types:
                ch_id_str = request.form.get(f"ch_{lt}", "").strip()
                ch_id = int(ch_id_str) if ch_id_str.isdigit() else None
                setting = db.query(LogSetting).filter_by(log_type=lt).first()
                if not setting:
                    setting = LogSetting(log_type=lt)
                    db.add(setting)
                setting.channel_id = ch_id
            flash("로그 채널 설정이 저장되었습니다.", "success")
            return redirect(url_for("log_settings"))

        settings_map = {s.log_type: s.channel_id for s in db.query(LogSetting).all()}
        return render_template("logs.html", log_types=log_types, settings_map=settings_map)

@app.route("/logs/test/<string:log_type>", methods=["POST"])
@login_required
def log_test(log_type):
    send_discord_log(
        log_type=log_type,
        title="🔔 [테스트] 로그 전송 확인",
        fields={
            "테스트 시간": "정상 작동 확인",
            "실행자": session.get("admin_username", "Admin")
        },
        color=0x5865F2
    )
    return jsonify({"success": True, "message": f"{log_type} 테스트 로그가 전송되었습니다."})

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    keys = ["bank_name", "bank_account", "bank_holder"]
    with get_db() as db:
        if request.method == "POST":
            for k in keys:
                val = request.form.get(k, "").strip()
                setting = db.query(SystemSetting).filter_by(key=k).first()
                if not setting:
                    setting = SystemSetting(key=k)
                    db.add(setting)
                setting.value = val
            flash("입금 계좌 설정이 저장되었습니다.", "success")
            return redirect(url_for("settings"))

        settings_map = {s.key: s.value for s in db.query(SystemSetting).all()}
        return render_template("settings.html", settings=settings_map)

@app.route("/system-logs")
@login_required
def system_logs():
    with get_db() as db:
        logs = db.query(SystemLog).order_by(SystemLog.id.desc()).limit(100).all()
        return render_template("system_logs.html", logs=logs)

# ----------------- 영수증 이미지 서빙 라우트 -----------------
@app.route("/uploads/receipts/<path:filename>")
@login_required
def uploaded_receipt(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)