# Groq API — Guide Complet d'Installation et Configuration
## Etape 1 — Créer un compte Groq et obtenir une clé API

### 1.1 Aller sur le site Groq

Ouvrez votre navigateur Windows et allez sur :

```
https://console.groq.com
```

### 1.2 Créer un compte

- Cliquez sur **Sign Up**
- Inscrivez-vous avec votre email Google ou une adresse email classique
- Confirmez votre email si demandé
- **Aucune carte bancaire requise**

### 1.3 Générer une clé API

Une fois connecté :

1. Dans le menu à gauche, cliquez sur **API Keys**
2. Cliquez sur **Create API Key**
3. Donnez un nom à votre clé : `superset-ai`
4. Cliquez sur **Submit**
5. **COPIEZ la clé immédiatement** — elle commence par `gsk_` et ne sera plus affichée après

```
Exemple: gsk_abc123xyz456def789...
```

> ⚠️ Gardez cette clé secrète. Ne la partagez jamais et ne la mettez pas dans un dépôt Git.

---

## Etape 2 — Tester la clé API depuis le terminal

Avant de modifier quoi que ce soit dans Superset, vérifiez que la clé fonctionne.

### Ouvrez un terminal WSL et activez l'environnement :

```bash
cd /home/hp/app
source env/bin/activate
```

### Testez la connexion à Groq :

```bash
curl -X POST https://api.groq.com/openai/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer gsk_VOTRE_CLE_ICI" \
     -d '{
       "model": "llama-3.3-70b-versatile",
       "messages": [
         {
           "role": "system",
           "content": "Tu es un expert SQL PostgreSQL. Reponds uniquement avec le SQL."
         },
         {
           "role": "user",
           "content": "Donne moi le score moyen par pays depuis la table vw_fatf_dashboard qui a les colonnes country, type, score_numeric"
         }
       ],
       "temperature": 0.1,
       "max_tokens": 300
     }'
```

### Réponse attendue (succès) :

```json
{
  "choices": [
    {
      "message": {
        "content": "SELECT country, AVG(score_numeric) AS score_moyen\nFROM vw_fatf_dashboard\nGROUP BY country\nORDER BY score_moyen DESC;"
      }
    }
  ]
}
```

Si vous voyez cette réponse → la clé fonctionne. Passez à l'étape 3.

Si vous voyez `invalid_api_key` → vérifiez que vous avez bien copié la clé depuis console.groq.com.

### Voir les modèles disponibles :

```bash
curl -H "Authorization: Bearer gsk_VOTRE_CLE_ICI" \
     https://api.groq.com/openai/v1/models \
     | python3 -m json.tool | grep '"id"'
```

---

## Etape 3 — Installer le package Python Groq (optionnel mais recommandé)

```bash
cd /home/hp/app
source env/bin/activate

pip install groq
```

Vérifiez l'installation :

```bash
pip show groq
```

Résultat attendu :

```
Name: groq
Version: 0.x.x
Location: /home/hp/app/env/lib/python3.10/site-packages
```

> Note : vous pouvez aussi utiliser `requests` directement sans ce package.
> Le package `groq` rend juste le code plus propre.

---

## Etape 4 — Modifier ai_api.py pour utiliser Groq

Remplacez entièrement le contenu du fichier `ai_api.py` :

```bash
cat > /home/hp/app/ai/ai_api.py << 'PYEOF'
import flask
import requests
from flask import request, jsonify
from flask_appbuilder import expose
from flask_appbuilder.views import BaseView

# ─────────────────────────────────────────────
# CONFIGURATION GROQ
# ─────────────────────────────────────────────
GROQ_API_KEY = "gsk_VOTRE_CLE_ICI"          # <-- remplacez par votre vraie clé
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
  - country      (VARCHAR) : nom du pays
  - type         (VARCHAR) : type de score (ex: TC, IO, etc.)
  - score_numeric (FLOAT)  : valeur numérique du score

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
PYEOF
```

### Remplacez la clé dans le fichier :

```bash
# Remplacez gsk_VOTRE_CLE_ICI par votre vraie clé
nano /home/hp/app/ai/ai_api.py
```

Dans nano :
- Trouvez la ligne `GROQ_API_KEY = "gsk_VOTRE_CLE_ICI"`
- Remplacez par votre vraie clé
- `Ctrl+O` pour sauvegarder
- `Ctrl+X` pour quitter

---

## Etape 5 — Vérifier que Ollama n'est plus nécessaire

Avec Groq, vous n'avez plus besoin de lancer Ollama.

```bash
# Arrêtez Ollama si il tourne encore
pkill ollama

# Vérifiez qu'il ne tourne plus
ps aux | grep ollama
# Ne doit plus apparaître
```

