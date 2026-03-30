const btn = document.getElementById('refresh-quote');

if (btn) {
    btn.addEventListener('click', function () {
        fetch('/random-quote')
            .then(response => response.json())
            .then(data => {
                document.getElementById('quote-content').innerHTML = data.quote_html;
                document.getElementById('quote-source').innerHTML = data.source;
            });
    });
}