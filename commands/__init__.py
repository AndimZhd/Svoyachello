from aiogram import Router

from commands.register import router as register_router
from commands.start import router as start_router
from commands.player_info import router as player_info_router
from commands.events import router as events_router
from commands.pause import router as pause_router
from commands.answer import router as answer_router
from commands.settings import router as settings_router

router = Router()
router.include_router(register_router)
router.include_router(start_router)
router.include_router(player_info_router)
router.include_router(events_router)
router.include_router(pause_router)
router.include_router(settings_router)
router.include_router(answer_router)  # Must be last - catches all non-command text


