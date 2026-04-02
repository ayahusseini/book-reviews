/**
 * Quote refresh — handles both the sidebar widget (desktop) and the
 * mobile slot widget with a single fetch per click.
 *
 * The response from /random-quote returns:
 *   { quote_html: "<p>...</p>", source: "— From book: <a>...</a>" }
 */

function updateQuoteWidgets(quoteHtml, sourceHtml) {
    // Desktop sidebar
    const desktopBody   = document.getElementById('quote-content');
    const desktopSource = document.getElementById('quote-source');
    if (desktopBody)   desktopBody.innerHTML   = quoteHtml;
    if (desktopSource) desktopSource.innerHTML = sourceHtml;

    // Mobile slot
    const mobileBody   = document.getElementById('quote-content-mobile');
    const mobileSource = document.getElementById('quote-source-mobile');
    if (mobileBody)   mobileBody.innerHTML   = quoteHtml;
    if (mobileSource) mobileSource.innerHTML = sourceHtml;
}

function fetchAndRefresh() {
    fetch('/random-quote')
        .then(function(response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(function(data) {
            updateQuoteWidgets(data.quote_html || '', data.source || '');
        })
        .catch(function(err) {
            console.error('Failed to refresh quote:', err);
        });
}

document.addEventListener('DOMContentLoaded', function () {
    var desktopBtn = document.getElementById('refresh-quote');
    var mobileBtn  = document.getElementById('refresh-quote-mobile');

    if (desktopBtn) desktopBtn.addEventListener('click', fetchAndRefresh);
    if (mobileBtn)  mobileBtn.addEventListener('click', fetchAndRefresh);
});