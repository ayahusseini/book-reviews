/**
 * Random quote widget — fetches all quotes once from /quotes.json and
 * picks one at random, both on page load and on refresh-button click.
 *
 * Each entry in quotes.json is shaped:
 *   { quote_html: "<p>...</p>", book_title: "...", book_url: "/books/.../" }
 */

let cachedQuotes = null;

function updateQuoteWidgets(quoteHtml, sourceHtml) {
    const desktopBody = document.getElementById('quote-content');
    const desktopSource = document.getElementById('quote-source');
    if (desktopBody) desktopBody.innerHTML = quoteHtml;
    if (desktopSource) desktopSource.innerHTML = sourceHtml;

    const mobileBody = document.getElementById('quote-content-mobile');
    const mobileSource = document.getElementById('quote-source-mobile');
    if (mobileBody) mobileBody.innerHTML = quoteHtml;
    if (mobileSource) mobileSource.innerHTML = sourceHtml;
}

function pickRandomQuote(quotes) {
    if (!quotes.length) return null;
    return quotes[Math.floor(Math.random() * quotes.length)];
}

function showRandomQuote(quotes) {
    const quote = pickRandomQuote(quotes);
    if (!quote) return;
    const sourceHtml = `— <a href="${quote.book_url}">${quote.book_title}</a>`;
    updateQuoteWidgets(quote.quote_html, sourceHtml);
}

function loadQuotes() {
    if (cachedQuotes) return Promise.resolve(cachedQuotes);
    return fetch('/quotes.json')
        .then(function (response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(function (quotes) {
            cachedQuotes = quotes;
            return quotes;
        });
}

function refreshQuote() {
    loadQuotes()
        .then(showRandomQuote)
        .catch(function (err) {
            console.error('Failed to refresh quote:', err);
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const desktopBtn = document.getElementById('refresh-quote');
    const mobileBtn = document.getElementById('refresh-quote-mobile');

    if (desktopBtn) desktopBtn.addEventListener('click', refreshQuote);
    if (mobileBtn) mobileBtn.addEventListener('click', refreshQuote);

    refreshQuote();
});
