document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('btn').addEventListener('click', async function() {
        const q = document.getElementById('q').value;
        document.getElementById('result').textContent = 'Generating...';
        const res = await fetch('/ai/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: q})
        });
        const data = await res.json();
        document.getElementById('result').textContent = data.sql || data.error;
    });
});
