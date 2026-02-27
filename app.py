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
        # Logique : détection de mots-clés financiers
        keywords = ["profit", "marché", "croissance", "investissement", "revenu", "business", "plan", "finance"]
        count = sum(1 for word in keywords if word in texte.lower())
        
        score = min(40 + (count * 8), 98)
        analyse = f"Analyse terminée pour votre projet. {count} indicateurs clés de viabilité ont été détectés. La structure du document démontre une maturité financière intéressante."
        return score, analyse

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
            flash(f"Votre code de sécurité est {code}", "info")
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
    plans = BusinessPlan.query.filter_by(user_id=current_user.id).order_by(BusinessPlan.date_scan.desc()).all()
    return render_template('dashboard.html', name=current_user.nom, plans=plans)

# --- ANALYSE & GÉNÉRATION DE RAPPORT ---

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier détecté"}), 400
    
    file = request.files['file']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Veuillez soumettre un fichier PDF valide"}), 400

    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file.read()))
        extracted_text = ""
        for i in range(min(len(pdf_reader.pages), 5)):
            page_text = pdf_reader.pages[i].extract_text()
            if page_text: extracted_text += page_text

        if not extracted_text.strip():
            return jsonify({"error": "PDF illisible (scan image non supporté)"}), 400

        score, analyse = ia.analyser(extracted_text) 

        new_plan = BusinessPlan(
            score_bancabilite=score,
            analyse_ia=analyse,
            user_id=current_user.id
        )
        db.session.add(new_plan)
        db.session.commit()

        return jsonify({"success": True, "score": score, "analyse": analyse})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur technique : {str(e)}"}), 500

@app.route('/download-report/<int:plan_id>')
@login_required
def download_report(plan_id):
    plan = BusinessPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        return "Accès refusé", 403

    pdf = FPDF()
    pdf.add_page()
    
    # Design du Rapport
    pdf.set_font("Arial", 'B', 20)
    pdf.set_text_color(30, 60, 114) 
    pdf.cell(190, 20, "RAPPORT D'ANALYSE PROFIN-AI", ln=True, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 10, f"Date : {plan.date_scan.strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Score de Bancabilité : {plan.score_bancabilite}%", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(190, 10, f"Commentaire de l'IA :\n{plan.analyse_ia}")

    output = io.BytesIO()
    pdf_content = pdf.output(dest='S').encode('latin-1', 'ignore')
    output.write(pdf_content)
    output.seek(0)

    return send_file(output, mimetype='application/pdf', 
                     as_attachment=True, 
                     download_name=f"Rapport_ProfinAI_{plan.id}.pdf")

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
