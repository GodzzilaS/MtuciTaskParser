from flask import Blueprint, render_template, request, redirect, url_for, flash

from core.models.config import get_schedule_interval, set_schedule_interval
from . import login_required

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def view_settings():
    if request.method == "POST":
        try:
            interval = int(request.form["interval"])
            set_schedule_interval(interval)
            flash(f"✅ Интервал проверки изменён: {interval} мин.", "info")
        except ValueError:
            flash("❌ Неверный формат интервала", "danger")
        return redirect(url_for("settings.view_settings"))

    interval = get_schedule_interval()
    return render_template("settings.html", interval=interval)
