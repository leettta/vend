import discord
from discord.ui import View, Button, Select, Modal, TextInput
from database.db import get_db
from database.models import User, Order
from services.inventory_service import InventoryService
from services.purchase_service import PurchaseService
from services.charge_service import ChargeService

def create_main_embed():
    embed = discord.Embed(
        title="🛒 프리미엄 자동 자판기",
        description="아래 버튼을 눌러 자판기 기능을 이용해보세요.\n빠르고 안전하게 상품을 구매하고 충전할 수 있습니다.",
        color=0x5865F2
    )
    embed.add_field(name="[ 구매 ]", value="상품을 선택하고 즉시 구매합니다.", inline=True)
    embed.add_field(name="[ 제품 ]", value="현재 판매 중인 상품 목록과 재고를 확인합니다.", inline=True)
    embed.add_field(name="[ 충전 ]", value="계좌 입금을 통해 잔액을 충전합니다.", inline=True)
    embed.add_field(name="[ 정보 ]", value="내 잔액 및 과거 구매 내역을 확인합니다.", inline=True)
    embed.set_footer(text="24시간 연중무휴 자동 발송 시스템")
    return embed

class MainVendingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="구매", style=discord.ButtonStyle.primary, custom_id="vending:purchase", emoji="🛍️")
    async def btn_purchase(self, interaction: discord.Interaction, button: Button):
        products = InventoryService.get_active_products()
        if not products:
            return await interaction.response.send_message("현재 등록된 상품이 없습니다.", ephemeral=True)
        
        view = PurchaseSelectView(products)
        embed = discord.Embed(
            title="🛍️ 상품 선택",
            description="구매하실 상품을 아래 목록에서 선택해주세요.",
            color=0x5865F2
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="제품", style=discord.ButtonStyle.secondary, custom_id="vending:products", emoji="📦")
    async def btn_products(self, interaction: discord.Interaction, button: Button):
        products = InventoryService.get_active_products()
        embed = discord.Embed(title="📦 판매 중인 상품 목록", color=0x5865F2)
        if not products:
            embed.description = "현재 판매 중인 제품이 없습니다."
        else:
            for p in products:
                status_str = f"🟢 재고 {p['stock']}개" if p['stock'] > 0 else "🔴 품절"
                embed.add_field(
                    name=f"{p['name']} - {p['price']:,}원",
                    value=f"설명: {p['description'] or '설명 없음'}\n상태: {status_str}",
                    inline=False
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="충전", style=discord.ButtonStyle.success, custom_id="vending:charge", emoji="💳")
    async def btn_charge(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ChargeModal())

    @discord.ui.button(label="정보", style=discord.ButtonStyle.secondary, custom_id="vending:info", emoji="👤")
    async def btn_info(self, interaction: discord.Interaction, button: Button):
        await show_user_info(interaction, page=0)

