import os
import pyotp
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Importation du moteur d'IA
from ia_engine import ProfinIA

app = Flask(__name__)
ia = ProfinIA()

# --- CONFIGURATION (Render & Sécurité) ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PfAI_9x$2KzL#vQ7!mR4@nB8*pT1&jW5^hG0%sX3+cV6=yU9_bN2[zM5]qW8{kP1}fL4|rS7')

uri = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration Email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER', 'contact.profin.ai@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS', 'jmnp cwbj mpzf fzjw') 

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODÈLES DE DONNÉES ---
class User(db.Model):
    __tablename__ = 'user' 
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False) 
    email = db.Column(db.String(150), unique=True, nullable=False) 
    password = db.Column(db.String(500), nullable=False) 
    otp_secret = db.Column(db.String(64)) 
    
    def is_authenticated(self): return True
    def is_active(self): return True
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

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
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            hashed_pw = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
            new_user = User(
                nom=request.form.get('nom'), 
                email=request.form.get('email'), 
                password=hashed_pw, 
                otp_secret=pyotp.random_base32()
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Compte créé ! Connectez-vous.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur : {str(e)}", 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            totp = pyotp.TOTP(user.otp_secret, interval=300)
            code = totp.now()
            session['temp_user_id'] = user.id
            session['debug_otp'] = code 
            flash(f"MODE DIAGNOSTIC : Votre code est {code}", "info")
            return redirect(url_for('verify_2fa'))
        flash('Identifiants incorrects.', 'danger')
    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'temp_user_id' not in session: return redirect(url_for('login'))
    debug_code = session.get('debug_otp', "Expiré")
    if request.method == 'POST':
        user = User.query.get(session['temp_user_id'])
        if pyotp.TOTP(user.otp_secret, interval=300).verify(request.form.get('otp')):
            login_user(user)
            session.pop('temp_user_id')
            session.pop('debug_otp', None)
            return redirect(url_for('dashboard'))
        flash('Code OTP invalide.', 'danger')
    return render_template('verify_2fa.html', debug_code=debug_code)

@app.route('/dashboard')
@login_required
def dashboard():
    # Récupérer l'historique des plans de l'utilisateur
    plans = BusinessPlan.query.filter_by(user_id=current_user.id).order_by(BusinessPlan.date_scan.desc()).all()
    return render_template('dashboard.html', name=current_user.nom, plans=plans)

# --- ROUTE D'ANALYSE DES BUSINESS PLANS ---
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier détecté"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide"}), 400

    if file and file.filename.lower().endswith('.pdf'):
        try:
            # Simulation d'extraction et d'analyse IA
            # On pourra plus tard utiliser ProfinIA.analyser()
            score = 78.5 
            analyse = "Analyse générée : Votre projet présente une structure solide."

            new_plan = BusinessPlan(
                score_bancabilite=score,
                analyse_ia=analyse,
                user_id=current_user.id
            )
            db.session.add(new_plan)
            db.session.commit()

            return jsonify({
                "success": True,
                "score": score,
                "analyse": analyse
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Seuls les fichiers PDF sont acceptés"}), 400

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
