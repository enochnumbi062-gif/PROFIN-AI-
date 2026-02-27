import os
import pyotp
import io
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Importation du moteur d'IA (Assurez-vous que ia_engine.py est dans le même dossier)
from ia_engine import ProfinIA

app = Flask(__name__)
ia = ProfinIA()

# --- CONFIGURATION (Render & Sécurité) ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre_cle_secrete_profin_2026')
# Utilise DATABASE_URL de Render (PostgreSQL), sinon SQLite en local
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration Email (Contact Profin-AI)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'contact.profin.ai@gmail.com'
app.config['MAIL_PASSWORD'] = 'jmnp cwbj mpzf fzjw' 

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODÈLES DE DONNÉES ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    otp_secret = db.Column(db.String(32)) 
    
class BusinessPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score_bancabilite = db.Column(db.Float)
    analyse_ia = db.Column(db.Text)
    date_scan = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES D'AUTHENTIFICATION ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(nom_complet=nom, email=email, password=hashed_pw, otp_secret=pyotp.random_base32())
        
        db.session.add(new_user)
        db.session.commit()
        flash('Compte créé ! Connectez-vous.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            totp = pyotp.TOTP(user.otp_secret, interval=300)
            otp_code = totp.now()
            
            msg = Message('Votre code ProFin-AI', sender=app.config['MAIL_USERNAME'], recipients=[user.email])
            msg.body = f"Bonjour {user.nom_complet}, votre code de sécurité est : {otp_code}"
            mail.send(msg)
            
            session['temp_user_id'] = user.id
            return redirect(url_for('verify_2fa'))
        flash('Identifiants incorrects.', 'danger')
    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'temp_user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        user = User.query.get(session['temp_user_id'])
        totp = pyotp.TOTP(user.otp_secret, interval=300)
        
        if totp.verify(otp_input):
            login_user(user)
            session.pop('temp_user_id')
            return redirect(url_for('dashboard'))
        flash('Code invalide ou expiré.', 'danger')
    return render_template('verify_2fa.html')

# --- ROUTES DU SALON PRINCIPAL (DASHBOARD) ---

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.nom_complet)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'business_plan' not in request.files:
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['business_plan']
    if file.filename == '':
        return redirect(url_for('dashboard'))

    if file:
        # L'IA analyse le fichier
        score, feedback = ia.analyser_pdf(file)
        
        # Enregistrement en base de données
        new_scan = BusinessPlan(score_bancabilite=score, analyse_ia=feedback, user_id=current_user.id)
        db.session.add(new_scan)
        db.session.commit()

        return render_template('dashboard.html', 
                               name=current_user.nom_complet, 
                               score=score, 
                               feedback=feedback)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
