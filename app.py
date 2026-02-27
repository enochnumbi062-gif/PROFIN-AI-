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
        analyse = f"Analyse terminée pour votre projet. {count} indicateurs clés de viabilité ont été détectés. La structure du document démontre une maturité financière intéressante."
        return score, analyse

app = Flask(__name__)
ia = ProfinIA()

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PfAI_9x$2KzL#vQ7!mR4@nB8*pT1&jW5^hG0%sX3+cV6=yU9_bN2[zM5]qW8{kP1}fL4|rS7')

uri = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration Email (SMTP)
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

class BusinessPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score_bancabilite = db.Column(db.Float)
    analyse_ia = db.Column(db.Text) 
    date_scan = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- UTILITAIRES (PDF & EMAILS) ---
def generate_pdf_report(plan, owner_name):
    if plan.score_bancabilite >= 80:
        statut, conseils = "EXCELLENT", "1. Prêt pour levée de fonds.\n2. Préparez la Due Diligence.\n3. Optimisez le pitch deck."
    elif plan.score_bancabilite >= 50:
        statut, conseils = "FAVORABLE", "1. Renforcez la trésorerie.\n2. Précisez l'acquisition client.\n3. Besoin de garanties."
    else:
        statut, conseils = "À AMÉLIORER", "1. Revoyez le Business Model.\n2. Prouvez la traction.\n3. Détaillez l'usage des fonds."

    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 60, 114) # Bleu DorkNet
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_font("Arial", 'B', 24); pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 15, "DORKNET XCHANGE", ln=True, align='C')
    pdf.set_font("Arial", 'I', 12); pdf.cell(190, 10, "Rapport d'Analyse Financière IA", ln=True, align='C')
    
    pdf.ln(20); pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 14)
    pdf.cell(100, 10, f"Entrepreneur : {owner_name}")
    pdf.cell(90, 10, f"Date : {plan.date_scan.strftime('%d/%m/%Y')}", ln=True, align='R')
    pdf.line(10, 65, 200, 65); pdf.ln(10)

    pdf.set_font("Arial", 'B', 16); pdf.cell(190, 10, f"RÉSULTAT : {statut}", ln=True)
    pdf.set_font("Arial", 'B', 40); pdf.set_text_color(30, 60, 114); pdf.cell(190, 25, f"{plan.score_bancabilite}%", ln=True, align='C')
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, "Observations IA :", ln=True)
    pdf.set_font("Arial", size=11); pdf.multi_cell(190, 8, plan.analyse_ia); pdf.ln(5)

    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, "CONSEILS STRATÉGIQUES :", ln=True, fill=True)
    pdf.set_font("Arial", size=11); pdf.multi_cell(190, 8, conseils)
    
    return pdf.output(dest='S').encode('latin-1', 'ignore')

def send_thank_you_email(user_email, user_nom):
    msg = Message(
        subject="Bienvenue dans l'aventure DorkNet Xchange 🚀",
        sender=app.config['MAIL_USERNAME'],
        recipients=[user_email]
    )
    msg.body = f"""
Bonjour {user_nom},

C'est un honneur pour moi de vous remercier personnellement pour votre généreux soutien à DorkNet Xchange.

Votre contribution nous permet de rester indépendants et de continuer à offrir aux entrepreneurs les outils des plus grandes banques d'affaires.

Grâce à vous, nous bâtissons l'avenir de la finance.

Bien à vous,

Dr Enoch Numbi
Fondateur, DorkNet Xchange
    """
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Erreur d'envoi : {e}")
        return False

# --- ROUTES AUTHENTIFICATION ---
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        new_user = User(nom=request.form.get('nom'), email=request.form.get('email'), password=hashed_pw, otp_secret=pyotp.random_base32())
        db.session.add(new_user); db.session.commit()
        flash('Compte créé avec succès !', 'success')
        return redirect(url_for('login'))
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
        if pyotp.TOTP(user.otp_secret, interval=300).verify(request.form.get('otp')):
            login_user(user); session.pop('temp_user_id')
            return redirect(url_for('dashboard'))
        flash('Code OTP invalide', 'danger')
    return render_template('verify_2fa.html')

# --- ROUTES UTILISATEURS & NAVIGATION ---
@app.route('/dashboard')
@login_required
def dashboard():
    plans = BusinessPlan.query.filter_by(user_id=current_user.id).order_by(BusinessPlan.date_scan.desc()).all()
    return render_template('dashboard.html', name=current_user.nom, plans=plans)

@app.route('/profil')
@login_required
def profil():
    total_plans = BusinessPlan.query.filter_by(user_id=current_user.id).count()
    return render_template('profil.html', user=current_user, total=total_plans)

@app.route('/mes-documents')
@login_required
def mes_documents():
    search_query = request.args.get('search', '')
    query = BusinessPlan.query.filter_by(user_id=current_user.id)
    if search_query:
        query = query.filter(BusinessPlan.analyse_ia.icontains(search_query))
    plans = query.order_by(BusinessPlan.date_scan.desc()).all()
    return render_template('documents.html', plans=plans, search_query=search_query)

@app.route('/donner')
@login_required
def donner():
    return render_template('donner.html')

# --- ACTIONS TECHNIQUES ---
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files['file']
    if not file: return jsonify({"error": "Fichier manquant"}), 400
    pdf_reader = pypdf.PdfReader(io.BytesIO(file.read()))
    text = "".join([p.extract_text() for p in pdf_reader.pages[:5]])
    score, analyse = ia.analyser(text)
    new_plan = BusinessPlan(score_bancabilite=score, analyse_ia=analyse, user_id=current_user.id)
    db.session.add(new_plan); db.session.commit()
    return jsonify({"success": True, "score": score})

@app.route('/download-report/<int:plan_id>')
@login_required
def download_report(plan_id):
    plan = BusinessPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id: return "Accès refusé", 403
    pdf_content = generate_pdf_report(plan, current_user.nom)
    return send_file(io.BytesIO(pdf_content), mimetype='application/pdf', as_attachment=True, download_name=f"Rapport_DorkNet_{plan.id}.pdf")

@app.route('/share-report', methods=['POST'])
@login_required
def share_report():
    data = request.get_json()
    plan = BusinessPlan.query.get_or_404(data.get('plan_id'))
    if plan.user_id != current_user.id: return jsonify({"error": "Interdit"}), 403
    try:
        pdf_content = generate_pdf_report(plan, current_user.nom)
        msg = Message(subject=f"DorkNet Xchange : Projet de {current_user.nom}", sender=app.config['MAIL_USERNAME'], recipients=[data.get('email')])
        msg.body = f"Bonjour,\n\n{current_user.nom} vous partage son analyse de projet.\n\nMessage : {data.get('message')}"
        msg.attach(f"Rapport_DorkNet_{plan.id}.pdf", "application/pdf", pdf_content)
        mail.send(msg)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete-plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_plan(plan_id):
    plan = BusinessPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        return jsonify({"success": False, "error": "Action non autorisée"}), 403
    try:
        db.session.delete(plan)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('login'))

# --- TEST REMERCIEMENT ---
@app.route('/test-thank-you')
@login_required
def test_thank_you():
    success = send_thank_you_email(current_user.email, current_user.nom)
    if success:
        flash("Email de remerciement envoyé (test) !", "success")
    else:
        flash("Erreur lors de l'envoi de l'email.", "danger")
    return redirect(url_for('donner'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
