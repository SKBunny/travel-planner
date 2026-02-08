// ==================== ТЕМНА ТЕМА ====================

const themeToggle = document.getElementById('themeToggle');

const savedTheme = localStorage.getItem('theme') || 'light';
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
}

if (themeToggle) {
    themeToggle.addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');

        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        const icon = this.querySelector('i');
        if (icon) {
            icon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
        }
    });
}

// ==================== ШВИДКИЙ ПОШУК ====================

const searchInput = document.getElementById('globalSearch');
const quickResults = document.getElementById('quickResults');

if (searchInput && quickResults) {
    let searchTimeout;

    searchInput.addEventListener('input', function() {
        const query = this.value.trim();

        clearTimeout(searchTimeout);

        if (query.length < 2) {
            quickResults.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(() => {
            fetch('/api/quick-search?q=' + encodeURIComponent(query))
                .then(response => response.json())
                .then(data => {
                    if (data.results && data.results.length > 0) {
                        showQuickResults(data.results);
                    } else {
                        quickResults.innerHTML = '<div class="p-3 text-muted text-center">Нічого не знайдено</div>';
                        quickResults.style.display = 'block';
                    }
                })
                .catch(error => {
                    console.error('Помилка пошуку:', error);
                });
        }, 300);
    });

    function showQuickResults(results) {
        let html = '';

        results.forEach(result => {
            html += '<a href="' + result.url + '" class="quick-search-item">';
            html += '<span class="result-icon">' + result.icon + '</span>';
            html += '<div class="result-content">';
            html += '<div class="result-title">' + highlightMatch(result.title, searchInput.value) + '</div>';
            html += '<div class="result-subtitle">' + result.subtitle + '</div>';
            html += '</div></a>';
        });

        html += '<a href="/search?q=' + encodeURIComponent(searchInput.value) + '" class="quick-search-item view-all">';
        html += '<i class="bi bi-search"></i> Показати всі результати</a>';

        quickResults.innerHTML = html;
        quickResults.style.display = 'block';
    }

    function highlightMatch(text, query) {
        const regex = new RegExp('(' + query + ')', 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    document.addEventListener('click', function(e) {
        if (searchInput && !searchInput.contains(e.target) && quickResults && !quickResults.contains(e.target)) {
            quickResults.style.display = 'none';
        }
    });

    searchInput.addEventListener('focus', function() {
        if (quickResults && quickResults.innerHTML && this.value.length >= 2) {
            quickResults.style.display = 'block';
        }
    });
}

// ==================== ГАРЯЧА КЛАВІША ====================

document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const search = document.getElementById('globalSearch');
        if (search) {
            search.focus();
            search.select();
        }
    }
});

// ==================== TOOLTIPS ====================

document.addEventListener('DOMContentLoaded', function() {
    if (typeof bootstrap !== 'undefined') {
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(el => new bootstrap.Tooltip(el));
    }
});

console.log('Travel Planner JS loaded!');