 # database_operations.py
import mysql.connector

# 数据库配置 
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'pk20050714',
    'database': 'soccer'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"数据库连接错误: {err}")
        return None

def get_all_teams():
    conn = None
    teams_data = []
    error_message = None
    try:
        conn = get_db_connection()
        if not conn:
            return [], "无法连接到数据库。"
        cursor = conn.cursor(dictionary=True)
        # 查询球队表，并连接球场表获取主场实际名称
        query = "SELECT 球队id, 球队名称, 主教练, 所属城市, 主场名称 FROM 球队 ORDER BY 球队名称 ASC"
        cursor.execute(query)
        teams_data = cursor.fetchall()
    except mysql.connector.Error as err:
        error_message = f"查询所有球队信息失败: {err}"
    except Exception as e:
        error_message = f"程序错误: {e}"
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
    return teams_data, error_message

def get_all_tournament_seasons():
    conn = None
    tournaments_data = []
    error_message = None
    try:
        conn = get_db_connection()
        if not conn:
            return [], "无法连接到数据库。"
        cursor = conn.cursor(dictionary=True)
        # 查询赛事表，并连接球队表获取冠军球队的名称
        query = """
            SELECT 
                s.赛事名称, 
                s.当前赛季, 
                s.赛事冠军_球队id,
                t.球队名称 AS 冠军球队名称 
            FROM 赛事 s
            LEFT JOIN 球队 t ON s.赛事冠军_球队id = t.球队id
            ORDER BY s.赛事名称 ASC, s.当前赛季 DESC
        """
        cursor.execute(query)
        tournaments_data = cursor.fetchall()
    except mysql.connector.Error as err:
        error_message = f"查询所有赛事信息失败: {err}"
    except Exception as e:
        error_message = f"程序错误: {e}"
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
    return tournaments_data, error_message
# --- 核心操作函数 ---

# a. 含有事务应用的删除操作 (根据姓名删除球员)
def transactional_delete_player_by_name(player_name_to_delete): 
    conn = None
    log_messages = []
    operation_successful = False
    subclass_table_map = {
        '前锋': '锋线球员', '中场': '中场球员',
        '后卫': '后卫球员', '门将': '门将球员'
    }

    try:
        conn = get_db_connection()
        if not conn:
            log_messages.append("错误：无法连接到数据库。")
            return False, log_messages

        cursor = conn.cursor(dictionary=True) 

        # 步骤 1: 开始事务
        conn.start_transaction()
        log_messages.append(f"开始事务：查找并准备删除球员 '{player_name_to_delete}'...")

        # 步骤 2: 根据姓名查找球员ID和位置 
        sql_find_player = "SELECT 球员id, 位置 FROM 球员 WHERE 球员姓名 = %s"
        cursor.execute(sql_find_player, (player_name_to_delete,))
        players_found = cursor.fetchall()

        if not players_found:
            log_messages.append(f"未找到姓名为 '{player_name_to_delete}' 的球员。事务将回滚。")
            conn.rollback() 
            operation_successful = False
        elif len(players_found) > 1:
            log_messages.append(f"找到多名姓名为 '{player_name_to_delete}' 的球员，操作中止。事务将回滚。IDs: {[p['球员id'] for p in players_found]}")
            conn.rollback()
            operation_successful = False
        else: # 找到唯一球员
            player_data = players_found[0]
            player_id_to_delete = player_data['球员id']
            player_position = player_data['位置']
            subclass_table_name = subclass_table_map.get(player_position)

            if not subclass_table_name:
                log_messages.append(f"错误：球员ID {player_id_to_delete} 的位置 '{player_position}' 未知或无效。事务将回滚。")
                conn.rollback() 
                raise Exception(f"未知球员位置: {player_position}") 

            log_messages.append(f"找到球员: ID={player_id_to_delete}, 位置='{player_position}'. 继续删除操作...")
            
            # 步骤 3: 从子类表删除
            sql_delete_subclass = f"DELETE FROM {subclass_table_name} WHERE 球员id = %s"
            cursor.execute(sql_delete_subclass, (player_id_to_delete,))
            log_messages.append(f"- 从 {subclass_table_name} 删除记录，影响行数: {cursor.rowcount}")

            # 步骤 4: 从主球员表删除
            sql_delete_main = "DELETE FROM 球员 WHERE 球员id = %s"
            cursor.execute(sql_delete_main, (player_id_to_delete,))
            if cursor.rowcount == 0: 
                log_messages.append(f"错误：尝试删除主球员表记录时未找到球员ID {player_id_to_delete}。事务将回滚。")
                conn.rollback()
                raise Exception(f"主球员表删除失败，未找到球员ID {player_id_to_delete}。")
            log_messages.append(f"- 从 球员 表删除记录，影响行数: {cursor.rowcount}")
            
            # 步骤 5: 提交事务
            conn.commit()
            log_messages.append(f"球员 {player_name_to_delete} (ID: {player_id_to_delete}) 已成功删除。事务已提交。")
            operation_successful = True
       
    except mysql.connector.Error as err:
        log_messages.append(f"数据库错误: {err}")
        if conn and conn.in_transaction:
            conn.rollback()
            log_messages.append("数据库操作失败，事务已回滚。")
    except Exception as e:
        log_messages.append(f"发生其他错误: {e}")
        if conn and conn.in_transaction:
            conn.rollback()
            log_messages.append("操作失败，事务已回滚。")
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: 
                cursor.close()
            conn.close()
            log_messages.append("MySQL 连接已关闭。")
    
    return operation_successful, log_messages

