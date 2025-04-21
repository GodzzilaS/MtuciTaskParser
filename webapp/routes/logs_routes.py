import logging
import os

from flask import Blueprint, render_template, send_file, redirect, url_for, flash, current_app

from . import login_required

logger = logging.getLogger(__name__)
logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/", methods=["GET"])
@login_required
def view_logs():
    log_path = current_app.config["SETTINGS"].LOG_FILE
    if not os.path.exists(log_path):
        lines = ["Лог-файл не найден"]
    else:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            lines = [line.replace("[32m", "") for line in f.readlines()][-200:]
    return render_template("logs.html", logs=lines)


@logs_bp.route("/download", methods=["GET"])
@login_required
def download_logs():
    log_path = current_app.config["SETTINGS"].LOG_FILE
    if not os.path.exists(log_path):
        flash("Лог не найден", "warning")
        return redirect(url_for("logs.view_logs"))
    return send_file(log_path, as_attachment=True, download_name=os.path.basename(log_path))


@logs_bp.route("/clear", methods=["POST"])
@login_required
def clear_logs():
    log_path = current_app.config["SETTINGS"].LOG_FILE
    try:
        open(log_path, "w", encoding="utf-8").close()
        flash("✅ Логи очищены", "info")
    except Exception as e:
        logger.error("Ошибка очистки логов: %s", e)
        flash("❌ Не удалось очистить лог", "error")
    return redirect(url_for("logs.view_logs"))
