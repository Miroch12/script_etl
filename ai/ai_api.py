import flask
import requests
from flask import request, jsonify
from flask_appbuilder import expose
from flask_appbuilder.views import BaseView

# ─────────────────────────────────────────────
# CONFIGURATION GROQ
# ─────────────────────────────────────────────
GROQ_API_KEY = " "          # <-- remplacez par votre vraie clé
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"    # meilleur modèle SQL disponible

# ─────────────────────────────────────────────
# CONTEXTE DE VOTRE BASE DE DONNÉES
# Adaptez ce bloc à vos vraies tables et colonnes
# ─────────────────────────────────────────────
DB_CONTEXT = """
Tu es un expert SQL PostgreSQL.
Tu travailles avec la base de données suivante :

Table: vw_fatf_dashboard
Colonnes:
  - country_id    (BIGINT)                    : identifiant unique du pays
  - country       (TEXT)                      : nom du pays
  - continent     (TEXT)                      : nom du continent
  - report_date   (TIMESTAMP WITHOUT TIME ZONE): date du rapport
  - metric_code   (TEXT)                      : code de la métrique
  - type          (TEXT)                      : type de score (ex: TC, IO, R1...)
  - score_numeric (DOUBLE PRECISION)          : valeur numérique du score
Règles:
  - Réponds UNIQUEMENT avec le code SQL, sans explication
  - N'ajoute pas de markdown, pas de ``` , pas de commentaires
  - Utilise la syntaxe PostgreSQL
  - Si la question n'est pas claire, génère une requête SELECT générale
"""

class AIView(BaseView):
    route_base = "/ai"
    default_view = "index"

    @expose("/")
    def index(self):
        return "AI actif"

    @expose("/generate", methods=["GET", "POST"])
    def generate(self):
        if flask.request.method != "POST":
            return jsonify({"status": "ok"})

        try:
            # 1. Lire la question envoyée par le widget
            data = request.get_json(force=True, silent=True) or {}
            question = data.get("question", "").strip()

            if not question:
                return jsonify({"error": "Question vide"}), 400

            # 2. Préparer l'appel à l'API Groq
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": DB_CONTEXT
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "temperature": 0.1,    # 0.1 = réponses stables et précises
                "max_tokens": 500      # suffisant pour une requête SQL
            }

            # 3. Envoyer la requête à Groq (timeout 30s car Groq est rapide)
            resp = requests.post(
                GROQ_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            resp.raise_for_status()

            # 4. Extraire le SQL de la réponse
            sql = resp.json()["choices"][0]["message"]["content"].strip()

            # 5. Nettoyer le SQL si le modèle a quand même ajouté des backticks
            sql = sql.replace("```sql", "").replace("```", "").strip()

            return jsonify({"sql": sql})

        except requests.exceptions.Timeout:
            return jsonify({"error": "Groq ne répond pas — réessayez dans quelques secondes"}), 504

        except requests.exceptions.ConnectionError:
            return jsonify({"error": "Impossible de joindre l'API Groq — vérifiez votre connexion internet"}), 503

        except requests.exceptions.HTTPError as e:
            if resp.status_code == 401:
                return jsonify({"error": "Clé API Groq invalide — vérifiez GROQ_API_KEY dans ai_api.py"}), 401
            if resp.status_code == 429:
                return jsonify({"error": "Limite Groq atteinte — attendez 1 minute et réessayez"}), 429
            return jsonify({"error": f"Erreur Groq HTTP {resp.status_code}"}), 500

        except KeyError:
            return jsonify({"error": "Réponse Groq inattendue — format inconnu"}), 500

        except Exception as e:
            return jsonify({"error": str(e)}), 500
