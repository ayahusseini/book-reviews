const buttons = document.querySelectorAll('#refresh-quote, #refresh-quote-mobile');

buttons.forEach(btn => {
    btn.addEventListener('click', function () {
        fetch('/random-quote')
            .then(response => response.json())
            .then(data => {
                // Update desktop if it exists
                const content = document.getElementById('quote-content');
                const source = document.getElementById('quote-source');

                if (content) content.innerHTML = data.quote_html;
                if (source) source.innerHTML = data.source;

                // Update mobile if it exists
                const mobileContent = document.querySelector('.mobile-quote blockquote');
                const mobileSource = document.querySelector('.mobile-quote .sidebar-quote-source');

                if (mobileContent) mobileContent.innerHTML = data.quote_html;
                if (mobileSource) mobileSource.innerHTML = data.source;
            });
    });
});