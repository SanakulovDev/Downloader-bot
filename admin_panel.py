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
    can_edit = True
    can_delete = True
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

admin = Admin(app, engine, templates_dir="templates")
admin.add_view(UserAdmin)

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import RedirectResponse
import aiohttp

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import RedirectResponse
import aiohttp
from utils.broadcast_worker import broadcast_worker
from utils.db_api.models import Broadcast

class BroadcastView(BaseView):
    name = "Broadcast"
    icon = "fa-solid fa-bullhorn"

    @expose("/broadcast", methods=["GET", "POST"])
    async def broadcast_page(self, request: Request):
        if request.method == "POST":
            form = await request.form()
            message_text = form.get("message")
            message_type = form.get("message_type")
            
            file_id = None
            
            # Check for file upload
            uploaded_file = form.get("file_upload")
            if uploaded_file and hasattr(uploaded_file, "filename") and uploaded_file.filename:
                import shutil
                from pathlib import Path
                
                upload_dir = Path("/app/downloads/broadcasts")
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = upload_dir / uploaded_file.filename
                
                # Save file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(uploaded_file.file, buffer)
                
                file_id = str(file_path)
            else:
                # Fallback to link/ID
                file_id = form.get("file_id")

            
            # Create DB record
            from utils.db_api.database import async_session
            async with async_session() as session:
                new_broadcast = Broadcast(
                    message_text=message_text, 
                    message_type=message_type, 
                    file_id=file_id,
                    status="processing"
                )
                session.add(new_broadcast)
                await session.commit()
                broadcast_id = new_broadcast.id

            # Start Background Task
            task = asyncio.create_task(broadcast_worker(broadcast_id))
            def handle_task_result(task: asyncio.Task):
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass  # Task cancellation should not be treated as an error.
                except Exception as e:
                    import logging
                    logging.getLogger("admin_panel").error(f"Broadcast task failed: {e}")
            task.add_done_callback(handle_task_result)
            
            return await self.templates.TemplateResponse(request, "broadcast_result.html", 
                                                      {"message": f"Broadcast {broadcast_id} started!"})

        # List History
        from utils.db_api.database import async_session
        from sqlalchemy import select, desc
        async with async_session() as session:
            result = await session.execute(select(Broadcast).order_by(desc(Broadcast.created_at)).limit(10))
            history = result.scalars().all()

        return await self.templates.TemplateResponse(request, "broadcast.html", {"history": history})

    @expose("/broadcast-resend/{broadcast_id}", methods=["GET", "POST"])
    async def resend_broadcast(self, request: Request):
        if request.method == "GET":
             return RedirectResponse(url="/admin/broadcast", status_code=303)
        try:
            broadcast_id = int(request.path_params["broadcast_id"])
            from utils.db_api.database import async_session
            from sqlalchemy import select
            
            async with async_session() as session:
                # Fetch original
                result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
                original = result.scalar_one_or_none()
                
                if original:
                    # Create copy
                    new_broadcast = Broadcast(
                        message_text=original.message_text,
                        message_type=original.message_type,
                        file_id=original.file_id,
                        status="processing"
                    )
                    session.add(new_broadcast)
                    await session.commit()
                    new_id = new_broadcast.id
                    
                    # Start worker
                    asyncio.create_task(broadcast_worker(new_id))
                    
            return RedirectResponse(url="/admin/broadcast", status_code=303)
        except Exception as e:
            return RedirectResponse(url="/admin/broadcast", status_code=303)

    @expose("/broadcast-edit/{broadcast_id}", methods=["GET", "POST"])
    async def edit_broadcast(self, request: Request):
        if request.method == "GET":
             return RedirectResponse(url="/admin/broadcast", status_code=303)
        try:
            broadcast_id = int(request.path_params["broadcast_id"])
            form = await request.form()
            new_text = form.get("message_text")
            update_sent = form.get("update_sent") == "on"
            
            # New fields
            new_type = form.get("message_type")
            new_file_id = None
            
            # Check for file upload (edit_media_source=upload/link)
            edit_source = form.get("edit_media_source")
            uploaded_file = form.get("file_upload")
            
            if new_type and new_type != 'text':
                if edit_source == 'upload' and uploaded_file and hasattr(uploaded_file, "filename") and uploaded_file.filename:
                    import shutil
                    from pathlib import Path
                    upload_dir = Path("/app/downloads/broadcasts")
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    file_path = upload_dir / uploaded_file.filename
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(uploaded_file.file, buffer)
                    new_file_id = str(file_path)
                else:
                    new_file_id = form.get("file_id")

            if update_sent:
                from utils.broadcast_worker import edit_broadcast_worker
                # Pass all new data to worker
                asyncio.create_task(edit_broadcast_worker(broadcast_id, new_text, new_type, new_file_id))
            else:
                 # Just update DB
                from utils.db_api.database import async_session
                from sqlalchemy import select
                async with async_session() as session:
                    result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
                    broadcast = result.scalar_one_or_none()
                    if broadcast:
                        broadcast.message_text = new_text
                        if new_type:
                            broadcast.message_type = new_type
                        if new_file_id:
                            broadcast.file_id = new_file_id
                        await session.commit()

            return RedirectResponse(url="/admin/broadcast", status_code=303)
        except Exception as e:
            return RedirectResponse(url="/admin/broadcast", status_code=303)
            
    @expose("/broadcast-delete-record/{broadcast_id}", methods=["GET", "POST"])
    async def delete_broadcast_record(self, request: Request):
        if request.method == "GET":
             return RedirectResponse(url="/admin/broadcast", status_code=303)
        try:
            broadcast_id = int(request.path_params["broadcast_id"])
            from utils.broadcast_worker import delete_broadcast_worker
            # Trigger worker to delete messages AND the record
            asyncio.create_task(delete_broadcast_worker(broadcast_id, delete_record=True))
                     
            return RedirectResponse(url="/admin/broadcast", status_code=303)
        except Exception as e:
            return RedirectResponse(url="/admin/broadcast", status_code=303)

    @expose("/broadcast-delete/{broadcast_id}", methods=["GET", "POST"])
    async def delete_broadcast(self, request: Request):
        if request.method == "GET":
             return RedirectResponse(url="/admin/broadcast", status_code=303)
        try:
            broadcast_id = int(request.path_params["broadcast_id"])
            from utils.broadcast_worker import delete_broadcast_worker
            asyncio.create_task(delete_broadcast_worker(broadcast_id))
            return RedirectResponse(url="/admin/broadcast", status_code=303)
        except Exception as e:
             # In a real app we'd flash a message
            return RedirectResponse(url="/admin/broadcast", status_code=303)

