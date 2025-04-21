from flask import Blueprint, render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from core.models.tasks import custom_select, select_task
from . import login_required

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/', methods=['GET'])
@login_required
def view_tasks():
    args = request.args
    filters = {}
    if args.get('user_id'):
        try:
            filters['user_id'] = int(args['user_id'])
        except ValueError:
            flash('User ID должен быть числом', 'warning')
    if args.get('course'):
        filters['course'] = args['course']
    if args.get('response_status'):
        filters['response_status'] = args['response_status']
    if args.get('grade_status'):
        filters['grade_status'] = args['grade_status']

    tasks = list(custom_select(filters))
    return render_template('tasks.html', tasks=tasks, filters=args)

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