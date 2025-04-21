from flask import Blueprint, render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from core.models.tasks import custom_select, select_task
from . import login_required

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/', methods=['GET'])
@login_required
def view_tasks():
    raw_args = request.args.to_dict(flat=True)
    clean_args = {k: v for k, v in raw_args.items() if v}

    if raw_args and clean_args != raw_args:
        return redirect(url_for('tasks.view_tasks', **clean_args))

    filters = {}
    if 'user_id' in clean_args:
        try:
            filters['user_id'] = int(clean_args['user_id'])
        except ValueError:
            flash('User ID должен быть числом', 'warning')

    if 'course' in clean_args:
        filters['course'] = clean_args['course']

    if 'response_status' in clean_args:
        filters['response_status'] = clean_args['response_status']

    if 'grade_status' in clean_args:
        filters['grade_status'] = clean_args['grade_status']

    tasks = list(custom_select(filters))
    return render_template('tasks.html', tasks=tasks, filters=clean_args)

@tasks_bp.route('/update/<task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    task = None
    try:
        task = select_task({'_id': ObjectId(task_id)})
    except Exception:
        pass

    if not task:
        flash('Задача не найдена', 'danger')
        return redirect(url_for('tasks.view_tasks', **request.args))

    new_resp = request.form.get('response_status')
    new_grade = request.form.get('grade_status')
    if new_resp is not None:
        task.response_status = new_resp
    if new_grade is not None:
        task.grade_status = new_grade

    flash('Статус задачи обновлён', 'success')
    return redirect(url_for('tasks.view_tasks', **request.args))