admin.add_view(BroadcastView)

# --- Support Mini App Endpoints ---
from utils.db_api.models import SupportTicket

@app.get("/support")
async def support_page(request: Request):
    from starlette.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse(request=request, name="support.html")

from pydantic import BaseModel

class SupportRequest(BaseModel):
    user_id: int
    username: str | None = None
    fullname: str | None = None
    message: str
    initData: str | None = None

@app.post("/support/submit")
async def submit_support(data: SupportRequest):
    try:
        # 1. Save to DB
        from utils.db_api.database import async_session
        async with async_session() as session:
            ticket = SupportTicket(
                user_id=data.user_id,
                message=data.message,
                status="open"
            )
            session.add(ticket)
            await session.commit()
            
        # 2. Notify Admin
        import os
        admins_str = os.getenv("ADMINS", "")
        # Handle "id, id" or "id,id" formats
        admins = [a.strip() for a in admins_str.split(",") if a.strip()]
        
        if admins:
            from loader import bot
            text = (
                f"📨 <b>Yangi Murojaat!</b>\n\n"
                f"👤 <b>User:</b> {data.fullname} (@{data.username})\n"
                f"🆔 <b>ID:</b> <code>{data.user_id}</code>\n\n"
                f"📝 <b>Xabar:</b>\n{data.message}"
            )
            for admin_id in admins:
                try:
                    await bot.send_message(chat_id=int(admin_id), text=text, parse_mode="HTML")
                except Exception as e:
                    print(f"Failed to send support msg to {admin_id}: {e}")
                    pass
                    
        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# --- Support Admin Dashboard ---
class SupportView(BaseView):
    name = "Support"
    icon = "fa-solid fa-envelope"
    identity = "support_hub"

    @expose("/inbox", methods=["GET"])
    async def support_dashboard(self, request: Request):
        from starlette.templating import Jinja2Templates
        from sqlalchemy import select, desc
        from utils.db_api.database import async_session
        
        # self.templates is available in BaseView
        
        async with async_session() as session:
            result = await session.execute(
                select(SupportTicket).order_by(
                    # Open tickets first, then by date desc
                    desc(SupportTicket.status == 'open'),
                    desc(SupportTicket.created_at)
                ).limit(50)
            )
            tickets = result.scalars().all()
            
        return await self.templates.TemplateResponse(request, "admin_support.html", context={"tickets": tickets})

    @expose("/reply/{ticket_id}", methods=["POST"])
    async def support_reply(self, request: Request):
        ticket_id = int(request.path_params["ticket_id"])
        form = await request.form()
        reply_text = form.get("reply_text")
        
        if not reply_text:
            return RedirectResponse(url="/admin/support_hub/inbox", status_code=303)
            
        from utils.db_api.database import async_session
        from sqlalchemy import select, func
        from loader import bot
        
        async with async_session() as session:
            result = await session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            
            if ticket and ticket.status == 'open':
                # 1. Send to User
                try:
                    await bot.send_message(
                        chat_id=ticket.user_id,
                        text=f"📨 <b>Admin javobi:</b>\n\n{reply_text}",
                        parse_mode="HTML"
                    )
                    
                    # 2. Update DB
                    ticket.admin_reply = reply_text
                    ticket.replied_at = func.now()
                    ticket.status = "resolved"
                    await session.commit()
                    
                except Exception as e:
                    import logging
                    logging.error(f"Failed to send reply to {ticket.user_id}: {e}")
                    
        return RedirectResponse(url="/admin/support_hub/inbox", status_code=303)

admin.add_view(SupportView)
