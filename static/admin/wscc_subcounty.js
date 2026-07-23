(function() {
    // Admin dependent select: sub_county -> ward
    function $(sel){return document.querySelector(sel)}
    function $all(sel){return Array.from(document.querySelectorAll(sel))}

    function init() {
        var sc = $('#id_sub_county');
        var ward = $('#id_ward');
        var role = $('#id_role');
        if (!sc || !ward) return;

        var mapping = {};
        try {
            mapping = JSON.parse(sc.getAttribute('data-wards') || '{}');
        } catch(e) { mapping = {}; }

        function populateWards(selectedSC) {
            // preserve current value
            var current = ward.value;
            // clear
            while (ward.firstChild) ward.removeChild(ward.firstChild);
            // empty option
            var empty = document.createElement('option');
            empty.value = '';
            empty.text = '---------';
            ward.appendChild(empty);

            var wards = mapping[selectedSC] || [];
            wards.forEach(function(w){
                var opt = document.createElement('option');
                opt.value = w;
                opt.text = w;
                ward.appendChild(opt);
            });
            // restore if still valid
            if (current) {
                var found = Array.from(ward.options).some(function(o){ return o.value === current; });
                if (found) ward.value = current;
            }
        }

        // On load, if sub_county has a value, populate wards
        if (sc.value) populateWards(sc.value);

        sc.addEventListener('change', function(){
            populateWards(this.value);
        });

        // Optional: if role is not WSCC, don't force selection; but we still allow picking
        if (role) {
            role.addEventListener('change', function(){
                // If role changed to ward_sports_council_chair, ensure sub_county hint shown
                if (this.value === 'ward_sports_council_chair') {
                    // focus sub_county to nudge admin
                    sc.focus();
                }
            });
        }
    }

    // Wait for DOM ready in Django admin
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
