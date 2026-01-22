from handlers.users import admin, help, main_handler, music, start, video


def register_routers(dp) -> None:
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(video.router)
    dp.include_router(music.router)
    dp.include_router(help.router)
    dp.include_router(main_handler.router)
