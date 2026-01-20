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

    @expose("/broadcast/delete/{broadcast_id}", methods=["POST"])
    async def delete_broadcast(self, request: Request):
        try:
            broadcast_id = int(request.path_params["broadcast_id"])
            from utils.broadcast_worker import delete_broadcast_worker
            asyncio.create_task(delete_broadcast_worker(broadcast_id))
            return RedirectResponse(url="/admin/broadcast", status_code=303)
        except Exception as e:
             # In a real app we'd flash a message
            return RedirectResponse(url="/admin/broadcast", status_code=303)

admin.add_view(BroadcastView)
