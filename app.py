import os
import pyotp
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION (À adapter pour Render) ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre_cle_secrete_ultra_secure')
# Utilisation de PostgreSQL sur Render, sinon SQLite en local
app.config['SQLALCHEMY_DATABASE_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration Email (Exemple Gmail)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER') # Votre email
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS') # Votre Mot de passe d'application

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODÈLE UTILISATEUR ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    otp_secret = db.Column(db.String(32)) # Secret unique pour le 2FA
    is_verified = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='sha256')
        # Générer un secret OTP unique pour cet utilisateur
        new_user = User(nom_complet=nom, email=email, password=hashed_pw, otp_secret=pyotp.random_base32())
        
        db.session.add(new_user)
        db.session.commit()
        flash('Compte créé ! Connectez-vous maintenant.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            # 1. Générer le code OTP
            totp = pyotp.TOTP(user.otp_secret, interval=300) # Code valide 5 min
            otp_code = totp.now()
            
            # 2. Envoyer par email
            msg = Message('Votre code de vérification ProFin-AI',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[user.email])
            msg.body = f"Bonjour {user.nom_complet}, votre code de sécurité est : {otp_code}"
            mail.send(msg)
            
            # 3. Stocker l'ID utilisateur temporairement en session
            session['temp_user_id'] = user.id
            return redirect(url_for('verify_2fa'))
        else:
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
        else:
            flash('Code invalide ou expiré.', 'danger')
            
    return render_template('verify_2fa.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.nom_complet)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Crée la base de données au lancement
    app.run(debug=True)
