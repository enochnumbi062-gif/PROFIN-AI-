import io
from pdfminer.high_level import extract_text

class ProfinIA:
    def __init__(self):
        # Critères structurés pour une analyse multicritère approfondie
        self.piliers = {
            "Finance": ["chiffre d'affaires", "rentabilité", "investissement", "flux de trésorerie", "bilan", "prévisions"],
            "Marché": ["concurrence", "cible", "clientèle", "secteur", "croissance", "demande"],
            "Opérationnel": ["équipe", "stratégie", "ressources humaines", "logistique", "production"],
            "Risques": ["mitigation", "garantie", "risques", "plan de secours"]
        }

    def analyser_pdf(self, file_storage):
        """
        Analyse le Business Plan et retourne un score (Float) et un feedback (Text).
        Compatible avec Flask FileStorage et PostgreSQL.
        """
        try:
            # Sécurité : on rembobine le curseur du fichier avant lecture
            file_storage.seek(0)
            pdf_content = file_storage.read()
            
            # Extraction du texte via pdfminer
            text = extract_text(io.BytesIO(pdf_content)).lower()
            
            if not text.strip():
                return 0.0, "Le fichier est illisible ou vide (vérifiez s'il s'agit d'un scan sous forme d'image)."

            score_total = 0.0
            piliers_trouves = []

            # Calcul du score par piliers (25 points max par catégorie)
            for nom_pilier, mots_cles in self.piliers.items():
                mots_presents = [mot for mot in mots_cles if mot in text]
                if mots_presents:
                    # Calcul proportionnel : (mots trouvés / total mots du pilier) * 25
                    contribution = (len(mots_presents) / len(mots_cles)) * 25
                    score_total += contribution
                    piliers_trouves.append(nom_pilier)

            # Arrondi du score final pour la base de données
            score_final = float(round(min(score_total, 100.0), 2))
            
            # Génération d'un feedback détaillé basé sur les résultats
            feedback = self.generer_feedback_dynamique(score_final, piliers_trouves)
            
            return score_final, feedback

        except Exception as e:
            print(f"Erreur technique IA : {e}")
            return 0.0, f"Erreur lors de l'analyse : {str(e)}. Vérifiez le format du PDF."

    def generer_feedback_dynamique(self, score, piliers_trouves):
        """Génère un diagnostic textuel basé sur le score et les piliers identifiés."""
        if score >= 80:
            msg = "Excellent ! Votre Business Plan est complet et structuré. "
            msg += f"Les piliers {', '.join(piliers_trouves)} sont bien documentés."
            return msg + " Votre projet présente un profil hautement bancable."
        
        elif score >= 50:
            msg = "Bonne base de travail. "
            if "Finance" not in piliers_trouves or "Risques" not in piliers_trouves:
                msg += "Cependant, vous devriez approfondir les sections financières et la gestion des risques. "
            return msg + "Votre projet a du potentiel mais nécessite des précisions pour rassurer un banquier."
        
        else:
            return ("Dossier trop incomplet. L'IA n'a pas détecté assez d'éléments clés sur la structure de votre projet. "
                    "Assurez-vous d'inclure des termes relatifs à la rentabilité, au marché et aux garanties.")

