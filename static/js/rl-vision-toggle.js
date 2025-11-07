/**
 * RL Vision Monitor Toolbar Toggle
 * Allows showing/hiding the entire RL Vision Monitor from the toolbar
 */

document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('rlVisionToggleBtn');
    const monitor = document.getElementById('rlVisionMonitor');

    if (!toggleBtn || !monitor) {
        console.warn('[RLVision] Toggle button or monitor not found');
        return;
    }

    // Restore visibility state from localStorage (default: visible)
    const savedState = localStorage.getItem('rlVisionVisible');
    const isVisible = savedState === null ? true : savedState === 'true';

    // Apply initial state
    if (!isVisible) {
        monitor.classList.add('hidden');
        toggleBtn.classList.remove('active');
        toggleBtn.querySelector('.ai-status').textContent = 'AUS';
    } else {
        monitor.classList.remove('hidden');
        toggleBtn.classList.add('active');
        toggleBtn.querySelector('.ai-status').textContent = 'AN';
    }

    // Toggle click handler
    toggleBtn.addEventListener('click', function() {
        const isCurrentlyVisible = !monitor.classList.contains('hidden');

        if (isCurrentlyVisible) {
            // Hide monitor
            monitor.classList.add('hidden');
            toggleBtn.classList.remove('active');
            toggleBtn.querySelector('.ai-status').textContent = 'AUS';
            localStorage.setItem('rlVisionVisible', 'false');
            console.log('[RLVision] Monitor hidden');
        } else {
            // Show monitor
            monitor.classList.remove('hidden');
            toggleBtn.classList.add('active');
            toggleBtn.querySelector('.ai-status').textContent = 'AN';
            localStorage.setItem('rlVisionVisible', 'true');
            console.log('[RLVision] Monitor visible');
        }
    });

    console.log('[RLVision] Toolbar toggle initialized');
});
