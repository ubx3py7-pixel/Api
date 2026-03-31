from flask import Flask, request, jsonify
import sqlite3
import os
import tempfile
import requests

app = Flask(__name__)

# ================= CONFIG =================
DRIVE_FILE_ID = os.environ.get('DRIVE_FILE_ID', '1int8ppAHK6elB66jSrwIGyA741-mK4Zk')


# ================= DB HELPER =================
def download_drive_file(file_id, dest_path):
    """Download from Google Drive properly handling redirect/confirmation"""
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"

    response = session.get(url, stream=True)

    # Handle virus scan warning page
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={value}"
            response = session.get(url, stream=True)
            break

    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)


def get_db_connection():
    """Download DB from Drive into /tmp and return connection"""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_path = tmp.name
    tmp.close()

    download_drive_file(DRIVE_FILE_ID, tmp_path)

    conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    return conn, tmp_path


def close_db(conn, tmp_path):
    conn.close()
    os.unlink(tmp_path)


# ================= GET ALL USERS =================
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn, tmp_path = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM telegram_users ORDER BY created_at DESC')
        rows = [dict(row) for row in cursor.fetchall()]
        close_db(conn, tmp_path)

        return jsonify({
            "status": "success",
            "count": len(rows),
            "users": rows
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= GET SINGLE USER =================
@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        conn, tmp_path = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM telegram_users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        close_db(conn, tmp_path)

        if row:
            return jsonify({"status": "success", "user": dict(row)}), 200
        else:
            return jsonify({"status": "not_found", "user_id": user_id}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= SEARCH =================
@app.route('/api/users/search', methods=['GET'])
def search_users():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Missing ?q= param"}), 400

    try:
        conn, tmp_path = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM telegram_users
            WHERE username LIKE ? OR first_name LIKE ? OR phone LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
        rows = [dict(row) for row in cursor.fetchall()]
        close_db(conn, tmp_path)

        return jsonify({
            "status": "success",
            "count": len(rows),
            "users": rows
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= HEALTH CHECK =================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "file_id": DRIVE_FILE_ID}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
