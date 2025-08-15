// File: assets/cytoscape_mouse.js
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        var cyContainer = document.getElementById('network-topology-graph');
        if (cyContainer) {
            cyContainer.addEventListener('mousemove', function(e) {
                var rect = cyContainer.getBoundingClientRect();
                // Calculate mouse position relative to the Cytoscape container
                var x = e.clientX - rect.left;
                var y = e.clientY - rect.top;
                // Get the hidden store for mouse coordinates
                var mouseStore = document.getElementById('mouse-pos-store');
                if (mouseStore) {
                    // Store the coordinates as a JSON string
                    mouseStore.value = JSON.stringify({x: x, y: y});
                    // Dispatch an input event to notify Dash of the update
                    var event = new Event('input', { bubbles: true });
                    mouseStore.dispatchEvent(event);
                }
            });
        }
    });
})();
