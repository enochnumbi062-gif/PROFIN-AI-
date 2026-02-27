import os
import pyotp
import io
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Importation du moteur d'IA
from ia_engine import ProfinIA

app = Flask(__name__)
ia = ProfinIA()

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PfAI_9x$2KzL#vQ7!mR4@nB8*pT1&jW5^hG0%sX3+cV6=yU9_bN2[zM5]qW8{kP1}fL4|rS7')

uri = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Config Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER', 'contact.profin.ai@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS', 'jmnp cwbj mpzf fzjw') 

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODÈLES ---
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False) 
    email = db.Column(db.String(150), unique=True, nullable=False) 
    password = db.Column(db.String(500), nullable=False) 
    otp_secret = db.Column(db.String(64)) 

class BusinessPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score_bancabilite = db.Column(db.Float)
    analyse_ia = db.Column(db.Text) 
    date_scan = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom_in = request.form.get('nom')
        email = request.form.get('email')
        pw = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Email déjà utilisé.', 'danger')
            return redirect(url_for('register'))
        new_u = User(nom=nom_in, email=email, password=generate_password_hash(pw), otp_secret=pyotp.random_base32())
        db.session.add(new_u)
        db.session.commit()
        flash('Compte créé !', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form.get('email')).first()
        if u and check_password_hash(u.password, request.form.get('password')):
            totp = pyotp.TOTP(u.otp_secret)
            msg = Message('Code ProFin-AI', sender=app.config['MAIL_USERNAME'], recipients=[u.email])
            msg.body = f"Code : {totp.now()}"
            mail.send(msg)
            session['temp_user_id'] = u.id
            return redirect(url_for('verify_2fa'))
    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'temp_user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        u = User.query.get(session['temp_user_id'])
        if pyotp.TOTP(u.otp_secret).verify(request.form.get('otp')):
            login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('verify_2fa.html')

@app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html', name=current_user.nom)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('business_plan')
    if file:
        score, feedback = ia.analyser_pdf(file)
        new_s = BusinessPlan(score_bancabilite=score, analyse_ia=feedback, user_id=current_user.id)
        db.session.add(new_s)
        db.session.commit()
        return render_template('dashboard.html', name=current_user.nom, score=score, feedback=feedback)
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- EXÉCUTION & NETTOYAGE FORCÉ (LE COEUR DE LA SOLUTION) ---
if __name__ == '__main__':
    with app.app_context():
        try:
            print("Action Commando : Nettoyage forcé de la base...")
            # On force la suppression des tables corrompues sur Render
            db.session.execute(db.text('DROP TABLE IF EXISTS business_plan CASCADE;'))
            db.session.execute(db.text('DROP TABLE IF EXISTS "user" CASCADE;'))
            db.session.commit()
            # On recrée tout proprement
            db.create_all()
            print("Structure reconstruite à neuf avec succès.")
        except Exception as e:
            print(f"Erreur Nettoyage : {e}")
            db.session.rollback()

    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
