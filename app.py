import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Optional

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change_this_secret')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

def get_db():
    conn = sqlite3.connect('database.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS berths (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        capacity INTEGER DEFAULT 0,
        status TEXT DEFAULT 'operational')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vessel_name TEXT NOT NULL,
        vessel_type TEXT,
        eta TEXT,
        etd TEXT,
        berth_id INTEGER,
        status TEXT DEFAULT 'scheduled',
        FOREIGN KEY(berth_id) REFERENCES berths(id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL)""")
    # default users
    cur = conn.execute('SELECT id FROM users WHERE username=?', ('admin',))
    if cur.fetchone() is None:
        conn.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                     ('admin', generate_password_hash('admin123'), 'admin'))
    cur = conn.execute('SELECT id FROM users WHERE username=?', ('viewer',))
    if cur.fetchone() is None:
        conn.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                     ('viewer', generate_password_hash('viewer123'), 'user'))
    conn.commit()
    conn.close()

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['role'])
    return None

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class BerthForm(FlaskForm):
    name = StringField('Nama Dermaga', validators=[DataRequired()])
    location = StringField('Lokasi', validators=[Optional()])
    capacity = IntegerField('Kapasitas', validators=[Optional()])
    status = SelectField('Status', choices=[('operational','Operational'),('maintenance','Maintenance'),('closed','Closed')])
    submit = SubmitField('Simpan')

class OperationForm(FlaskForm):
    vessel_name = StringField('Nama Kapal', validators=[DataRequired()])
    vessel_type = StringField('Jenis Kapal', validators=[Optional()])
    eta = StringField('ETA (yyyy-mm-dd hh:mm)', validators=[Optional()])
    etd = StringField('ETD (yyyy-mm-dd hh:mm)', validators=[Optional()])
    berth_id = SelectField('Dermaga', coerce=int, validators=[Optional()])
    status = SelectField('Status', choices=[('scheduled','Scheduled'),('arrived','Arrived'),('ongoing','Ongoing'),('completed','Completed'),('cancelled','Cancelled')])
    submit = SubmitField('Simpan')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=?', (form.username.data,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], form.password.data):
            login_user(User(user['id'], user['username'], user['role']))
            flash('Login berhasil.', 'success')
            return redirect(url_for('dashboard'))
        flash('Username atau password salah.', 'danger')
    return render_template('login.html', form=form, title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    berths_count = conn.execute('SELECT COUNT(*) AS cnt FROM berths').fetchone()['cnt']
    operations_count = conn.execute('SELECT COUNT(*) AS cnt FROM operations').fetchone()['cnt']
    latest_ops = conn.execute('SELECT o.*, b.name as berth_name FROM operations o LEFT JOIN berths b ON o.berth_id=b.id ORDER BY o.id DESC LIMIT 5').fetchall()
    conn.close()
    return render_template('dashboard.html', berths_count=berths_count, operations_count=operations_count, latest_ops=latest_ops, title='Dashboard')

@app.route('/berths', methods=['GET','POST'])
@login_required
def berths():
    form = BerthForm()
    conn = get_db()
    if request.method == 'POST' and form.validate_on_submit():
        if current_user.role != 'admin':
            flash('Akses ditolak. Hanya admin.', 'danger')
            return redirect(url_for('berths'))
        conn.execute('INSERT INTO berths(name,location,capacity,status) VALUES (?,?,?,?)',
                     (form.name.data, form.location.data or '', form.capacity.data or 0, form.status.data))
        conn.commit()
        flash('Dermaga berhasil ditambahkan.', 'success')
    rows = conn.execute('SELECT * FROM berths ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('berths.html', rows=rows, form=form, title='Berths')

@app.route('/berths/delete/<int:id>')
@login_required
def delete_berth(id):
    if current_user.role != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('berths'))
    conn = get_db()
    row = conn.execute('SELECT * FROM berths WHERE id=?', (id,)).fetchone()
    if row:
        conn.execute('DELETE FROM berths WHERE id=?', (id,))
        conn.commit()
        flash('Dermaga dihapus.', 'success')
    else:
        flash('Dermaga tidak ditemukan.', 'warning')
    conn.close()
    return redirect(url_for('berths'))

@app.route('/operations', methods=['GET','POST'])
@login_required
def operations():
    conn = get_db()
    berths = conn.execute('SELECT id, name FROM berths ORDER BY name').fetchall()
    berth_choices = [(0, '— Pilih Dermaga —')] + [(b['id'], b['name']) for b in berths]
    form = OperationForm()
    form.berth_id.choices = berth_choices
    if request.method == 'POST' and form.validate_on_submit():
        if current_user.role != 'admin':
            flash('Akses ditolak. Hanya admin.', 'danger')
            return redirect(url_for('operations'))
        berth_id = form.berth_id.data if form.berth_id.data != 0 else None
        conn.execute('INSERT INTO operations(vessel_name, vessel_type, eta, etd, berth_id, status) VALUES (?,?,?,?,?,?)',
                     (form.vessel_name.data, form.vessel_type.data or '', form.eta.data or '', form.etd.data or '', berth_id, form.status.data))
        conn.commit()
        flash('Operasi disimpan.', 'success')
    rows = conn.execute('SELECT o.*, b.name as berth_name FROM operations o LEFT JOIN berths b ON o.berth_id=b.id ORDER BY o.id DESC').fetchall()
    conn.close()
    return render_template('operations.html', rows=rows, form=form, title='Operations')

@app.route('/operations/delete/<int:id>')
@login_required
def delete_operation(id):
    if current_user.role != 'admin':
        flash('Akses ditolak. Hanya admin.', 'danger')
        return redirect(url_for('operations'))
    conn = get_db()
    row = conn.execute('SELECT * FROM operations WHERE id=?', (id,)).fetchone()
    if row:
        conn.execute('DELETE FROM operations WHERE id=?', (id,))
        conn.commit()
        flash('Operasi dihapus.', 'success')
    else:
        flash('Operasi tidak ditemukan.', 'warning')
    conn.close()
    return redirect(url_for('operations'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