> ✅ Plus besoin de `ollama serve` dans un terminal séparé.
> Groq fonctionne via internet — assurez-vous juste d'avoir une connexion internet active.

---

## Etape 6 — Relancer Superset

```bash
cd /home/hp/app
source env/bin/activate

export SUPERSET_CONFIG_PATH=/home/hp/app/superset_config.py
export PYTHONPATH=/home/hp/app:$PYTHONPATH

superset run -p 8088 --reload --debugger
```

Résultat attendu (aucune erreur) :

```
Loaded your LOCAL configuration at [/home/hp/app/superset_config.py]
INFO  [superset.app] Configuration sync to database completed successfully
* Debugger is active!
* Running on http://127.0.0.1:8088
```

---

## Etape 7 — Tester le widget dans Superset

1. Ouvrez `http://localhost:8088` dans votre navigateur
2. Connectez-vous
3. Cliquez sur le bouton **🤖** en bas à droite
4. Tapez une question : `Score moyen par pays`
5. Cliquez sur **Générer SQL**
6. En **1-2 secondes** le SQL apparaît

### Tester depuis le terminal aussi :

```bash
curl -X POST http://localhost:8088/ai/generate \
     -H "Content-Type: application/json" \
     -d '{"question": "top 5 pays avec le score le plus haut"}'
```

Résultat attendu :

```json
{
  "sql": "SELECT country, MAX(score_numeric) AS max_score\nFROM vw_fatf_dashboard\nGROUP BY country\nORDER BY max_score DESC\nLIMIT 5;"
}
```

---

## Etape 8 — Adapter le contexte à vos vraies tables (important)

Pour que Groq génère du SQL correct, il faut lui donner le bon contexte.
Modifiez le bloc `DB_CONTEXT` dans `ai_api.py` :

```bash
nano /home/hp/app/ai/ai_api.py
```

Trouvez ce bloc et adaptez-le à vos tables réelles :

```python
DB_CONTEXT = """
Tu es un expert SQL PostgreSQL.
Tu travailles avec la base de données suivante :

Table: vw_fatf_dashboard
Colonnes:
  - country      (VARCHAR) : nom du pays
  - type         (VARCHAR) : type (TC, IO, R1, R2...)
  - score_numeric (FLOAT)  : score numérique entre 0 et 1

-- Ajoutez vos autres tables ici si nécessaire :
-- Table: autre_table
-- Colonnes: col1, col2, col3

Règles:
  - Réponds UNIQUEMENT avec le SQL
  - Syntaxe PostgreSQL
  - Pas de markdown ni backticks
"""
```

---

## Résumé des commandes

```bash
# 1. Activer l'environnement
cd /home/hp/app && source env/bin/activate

# 2. Installer le package groq (une seule fois)
pip install groq

# 3. Modifier ai_api.py avec votre clé Groq
nano /home/hp/app/ai/ai_api.py

# 4. Lancer Superset (seul terminal nécessaire, plus besoin d'Ollama)
export SUPERSET_CONFIG_PATH=/home/hp/app/superset_config.py
export PYTHONPATH=/home/hp/app:$PYTHONPATH
superset run -p 8088 --reload --debugger

# 5. Tester depuis le terminal
curl -X POST http://localhost:8088/ai/generate \
     -H "Content-Type: application/json" \
     -d '{"question": "score moyen TC"}'
```

---

## Limites du tier gratuit Groq (2026)

| Limite | Valeur |
|--------|--------|
| Requêtes par minute | 30 |
| Requêtes par jour | 14 400 |
| Tokens par minute | 6 000 |
| Carte bancaire requise | ❌ Non |
| Modèles disponibles | Llama 3.3 70B, Llama 3.1 8B, Llama 4, Qwen3... |

> Pour un usage interne en entreprise avec peu d'utilisateurs simultanés, le tier gratuit est largement suffisant.

---

## Dépannage rapide

| Erreur | Cause | Solution |
|--------|-------|----------|
| `invalid_api_key` | Mauvaise clé | Vérifiez GROQ_API_KEY dans ai_api.py |
| `rate_limit_exceeded` | Trop de requêtes | Attendez 1 minute |
| `Connection refused` | Pas d'internet | Vérifiez votre connexion réseau |
| `400 Bad Request` | CSRF actif | Vérifiez WTF_CSRF_ENABLED = False dans superset_config.py |
| SQL incorrect | Contexte incomplet | Enrichissez DB_CONTEXT avec vos vraies colonnes |

---

*Guide d'intégration Groq API — Module AI SQL Generator pour Apache Superset*
