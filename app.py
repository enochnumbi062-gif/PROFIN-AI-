import os
import pyotp
import pypdf
import io
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from fpdf import FPDF

# --- MOTEUR IA ---
class ProfinIA:
    def analyser(self, texte):
        keywords = ["profit", "marché", "croissance", "investissement", "revenu", "business", "plan", "finance"]
        count = sum(1 for word in keywords if word in texte.lower())
        score = min(40 + (count * 8), 98)
        analyse = f"Analyse terminée pour votre projet. {count} indicateurs clés de viabilité ont été détectés."
        return score, analyse

app = Flask(__name__)
ia = ProfinIA()

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PfAI_9x$2KzL#vQ7!mR4@nB8*pT1&jW5^hG0%sX3+cV6=yU9_bN2')
uri = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Config
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

# Initialisation forcée
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES AUTHENTIFICATION (CORRIGÉES) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        password = request.form.get('password')
        
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        otp_s = pyotp.random_base32() # Génération du secret
        
        new_user = User(nom=nom, email=email, password=hashed_pw, otp_secret=otp_s)
        db.session.add(new_user)
        db.session.commit()
        
        # CRUCIAL : On redirige vers une page qui affiche la clé de sécurité
        return render_template('setup_2fa.html', secret=otp_s, email=email)
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            session['temp_user_id'] = user.id
            return redirect(url_for('verify_2fa'))
        flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'temp_user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user = User.query.get(session['temp_user_id'])
        # Vérification du code saisi
        if pyotp.TOTP(user.otp_secret, interval=300).verify(request.form.get('otp')):
            login_user(user)
            session.pop('temp_user_id')
            return redirect(url_for('dashboard'))
        flash('Code OTP invalide ou expiré', 'danger')
    return render_template('verify_2fa.html')

# --- AUTRES ROUTES (Dashboard, Upload, PDF...) ---
# (Gardez vos routes existantes ici sans changement)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
