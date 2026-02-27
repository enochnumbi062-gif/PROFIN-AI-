import io
from pdfminer.high_level import extract_text

class ProfinIA:
    def __init__(self):
        # Critères de bancabilité pour le marché africain/congolais
        self.criteres = {
            "finance": ["chiffre d'affaires", "rentabilité", "investissement", "flux de trésorerie", "bilan", "prévisions"],
            "marche": ["concurrence", "cible", "clientèle", "secteur", "croissance", "demande"],
            "operationnel": ["équipe", "stratégie", "ressources humaines", "logistique", "production"],
            "risques": ["mitigation", "garantie", "risques", "plan de secours"]
        }

    def analyser_pdf(self, pdf_file):
        # Extraction du texte du PDF
        text = extract_text(io.BytesIO(pdf_file.read())).lower()
        
        score_total = 0
        details_analyse = {}

        # Analyse par pilier
        for pilier, mots_cles in self.criteres.items():
            presents = [mot for mot in mots_cles if mot in text]
            poids = (len(presents) / len(mots_cles)) * 25 # Chaque pilier vaut 25%
            score_total += poids
            details_analyse[pilier] = len(presents)

        # Logique de scoring ajustée
        score_final = round(min(score_total, 100), 2)
        
        # Génération d'un commentaire automatique
        commentaire = self.generer_feedback(score_final, details_analyse)
        
        return score_final, commentaire

    def generer_feedback(self, score, details):
        if score < 40:
            return "Projet trop embryonnaire. Manque de détails financiers et structurels."
        elif score < 75:
            return "Bonne base, mais vous devez renforcer la partie 'Risques' et 'Prévisions Financières' pour rassurer les banques."
        else:
            return "Excellent dossier ! Votre projet présente une maturité solide pour une demande de financement."
