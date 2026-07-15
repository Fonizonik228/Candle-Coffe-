// Auto-submit the avatar form as soon as a file is chosen.
document.addEventListener('DOMContentLoaded', function () {
  var avatarInput = document.getElementById('avatarInput');
  if (avatarInput) {
    avatarInput.addEventListener('change', function () {
      if (avatarInput.files && avatarInput.files.length) {
        avatarInput.closest('form').submit();
      }
    });
  }

  // Poll the unread-count endpoint every 8s so badges update without a manual refresh.
  var badge = document.getElementById('liveBadge');
  if (badge) {
    setInterval(function () {
      fetch('/api/unread-count/')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.count > 0) {
            badge.style.display = 'flex';
            badge.textContent = data.count;
          } else {
            badge.style.display = 'none';
          }
        })
        .catch(function () {});
    }, 8000);
  }

  // Auto-scroll chat windows to the latest message.
  var chatBox = document.querySelector('.chat-messages');
  if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

  // Rotate each product's photo gallery every 10s (slight stagger so cards don't all flip in sync).
  document.querySelectorAll('.ticket-media').forEach(function (media, idx) {
    var imgs = media.querySelectorAll('.ticket-img');
    if (imgs.length <= 1) return;
    var current = 0;
    setInterval(function () {
      imgs[current].classList.remove('active');
      current = (current + 1) % imgs.length;
      imgs[current].classList.add('active');
    }, 10000 + (idx % 5) * 200);
  });

  // Reveal sections as they scroll into view, hide them again when scrolled past
  // (works both scrolling down and scrolling back up).
  var revealEls = document.querySelectorAll('.reveal');
  if (revealEls.length) {
    if ('IntersectionObserver' in window) {
      var revealObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          entry.target.classList.toggle('in-view', entry.isIntersecting);
        });
      }, { threshold: 0.18 });
      revealEls.forEach(function (el) { revealObserver.observe(el); });
    } else {
      revealEls.forEach(function (el) { el.classList.add('in-view'); });
    }
  }

  // Live order tracking: poll each active order's status and update the stepper + pill in place.
  document.querySelectorAll('.order-tracker[data-active="1"]').forEach(function (tracker) {
    var orderId = tracker.dataset.orderId;
    var steps = tracker.dataset.steps.split(',');
    var pill = document.getElementById('status-pill-' + orderId);

    function applyStatus(data) {
      if (data.status === 'cancelled' || data.status === 'done') {
        clearInterval(timer);
      }
      var idx = steps.indexOf(data.status);
      tracker.querySelectorAll('.tracker-step').forEach(function (stepEl, i) {
        stepEl.classList.remove('done', 'current');
        if (idx === -1) return;
        if (i < idx) stepEl.classList.add('done');
        else if (i === idx) stepEl.classList.add('current');
      });
      if (pill) {
        pill.textContent = data.status_display;
        pill.className = 'status-pill ' + data.css;
      }
    }

    function poll() {
      fetch('/api/order-status/' + orderId + '/')
        .then(function (r) { return r.json(); })
        .then(applyStatus)
        .catch(function () {});
    }

    var timer = setInterval(poll, 8000);
  });
});
