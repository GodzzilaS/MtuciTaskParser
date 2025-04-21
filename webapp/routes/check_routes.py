import asyncio
import logging
from threading import Thread

from flask import Blueprint, current_app, flash, redirect, url_for

from scheduler import scheduled_check
from services.encryption import EncryptionService
from services.scraper import Scraper
from . import login_required

logger = logging.getLogger(__name__)
check_bp = Blueprint("check", __name__)


@check_bp.route("/run-check", methods=["POST"])
@login_required
def run_check():
    settings = current_app.config["SETTINGS"]

    def worker():
        scraper = Scraper(settings)
        encryptor = EncryptionService(settings.ENCRYPTION_KEY)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scheduled_check(None, settings, scraper, encryptor))
        finally:
            loop.close()

    Thread(target=worker, daemon=True).start()
    flash("✅ Ручная проверка задач запущена", "info")
    return redirect(url_for("main.root"))
