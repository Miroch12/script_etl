import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append('/home/hp/app')
from explain_plugin import ExplainView
def init_app(app):
    from superset.extensions import appbuilder
    from explain_plugin import ExplainView
    try:
        appbuilder.add_view(
            ExplainView,
            "Explain SQL",
            label="Explain SQL",
            icon="fa-brain",
            category="Tools"
        )
        print("✅ Plugin Explain SQL chargé")
    except Exception as e:
        print("❌ ERREUR:", e)
SECRET_KEY = 'ngrzlKuaSZhVimhMfxW1eA9hA7uvv4QyfnBr7aqO9U6XQOWJJjX8vvgQ'

WTF_CSRF_ENABLED = False

# Liste des endpoints exemptés de CSRF (corrigé)
WTF_CSRF_EXEMPT_LIST = ["ai.ai_api.AIView.generate"]

from superset.initialization import SupersetAppInitializer
from superset.extensions import appbuilder

FLOATING_AI_WIDGET = """<style>
#ai-fab {position:fixed;bottom:30px;right:30px;z-index:99999;width:56px;height:56px;border-radius:28px;background:#00A699;color:white;border:none;cursor:pointer;font-size:24px;box-shadow:0 2px 10px rgba(0,0,0,0.2);transition:transform 0.2s;}
#ai-fab:hover {transform:scale(1.1);}
#ai-panel {display:none;position:fixed;bottom:100px;right:30px;width:400px;max-width:90vw;background:white;border-radius:10px;box-shadow:0 5px 20px rgba(0,0,0,0.3);z-index:99998;}
#ai-panel-header {background:#00A699;color:white;padding:15px 20px;border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;}
#ai-close {cursor:pointer;font-size:20px;background:none;border:none;color:white;font-weight:bold;}
#ai-panel-body {padding:20px;}
#ai-input {width:100%;padding:10px;font-size:14px;border:1px solid #ddd;border-radius:5px;font-family:monospace;min-height:80px;}
#ai-send {margin-top:10px;width:100%;padding:10px;background:#00A699;color:white;border:none;border-radius:5px;cursor:pointer;font-size:14px;font-weight:bold;}
#ai-send:hover {background:#008f84;}
#ai-send:disabled {background:#aaa;cursor:not-allowed;}
#ai-result {margin-top:15px;background:#1e1e1e;color:#00ff99;padding:10px;border-radius:5px;font-family:monospace;font-size:12px;overflow-x:auto;white-space:pre-wrap;display:none;}
#ai-status {font-size:12px;color:#666;margin-top:5px;}
</style>
<button id="ai-fab" title="AI SQL Generator">🤖</button>
<div id="ai-panel">
  <div id="ai-panel-header">
    <span>🤖 AI SQL Generator</span>
    <button id="ai-close">✕</button>
  </div>
  <div id="ai-panel-body">
    <textarea id="ai-input" placeholder="Ex: Quels sont les 10 pays avec le meilleur score ?" rows="4"></textarea>
    <div id="ai-status"></div>
    <button id="ai-send">✨ Generer SQL</button>
    <pre id="ai-result"></pre>
  </div>
</div>
<script nonce="NONCE_PLACEHOLDER">
(function() {
    var fab = document.getElementById('ai-fab');
    var panel = document.getElementById('ai-panel');
    var close = document.getElementById('ai-close');
    var send = document.getElementById('ai-send');
    var input = document.getElementById('ai-input');
    var result = document.getElementById('ai-result');
    var status = document.getElementById('ai-status');
    
    fab.addEventListener('click', function() {
        panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
    });
    
    close.addEventListener('click', function() {
        panel.style.display = 'none';
    });
    
    send.addEventListener('click', async function() {
        var q = input.value.trim();
        if (!q) {
            status.textContent = 'Veuillez saisir une question';
            return;
        }
        send.disabled = true;
        send.textContent = 'Génération...';
        result.style.display = 'none';
        status.textContent = 'Génération du SQL en cours...';
        
        try {
            var res = await fetch('/ai/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({question: q})
            });
            var data = await res.json();
            if (data.sql) {
                result.textContent = data.sql;
                result.style.display = 'block';
                status.textContent = '✅ SQL généré avec succès !';
            } else {
                result.textContent = 'Erreur: ' + (data.error || 'Erreur inconnue');
                result.style.display = 'block';
                status.textContent = '❌ Erreur';
            }
        } catch(e) {
            result.textContent = 'Erreur: ' + e.message;
            result.style.display = 'block';
            status.textContent = '❌ Erreur réseau';
        } finally {
            send.disabled = false;
            send.textContent = '✨ Generer SQL';
        }
    });
})();
</script>"""

class CustomAppInitializer(SupersetAppInitializer):
    def __init__(self, app):
        super().__init__(app)

    def init_views(self):
        super().init_views()
        from ai.ai_api import AIView
        appbuilder.add_view(
            AIView,
            "AI SQL Generator",
            label="AI SQL Generator",
            icon="fa-magic",
            category="AI Tools",
            category_label="AI Tools",
            category_icon="fa-robot",
        )

    def init_app(self):
        super().init_app()

        @self.superset_app.after_request
        def inject_ai_widget(response):
            if response.content_type and response.content_type.startswith('text/html'):
                try:
                    import flask
                    nonce = getattr(flask.request, 'csp_nonce', '')
                    widget = FLOATING_AI_WIDGET.replace('NONCE_PLACEHOLDER', nonce)
                    content = response.get_data(as_text=True)
                    if '</body>' in content:
                        content = content.replace('</body>', widget + '</body>')
                        response.set_data(content)
                except Exception as e:
                    print(f"Erreur injection widget: {e}")
            return response

APP_INITIALIZER = CustomAppInitializer









