/* ═══════════════════════════════════════════════════════════════════════════
   KYISA — Main JS (Public Website + CMS Portal)
   ═══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {

    // ── Staggered entrance animations ────────────────────────────────────
    // Cards, stat cards, action cards, table rows — appear one by one
    const staggerTargets = document.querySelectorAll(
        '.stat-card, .action-card, .card, .table-responsive'
    );
    staggerTargets.forEach(function (el, i) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(12px)';
        el.style.transition = 'opacity .35s ease, transform .35s ease';
        setTimeout(function () {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 60 + i * 55);
    });

    // ── Auto-dismiss alerts with slide-out ──────────────────────────────
    document.querySelectorAll('.alert').forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity .35s ease, transform .35s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-8px)';
            setTimeout(function () { alert.remove(); }, 350);
        }, 4500);
        // Manual close
        const closeBtn = alert.querySelector('.alert-close, [data-dismiss]');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                alert.style.transition = 'opacity .25s ease';
                alert.style.opacity = '0';
                setTimeout(function () { alert.remove(); }, 250);
            });
        }
    });

    // ── Mobile nav toggle (hamburger) ────────────────────────────────────
    var navToggle = document.querySelector('.nav-toggle');
    var navMenu = document.querySelector('.navbar-nav');
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function () {
            navMenu.classList.toggle('show');
            this.setAttribute('aria-expanded', navMenu.classList.contains('show'));
        });
    }
    // Public site mobile toggle
    var pubNavToggle = document.querySelector('.pub-nav-toggle, .fkf-nav-toggle');
    var pubNavLinks = document.querySelector('.pub-nav-links, .fkf-nav-links');
    if (pubNavToggle && pubNavLinks) {
        pubNavToggle.addEventListener('click', function () {
            pubNavLinks.classList.toggle('show');
            pubNavLinks.classList.toggle('open');
        });
    }

    // ── Navbar dropdowns: hover on desktop, click on mobile ──────────────
    document.querySelectorAll('.navbar-nav > li').forEach(function (li) {
        var dropdown = li.querySelector('.nav-dropdown-menu');
        if (!dropdown) return;
        var timeout;
        li.addEventListener('mouseenter', function () {
            if (window.innerWidth > 768) {
                clearTimeout(timeout);
                closeAllNavDropdowns();
                li.classList.add('open');
            }
        });
        li.addEventListener('mouseleave', function () {
            if (window.innerWidth > 768) {
                timeout = setTimeout(function () { li.classList.remove('open'); }, 180);
            }
        });
        // Touch / mobile click
        var link = li.querySelector(':scope > a');
        if (link) {
            link.addEventListener('click', function (e) {
                if (window.innerWidth <= 768 && dropdown) {
                    e.preventDefault();
                    var wasOpen = li.classList.contains('open');
                    closeAllNavDropdowns();
                    if (!wasOpen) li.classList.add('open');
                }
            });
        }
    });

    function closeAllNavDropdowns() {
        document.querySelectorAll('.navbar-nav > li.open').forEach(function (li) {
            li.classList.remove('open');
        });
    }
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.navbar-nav')) closeAllNavDropdowns();
    });

    // ── Sidebar collapsible sections ─────────────────────────────────────
    document.querySelectorAll('.sidebar-section-toggle').forEach(function (toggle) {
        toggle.addEventListener('click', function () {
            var section = toggle.closest('.sidebar-section');
            if (section) section.classList.toggle('collapsed');
        });
    });

    // ── Sortable table headers ───────────────────────────────────────────
    document.querySelectorAll('table thead th[data-sort]').forEach(function (th) {
        th.style.cursor = 'pointer';
        th.setAttribute('role', 'button');
        th.addEventListener('click', function () {
            var table = th.closest('table');
            var tbody = table.querySelector('tbody');
            var rows = Array.from(tbody.querySelectorAll('tr'));
            var idx = Array.from(th.parentNode.children).indexOf(th);
            var asc = !th.classList.contains('sort-asc');
            th.parentNode.querySelectorAll('th').forEach(function (t) {
                t.classList.remove('sort-asc', 'sort-desc');
            });
            th.classList.add(asc ? 'sort-asc' : 'sort-desc');
            rows.sort(function (a, b) {
                var at = (a.children[idx] || {}).textContent || '';
                var bt = (b.children[idx] || {}).textContent || '';
                return asc ? at.localeCompare(bt, undefined, { numeric: true }) :
                             bt.localeCompare(at, undefined, { numeric: true });
            });
            rows.forEach(function (row) { tbody.appendChild(row); });
        });
    });

    // ── Counter animation for public stats section ───────────────────────
    var counters = document.querySelectorAll('.counter-item h3[data-target]');
    if (counters.length) {
        function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
        function animateCounter(el) {
            var target = parseInt(el.getAttribute('data-target')) || 0;
            var duration = 1800;
            var start = performance.now();
            function tick(now) {
                var elapsed = Math.min((now - start) / duration, 1);
                el.textContent = Math.round(easeOutCubic(elapsed) * target);
                if (elapsed < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        }
        if ('IntersectionObserver' in window) {
            var obs = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        animateCounter(entry.target);
                        obs.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.5 });
            counters.forEach(function (c) { obs.observe(c); });
        } else {
            counters.forEach(animateCounter);
        }
    }

    // ── Smooth scroll for anchor links ───────────────────────────────────
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ── Keyboard shortcut: Ctrl+K to focus search ────────────────────────
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            var search = document.querySelector('.toolbar-search input');
            if (search) search.focus();
        }
    });

    // ── Ripple effect on primary buttons ─────────────────────────────────
    document.querySelectorAll('.btn-primary').forEach(function (btn) {
        btn.style.position = 'relative';
        btn.style.overflow = 'hidden';
        btn.addEventListener('click', function (e) {
            var rect = btn.getBoundingClientRect();
            var ripple = document.createElement('span');
            var size = Math.max(rect.width, rect.height);
            ripple.style.cssText =
                'position:absolute;border-radius:50%;background:rgba(255,255,255,.35);' +
                'width:' + size + 'px;height:' + size + 'px;' +
                'left:' + (e.clientX - rect.left - size / 2) + 'px;' +
                'top:' + (e.clientY - rect.top - size / 2) + 'px;' +
                'transform:scale(0);animation:ripple .5s ease-out forwards;pointer-events:none;';
            btn.appendChild(ripple);
            setTimeout(function () { ripple.remove(); }, 600);
        });
    });
});
