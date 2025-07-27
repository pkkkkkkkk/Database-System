from flask import Flask, render_template, request, redirect, url_for, flash
import database_operations as db_ops # 导入创建的数据库操作模块

app = Flask(__name__)
app.secret_key = 'your secret key' 

@app.route('/')
def index():
    teams, teams_error = db_ops.get_all_teams()
    tournaments, tournaments_error = db_ops.get_all_tournament_seasons()

    if teams_error:
        flash(teams_error, 'error')
    if tournaments_error:
        flash(tournaments_error, 'error')
        
    return render_template(
        'index.html', 
        title='足球赛事管理系统 - 首页', 
        teams_list=teams, 
        tournaments_list=tournaments
    )

# --- a. 删除球员 (事务) ---
@app.route('/player/delete', methods=['GET', 'POST'])
def delete_player_page():
    if request.method == 'POST':
        player_name = request.form.get('player_name')
        if not player_name:
            flash('请输入球员姓名进行删除。', 'error')
        else:
            success, logs = db_ops.transactional_delete_player_by_name(player_name)
            for log_entry in logs: 
                if "错误" in log_entry or "失败" in log_entry or "未找到" in log_entry:
                    flash(log_entry, 'error')
                else:
                    flash(log_entry, 'info') 
            if success:
                flash(f"球员 '{player_name}' 相关信息已成功删除。", 'success')
            else:
                flash(f"删除球员 '{player_name}' 操作未完全成功，请查看日志。", 'warning')
        return redirect(url_for('delete_player_page')) 
    return render_template('delete_player_form.html', title='删除球员')

# --- b. 添加球员 (触发器) ---
@app.route('/player/add', methods=['GET', 'POST'])
def add_player_page():
    if request.method == 'POST':
        player_data = {
            'id': request.form.get('player_id'),
            'name': request.form.get('name'),
            'position': request.form.get('position'),
            'nationality': request.form.get('nationality'),
            'birth_date': request.form.get('birth_date'),
            'height_weight': request.form.get('height_weight'),
            'team_id': request.form.get('team_id'),
            'goals': request.form.get('goals', 0), 
            'assists': request.form.get('assists', 0) 
        }
        # 简单验证
        if not all([player_data['id'], player_data['name'], player_data['position'], player_data['birth_date'], player_data['team_id']]):
            flash('请填写所有必填项。', 'error')
        else:
            success, logs = db_ops.add_player_with_trigger(player_data)
            for log_entry in logs:
                if "错误" in log_entry or "失败" in log_entry:
                    flash(log_entry, 'error')
                else:
                    flash(log_entry, 'info')
            if success:
                flash(f"球员 '{player_data['name']}' 添加成功。", 'success')
            else:
                flash(f"添加球员 '{player_data['name']}' 失败。", 'error')
        return redirect(url_for('add_player_page'))
    return render_template('add_player_form.html', title='添加球员')

# --- c. 球员转会 (存储过程) ---
@app.route('/player/transfer', methods=['GET', 'POST'])
def transfer_player_page():
    if request.method == 'POST':
        player_id = request.form.get('player_id')
        new_team_id = request.form.get('new_team_id')
        if not player_id or not new_team_id:
            flash('请输入球员ID和新球队ID。', 'error')
        else:
            try:
                player_id_int = int(player_id)
                new_team_id_int = int(new_team_id)
                success, logs = db_ops.transfer_player_with_sp(player_id_int, new_team_id_int)
                for log_entry in logs:
                    if "错误" in log_entry or "失败" in log_entry:
                        flash(log_entry, 'error')
                    else:
                        flash(log_entry, 'info')
                if success:
                    flash(f"球员 {player_id_int} 转会操作已执行。", 'success')
                else:
                    flash(f"球员 {player_id_int} 转会操作失败。", 'error')
            except ValueError:
                flash('球员ID和球队ID必须是数字。', 'error')
        return redirect(url_for('transfer_player_page'))
    return render_template('transfer_player_form.html', title='球员转会')

# --- d. 查看俱乐部球员 (视图) ---
@app.route('/club/players_by_name', methods=['GET', 'POST'])
def view_club_players_by_name_page():
    players_list = []
    club_name_searched = None
    if request.method == 'POST':
        club_name_input = request.form.get('club_name')
        club_name_searched = club_name_input

        if not club_name_input:
            flash('请输入俱乐部名称进行查询。', 'error')
        else:
            players_list, error_msg, searched_name_from_db = db_ops.get_players_from_view_by_club_name(club_name_input)
            club_name_searched = searched_name_from_db 

            if error_msg:
                flash(error_msg, 'error')
            elif not players_list:
                flash(f'未找到俱乐部 "{club_name_input}" 的球员信息，或该俱乐部无球员。', 'info')
    
    return render_template(
        'view_club_players_form.html', 
        title='查看俱乐部球员', 
        players=players_list, 
        club_name_searched=club_name_searched
    )

if __name__ == '__main__':
    app.run(debug=True) 