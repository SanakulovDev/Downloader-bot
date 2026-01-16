import os
import asyncio
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from loader import bot
from utils.db_api.database import engine
from utils.db_api.models import User

app = FastAPI()

@app.get("/")
async def index():
    return RedirectResponse(url="/admin")

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.full_name, User.username, User.joined_at]
    can_create = False
    can_edit = False
    can_delete = True
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

admin = Admin(app, engine)
admin.add_view(UserAdmin)

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import RedirectResponse
import aiohttp

class BroadcastView(BaseView):
    name = "Broadcast"
    icon = "fa-solid fa-bullhorn"

    @expose("/broadcast", methods=["GET", "POST"])
    async def broadcast_page(self, request: Request):
        if request.method == "POST":
            form = await request.form()
            message_text = form.get("message")
            
            # Send message logic
            # Since we can't easily access the bot instance from here if it's in a different process/loop 
            # (though here we import it), let's assume we can use it directly or via API.
            # Using the bot instance imported from bot.py might conflict with the main process if running separately?
            # Actually, aiogram Bot is stateless HTTP client, so it's fine to use it here to SEND messages.
            
            from loader import bot
            from sqlalchemy import select
            from utils.db_api.database import async_session
            
            count = 0
            try:
                async with async_session() as session:
                    result = await session.execute(select(User.id))
                    user_ids = result.scalars().all()
                    
                for user_id in user_ids:
                    try:
                        await bot.send_message(chat_id=user_id, text=message_text)
                        count += 1
                        await asyncio.sleep(0.05) # Rate limit
                    except Exception:
                        pass
                        
                return await self.templates.TemplateResponse(request, "broadcast_result.html", 
                                                          {"count": count, "total": len(user_ids)})
            except Exception as e:
                return await self.templates.TemplateResponse(request, "broadcast_result.html", {"error": str(e)})

        return await self.templates.TemplateResponse(request, "broadcast.html")

admin.add_view(BroadcastView)
