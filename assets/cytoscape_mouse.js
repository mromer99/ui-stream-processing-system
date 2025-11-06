(function() {
    document.addEventListener('DOMContentLoaded', function() {
        var cyContainer = document.getElementById('network-topology-graph');
        if (cyContainer) {
            cyContainer.addEventListener('mousemove', function(e) {
                var rect = cyContainer.getBoundingClientRect();
                var x = e.clientX - rect.left;
                var y = e.clientY - rect.top;
                var mouseStore = document.getElementById('mouse-pos-store');
                if (mouseStore) {
                    mouseStore.value = JSON.stringify({x: x, y: y});
                    var event = new Event('input', { bubbles: true });
                    mouseStore.dispatchEvent(event);
                }
            });
        }
    });
})();
