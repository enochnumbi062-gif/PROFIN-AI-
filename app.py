import os
import pyotp
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION (Render & Sécurité) ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PfAI_9x$2KzL#vQ7!mR4@nB8*pT1&jW5^hG0%sX3+cV6=yU9_bN2[zM5]qW8{kP1}fL4|rS7')
uri = os.environ.get('DATABASE_URL', 'sqlite:///profin_ai.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
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

# --- LE BULLDOZER : BRUTE FORCE SQL ---
def brute_force_db():
    with app.app_context():
        try:
            print("🧨 AMORÇAGE DU BULLDOZER SQL...")
            # On ne fait plus ALTER TABLE, on fait DROP pour tout raser
            # C'est la seule façon de garantir que 'user.nom' existera
            db.session.execute(db.text('DROP TABLE IF EXISTS business_plan CASCADE;'))
            db.session.execute(db.text('DROP TABLE IF EXISTS "user" CASCADE;'))
            db.session.commit()
            
            # Reconstruction immédiate
            db.create_all()
            print("🏗️  RECONSTRUCTION TERMINÉE : LA BASE EST VIERGE ET PARFAITE.")
        except Exception as e:
            print(f"❌ ERREUR LORS DU BULLDOZAGE : {e}")
            db.session.rollback()

# --- ROUTES (Simplifiées pour le test) ---
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
            return "✅ SUCCÈS ! La base a obéi. Vous êtes inscrit."
        except Exception as e:
            return f"🔥 ÉCHEC : La base résiste encore. Erreur : {str(e)}"
    return render_template('register.html')

if __name__ == '__main__':
    brute_force_db() # On rase tout avant de démarrer
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
