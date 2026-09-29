import os
import time
import sqlite3
from flask import Flask, request, render_template, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_minimal_app'
DB_FILE = 'tracker.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            username TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            last_updated REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'username' in session:
        if session.get('role') == 'parent':
            return redirect(url_for('parent'))
        elif session.get('role') == 'child':
            return redirect(url_for('child'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            conn.close()
            return "Username already exists. <a href='/signup'>Try again</a>", 400
            
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            session['role'] = role
            if role == 'parent':
                return redirect(url_for('parent'))
            else:
                return redirect(url_for('child'))
        return "Invalid credentials. <a href='/login'>Try again</a>", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'username' in session and session.get('role') == 'child':
        # Clear location when child logs out
        conn = get_db_connection()
        conn.execute('DELETE FROM locations WHERE username = ?', (session['username'],))
        conn.commit()
        conn.close()
        
    session.clear()
    return redirect(url_for('login'))

@app.route('/child')
def child():
    if 'username' not in session or session.get('role') != 'child':
        return redirect(url_for('login'))
    return render_template('child.html', username=session['username'])

@app.route('/parent')
def parent():
    if 'username' not in session or session.get('role') != 'parent':
        return redirect(url_for('login'))
    return render_template('parent.html', username=session['username'])

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'username' not in session or session.get('role') != 'child':
        return jsonify({"status": "unauthorized"}), 401
        
    data = request.json
    username = session['username']
    lat = data.get('lat')
    lng = data.get('lng')
    current_time = time.time()
    
    conn = get_db_connection()
    # Insert or update
    conn.execute('''
        INSERT INTO locations (username, lat, lng, last_updated) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET 
        lat=excluded.lat, lng=excluded.lng, last_updated=excluded.last_updated
    ''', (username, lat, lng, current_time))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

@app.route('/get_location', methods=['GET'])
def get_location():
    if 'username' not in session or session.get('role') != 'parent':
        return jsonify({"status": "unauthorized"}), 401
        
    username = session['username']
    
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM locations WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    # Check if location was updated in the last 15 seconds.
    # If not, it means the child is not actively sharing.
    if row and (time.time() - row['last_updated'] <= 15):
        return jsonify({"lat": row['lat'], "lng": row['lng']})
        
    return jsonify({"lat": None, "lng": None})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    