# b. 触发器控制下的添加操作 (添加球员)
def add_player_with_trigger(player_data):
    conn = None
    log_messages = []
    operation_successful = False
    try:
        conn = get_db_connection()
        if not conn:
            log_messages.append("无法连接到数据库。")
            return False, log_messages
        cursor = conn.cursor()

        sql_insert_player = """
            INSERT INTO 球员 (球员id, 球员姓名, 位置, 球员国籍, 出生日期, 身高体重, 效力球队id) 
            VALUES (%(id)s, %(name)s, %(position)s, %(nationality)s, %(birth_date)s, %(height_weight)s, %(team_id)s)
        """
        cursor.execute(sql_insert_player, player_data)
        
        # 如果添加成功且是特定位置，插入到子类表
        if player_data['position'] == "前锋":
            sql_insert_forward = "INSERT INTO 锋线球员 (球员id, 进球数, 助攻数) VALUES (%s, %s, %s)"
            cursor.execute(sql_insert_forward, (player_data['id'], player_data.get('goals', 0), player_data.get('assists', 0)))
        conn.commit()
        log_messages.append(f"球员 {player_data['name']} 添加请求已发送。触发器将处理年龄等检查。")
        operation_successful = True
    except mysql.connector.Error as err: 
        log_messages.append(f"添加球员失败: {err}")
        if conn: conn.rollback()
    except Exception as e:
        log_messages.append(f"程序错误: {e}")
        if conn: conn.rollback()
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
            log_messages.append("数据库连接已关闭。")
    return operation_successful, log_messages

# c. 存储过程控制下的更新操作 (球员转会)
def transfer_player_with_sp(player_id, new_team_id):
    conn = None
    log_messages = []
    operation_successful = False
    try:
        conn = get_db_connection()
        if not conn:
            log_messages.append("无法连接到数据库。")
            return False, log_messages
        cursor = conn.cursor(dictionary=True)

        args = (player_id, new_team_id)
        cursor.callproc('sp_transfer_player', args) 
        
        for result in cursor.stored_results():
            fetched_results = result.fetchall()
            if fetched_results:
                log_messages.append("存储过程返回: " + str(fetched_results))
        
        conn.commit() 
        log_messages.append(f"球员ID {player_id} 转会至球队ID {new_team_id} 的操作已执行。")
        operation_successful = True
    except mysql.connector.Error as err: 
        log_messages.append(f"球员转会失败: {err}")
    except Exception as e:
        log_messages.append(f"程序错误: {e}")
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
            log_messages.append("数据库连接已关闭。")
    return operation_successful, log_messages

# d. 含有视图的查询操作 (查询俱乐部球员)
def get_players_from_view_by_club_name(club_name_to_search):
    conn = None
    players_data = []
    error_message = None
    club_display_name = club_name_to_search
    try:
        conn = get_db_connection()
        if not conn:
            return [], "无法连接到数据库。", club_display_name
            
        cursor = conn.cursor(dictionary=True) 
        query = "SELECT * FROM view_club_player_details WHERE 效力球队名称 = %s"
        cursor.execute(query, (club_name_to_search,))
        players_data = cursor.fetchall()

    except mysql.connector.Error as err:
        error_message = f"查询球员信息失败: {err}"
    except Exception as e:
        error_message = f"程序错误: {e}"
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            conn.close()
            
    return players_data, error_message, club_display_name
