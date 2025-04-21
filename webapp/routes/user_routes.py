import json
import logging

from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash

from core.models import users
from . import login_required

logger = logging.getLogger(__name__)
users_bp = Blueprint("users", __name__)


@users_bp.route("/", methods=["GET"])
@login_required
def view_users():
    users_list = users.custom_select({})
    return render_template(
        "users.html",
        users_list=users_list,
        courses_map=json.dumps(current_app.config["SETTINGS"].COURSES_MAP, ensure_ascii=False)
    )


@users_bp.route("/update", methods=["POST"])
@login_required
def update_user():
    try:
        telegram_id = request.form.get('telegram_id')
        if not telegram_id:
            flash("Не указан идентификатор пользователя", "error")
            return redirect(url_for("main.view_users"))

        user = users.select_user(int(telegram_id))
        if not user:
            flash("Пользователь не найден", "error")
            return redirect(url_for("main.view_users"))

        has_changes = False

        new_telegram = request.form.get('telegram_username')
        if user.telegram_username != new_telegram:
            user.telegram_username = new_telegram
            has_changes = True

        new_mtuci_login = request.form.get('mtuci_login') or None
        if user.mtuci_login != new_mtuci_login:
            user.mtuci_login = new_mtuci_login
            has_changes = True

        new_faculty = request.form.get('faculty') or None
        if user.faculty != new_faculty:
            user.faculty = new_faculty
            has_changes = True

        new_course = request.form.get('course') or None
        if user.course != new_course:
            user.course = new_course
            has_changes = True

        new_group = request.form.get('group') or None
        if user.group != new_group:
            user.group = new_group
            has_changes = True

        new_education_level = request.form.get('education_level') or None
        if user.education_level != new_education_level:
            user.education_level = new_education_level
            has_changes = True

        new_form = request.form.get('study_form') or None
        if user.study_form != new_form:
            user.study_form = new_form
            has_changes = True

        if has_changes:
            flash(f"Данные пользователя {user.telegram_username} успешно обновлены", "info")
        else:
            flash("Нет изменений для сохранения", "info")

    except ValueError as e:
        flash(f"Ошибка формата данных: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {str(e)}")
        flash("Произошла ошибка при обновлении", "error")

    return redirect(url_for("users.view_users"))


@users_bp.route("/delete", methods=["POST"])
@login_required
def delete_user():
    try:
        telegram_id = request.form.get('telegram_id')
        if not telegram_id:
            flash("Не указан идентификатор пользователя", "error")
            return redirect(url_for("main.view_users"))

        user = users.select_user(int(telegram_id))
        if not user:
            flash("Пользователь не найден", "error")
            return redirect(url_for("main.view_users"))

        users.remove_user(int(telegram_id))

        flash(f"Пользователь удален", "info")

    except ValueError as e:
        flash(f"Ошибка формата данных: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {str(e)}")
        flash("Произошла ошибка при обновлении", "error")

    return redirect(url_for("main.view_users"))