class PurchaseSelectView(View):
    def __init__(self, products):
        super().__init__(timeout=120)
        options = []
        for p in products[:25]:
            stock_txt = f"{p['stock']}개 남음" if p['stock'] > 0 else "품절"
            options.append(discord.SelectOption(
                label=p['name'][:100],
                value=str(p['id']),
                description=f"가격: {p['price']:,}원 | {stock_txt}"
            ))

        select = Select(placeholder="구매할 상품을 선택하세요...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        product_id = int(interaction.data['values'][0])
        product = InventoryService.get_product_details(product_id)
        if not product:
            return await interaction.response.send_message("상품을 찾을 수 없습니다.", ephemeral=True)

        embed = discord.Embed(
            title=f"📦 {product['name']}",
            description=product['description'] or "제품 설명이 없습니다.",
            color=0x5865F2
        )
        embed.add_field(name="가격", value=f"{product['price']:,}원", inline=True)
        embed.add_field(name="남은 재고", value=f"{product['stock']}개", inline=True)
        if product['image_url']:
            embed.set_image(url=product['image_url'])

        view = PurchaseConfirmView(product_id, product['stock'])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class PurchaseConfirmView(View):
    def __init__(self, product_id: int, stock: int):
        super().__init__(timeout=120)
        self.product_id = product_id
        self.stock = stock

    @discord.ui.button(label="수량 입력 및 결제", style=discord.ButtonStyle.primary, emoji="💳")
    async def btn_order(self, interaction: discord.Interaction, button: Button):
        if self.stock <= 0:
            return await interaction.response.send_message("현재 품절된 상품입니다.", ephemeral=True)
        await interaction.response.send_modal(PurchaseQuantityModal(self.product_id))

class PurchaseQuantityModal(Modal, title="구매 수량 입력"):
    quantity_input = TextInput(label="구매 수량", placeholder="숫자만 입력 (예: 1)", min_length=1, max_length=3)

    def __init__(self, product_id: int):
        super().__init__()
        self.product_id = product_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("수량은 올바른 숫자로 입력해주세요.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        success, msg, data = PurchaseService.process_purchase(
            discord_id=interaction.user.id,
            username=str(interaction.user),
            product_id=self.product_id,
            quantity=qty
        )

        if not success:
            embed = discord.Embed(title="❌ 구매 실패", description=msg, color=0xED4245)
            return await interaction.followup.send(embed=embed, ephemeral=True)

        dm_sent = True
        try:
            dm_embed = discord.Embed(
                title="🎉 구매 및 상품 지급 완료",
                description="구매해주셔서 감사합니다! 아래 상품 지급 내용을 확인하세요.",
                color=0x57F287
            )
            dm_embed.add_field(name="주문번호", value=data['order_number'], inline=False)
            dm_embed.add_field(name="상품명", value=f"{data['product_name']} ({data['quantity']}개)", inline=True)
            dm_embed.add_field(name="결제금액", value=f"{data['total_amount']:,}원", inline=True)
            dm_embed.add_field(name="🔑 상품 내용", value=f"```\n{data['delivery_content']}\n```", inline=False)
            await interaction.user.send(embed=dm_embed)
        except Exception:
            dm_sent = False

        res_embed = discord.Embed(title="✅ 결제 성공", color=0x57F287)
        res_embed.add_field(name="상품명", value=data['product_name'], inline=True)
        res_embed.add_field(name="수량", value=f"{data['quantity']}개", inline=True)
        res_embed.add_field(name="결제 금액", value=f"{data['total_amount']:,}원", inline=True)
        res_embed.add_field(name="남은 잔액", value=f"{data['balance_after']:,}원", inline=True)
        
        if dm_sent:
            res_embed.description = "구매하신 상품 내용이 **Discord DM(개인 메시지)**으로 안전하게 전송되었습니다."
        else:
            res_embed.description = "⚠️ DM이 차단되어 있어 화면에 상품 코드를 표시합니다:\n" + f"```\n{data['delivery_content']}\n```"

        await interaction.followup.send(embed=res_embed, ephemeral=True)

class ChargeModal(Modal, title="잔액 충전 신청"):
    amount_input = TextInput(label="충전할 금액 (원)", placeholder="1000 이상 숫자 (예: 10000)", min_length=4, max_length=8)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("올바른 금액 숫자를 입력해주세요.", ephemeral=True)

        success, msg, req_no = ChargeService.create_request(
            discord_id=interaction.user.id,
            username=str(interaction.user),
            amount=amount
        )

        if not success:
            embed = discord.Embed(title="❌ 충전 신청 실패", description=msg, color=0xED4245)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        bank_info = ChargeService.get_bank_info()

        dm_embed = discord.Embed(
            title="💳 충전 신청 접수 및 입금 안내",
            description="아래 계좌로 입금 후, **이 채팅방에 입금 확인 영수증(이체내역 캡처 사진)을 전송**해주세요.\n*(영수증 사진이 업로드되면 보안을 위해 계좌 정보는 자동으로 삭제됩니다.)*",
            color=0xFEE75C
        )
        dm_embed.add_field(name="신청 번호", value=req_no, inline=False)
        dm_embed.add_field(name="충전 요청 금액", value=f"{amount:,}원", inline=False)
        dm_embed.add_field(name="입금 은행", value=bank_info['bank'], inline=True)
        dm_embed.add_field(name="계좌 번호", value=bank_info['account'], inline=True)
        dm_embed.add_field(name="예금주", value=bank_info['holder'], inline=True)

        try:
            await interaction.user.send(embed=dm_embed)
            await interaction.response.send_message(
                "✅ **충전 신청이 접수되었습니다.**\n봇이 발송한 **DM(개인메시지)을 확인**하여 입금을 진행해주세요.", 
                ephemeral=True
            )
        except discord.Forbidden:
            dm_embed.description = "⚠️ DM 발송에 실패하여 화면에 임시로 표시합니다. 아래 계좌로 입금 후 관리자에게 문의하세요.\n*(Discord 설정에서 서버 멤버의 다이렉트 메시지 허용을 켜주세요)*"
            await interaction.response.send_message(embed=dm_embed, ephemeral=True)

async def show_user_info(interaction: discord.Interaction, page: int = 0):
    user_id = interaction.user.id
    with get_db() as session:
        user = session.query(User).filter_by(discord_id=user_id).first()
        if not user:
            user = User(discord_id=user_id, username=str(interaction.user), balance=0)
            session.add(user)
            session.commit()

        balance = user.balance
        charged = user.total_charged
        spent = user.total_spent

        PAGE_SIZE = 4
        total_orders = session.query(Order).filter_by(discord_id=user_id).count()
        orders = session.query(Order).filter_by(discord_id=user_id).order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
        order_list = [
            {
                "order_number": o.order_number,
                "product_name": o.product_name,
                "quantity": o.quantity,
                "total_amount": o.total_amount,
                "created_at": o.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for o in orders
        ]

    embed = discord.Embed(title=f"👤 {interaction.user.name} 님의 계정 정보", color=0x5865F2)
    embed.add_field(name="현재 잔액", value=f"**{balance:,}원**", inline=True)
    embed.add_field(name="총 충전 금액", value=f"{charged:,}원", inline=True)
    embed.add_field(name="총 사용 금액", value=f"{spent:,}원", inline=True)

    if not order_list:
        embed.add_field(name="📦 구매 내역", value="구매 내역이 없습니다.", inline=False)
    else:
        desc = ""
        for o in order_list:
            desc += f"**{o['product_name']}** ({o['quantity']}개) - {o['total_amount']:,}원\n`{o['order_number']}` | {o['created_at']}\n\n"
        embed.add_field(name=f"📦 구매 내역 (페이지 {page+1}/{(total_orders-1)//PAGE_SIZE + 1 if total_orders > 0 else 1})", value=desc, inline=False)

    view = UserInfoPaginationView(page, total_orders, PAGE_SIZE)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class UserInfoPaginationView(View):
    def __init__(self, current_page: int, total_items: int, page_size: int):
        super().__init__(timeout=120)
        self.current_page = current_page
        self.total_pages = (total_items - 1) // page_size + 1 if total_items > 0 else 1

        if self.current_page <= 0:
            self.btn_prev.disabled = True
        if self.current_page >= self.total_pages - 1:
            self.btn_next.disabled = True

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: Button):
        await show_user_info(interaction, page=self.current_page - 1)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: Button):
        await show_user_info(interaction, page=self.current_page + 1)