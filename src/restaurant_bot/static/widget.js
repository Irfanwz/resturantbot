/**
 * Restaurant Bot - Embeddable Chat Widget
 * Usage: <script src="https://yourbot.com/static/widget.js" data-restaurant="RESTAURANT_ID"></script>
 */
(function() {
    const script = document.currentScript;
    const RESTAURANT_ID = script.getAttribute('data-restaurant');
    const API_BASE = script.src.replace('/static/widget.js', '');
    const PRIMARY_COLOR = script.getAttribute('data-color') || '#FF6B35';
    let SESSION_ID = 'widget-' + Math.random().toString(36).substr(2, 9);
    let isOpen = false;

    // Inject CSS
    const style = document.createElement('style');
    style.textContent = `
        #rb-widget-btn {
            position: fixed; bottom: 24px; right: 24px; z-index: 99999;
            width: 60px; height: 60px; border-radius: 50%;
            background: ${PRIMARY_COLOR}; border: none; cursor: pointer;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2); font-size: 28px;
            display: flex; align-items: center; justify-content: center;
            transition: transform 0.3s; color: white;
        }
        #rb-widget-btn:hover { transform: scale(1.08); }
        #rb-widget-frame {
            position: fixed; bottom: 96px; right: 24px; z-index: 99998;
            width: 380px; height: 560px; border: none; border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2); display: none;
            overflow: hidden; background: white;
        }
        #rb-widget-frame.open { display: block; animation: rbSlideUp 0.3s ease; }
        @keyframes rbSlideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 480px) {
            #rb-widget-frame {
                width: calc(100vw - 16px); height: calc(100vh - 80px);
                bottom: 8px; right: 8px; border-radius: 12px;
            }
        }
    `;
    document.head.appendChild(style);

    // Create button
    const btn = document.createElement('button');
    btn.id = 'rb-widget-btn';
    btn.innerHTML = '💬';
    btn.onclick = function() {
        isOpen = !isOpen;
        frame.classList.toggle('open', isOpen);
        btn.innerHTML = isOpen ? '✕' : '💬';
    };
    document.body.appendChild(btn);

    // Create iframe
    const frame = document.createElement('iframe');
    frame.id = 'rb-widget-frame';
    frame.src = API_BASE + '/static/chat.html?restaurant_id=' + RESTAURANT_ID;
    document.body.appendChild(frame);
})();
