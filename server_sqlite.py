import os
import sys
import json
import sqlite3
import bcrypt
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

# Resource path (for PyInstaller or local run)
def resource_path(filename):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(__file__), filename)

USER_FILE = resource_path("users.json")
DB_FILE = resource_path("clipboard.db")

app = Flask(__name__)
CORS(app)

# Load/save users.json
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USER_FILE, "w") as f:
        json.dump(data, f, indent=2)

# DB helper
def get_db():
    return sqlite3.connect(DB_FILE)

# 🔐 Login
@app.route('/login', methods=['POST'])
def login():
    users = load_users()
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Missing fields"}), 400
    if username not in users:
        return jsonify({"success": False, "message": "Invalid username"}), 401

    stored_hash = users[username].encode()
    if bcrypt.checkpw(password.encode(), stored_hash):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Incorrect password"}), 401

# 🆕 Register
@app.route('/update_user', methods=['POST'])
def update_user():
    data = request.json
    username = data.get("username")
    password_hash = data.get("password_hash")

    if not username or not password_hash:
        return jsonify({"success": False, "message": "Missing fields"}), 400

    users = load_users()
    if username in users:
        return jsonify({"success": False, "message": "User already exists"}), 400

    users[username] = password_hash
    save_users(users)
    return jsonify({"success": True, "message": "User created"})

# 📋 Upload clipboard entry
@app.route('/upload', methods=['POST'])
def upload_clipboard():
    users = load_users()
    data = request.json
    username = data.get("username")
    content = data.get("data")

    if not username or username not in users:
        return jsonify({"error": "Invalid user"}), 401
    if not content:
        return jsonify({"error": "Missing clipboard data"}), 400

    conn = get_db()
    timestamp = datetime.now().isoformat()
    conn.execute("INSERT INTO entries (username, content, timestamp) VALUES (?, ?, ?)", (username, content, timestamp))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# 📥 Get clipboard history
@app.route('/get', methods=['GET'])
def get_clipboard():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_db()
    rows = conn.execute("SELECT content, timestamp FROM entries WHERE username = ?", (user_id,)).fetchall()
    conn.close()

    if not rows:
        return jsonify([])

    return jsonify([
        {"content": row[0], "timestamp": row[1]}
        for row in rows
    ])

# 🧹 Clear clipboard history
@app.route('/clear', methods=['POST'])
def clear_clipboard():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_db()
    conn.execute("DELETE FROM entries WHERE username = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": f"Clipboard cleared for user: {user_id}"})

# 📏 Get storage size
@app.route('/size', methods=['GET'])
def get_storage_size():
    conn = get_db()
    rows = conn.execute("SELECT content FROM entries").fetchall()
    conn.close()

    total_bytes = sum(len(json.dumps(row[0]).encode('utf-8')) for row in rows)
    return jsonify({
        "total_size_bytes": total_bytes,
        "total_size_kb": round(total_bytes / 1024, 2),
        "total_size_mb": round(total_bytes / (1024 * 1024), 2)
    })

# 🗑️ Delete single clipboard entry
@app.route('/delete_entry', methods=['POST'])
def delete_entry():
    data = request.json
    username = data.get("username")
    timestamp = data.get("timestamp")

    if not username or not timestamp:
        return jsonify({"success": False, "message": "Missing data"}), 400

    conn = get_db()
    conn.execute("DELETE FROM entries WHERE username = ? AND timestamp = ?", (username, timestamp))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Deleted."})

# 🔁 Run server
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
