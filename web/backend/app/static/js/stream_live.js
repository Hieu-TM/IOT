// Real MJPEG live view — replaces the old pure-frontend canvas demo.
//
// The board already runs a second http server on server_port+1 (default 81;
// see firmware/aqua_scope_station/app_httpd.cpp) serving
// `multipart/x-mixed-replace` at /stream. A plain <img src="..."> decodes
// that natively in every browser, so no JS decoding loop or backend proxy is
// needed — the browser fetches it directly from the board over the LAN.
(function () {
  var stage = document.getElementById('stream-stage');
  if (!stage) return;

  var img = document.getElementById('stream-img');
  var emptyState = document.getElementById('stream-empty');
  var errorState = document.getElementById('stream-error');
  var errorMsg = document.getElementById('stream-error-msg');
  var toolbar = document.getElementById('stream-toolbar');
  var hostLabel = document.getElementById('stream-host-label');
  var retryBtn = document.getElementById('stream-retry');

  var STREAM_PORT = 81; // firmware always starts the stream server at server_port + 1
  var currentHost = null;

  function showOnly(el) {
    [img, emptyState, errorState].forEach(function (e) {
      e.hidden = e !== el;
    });
  }

  function streamUrlFor(host) {
    // station_host may carry an explicit ":port" for the main API (settings_store's
    // HOST_RE allows it) — the MJPEG server is always at the fixed +1 offset above
    // whatever port the board's main server actually used, not this one, so strip it.
    var bare = host.replace(/:\d+$/, '');
    return 'http://' + bare + ':' + STREAM_PORT + '/stream';
  }

  function connect(host) {
    currentHost = host;
    toolbar.hidden = false;
    hostLabel.textContent = 'live · ' + host + ':' + STREAM_PORT;
    // Cache-bust so a retry after an error always issues a fresh request
    // instead of the browser re-showing the same broken image.
    img.src = streamUrlFor(host) + '?t=' + Date.now();
    showOnly(img);
  }

  img.addEventListener('error', function () {
    if (!currentHost) return;
    errorMsg.textContent =
      'Không kết nối được tới board tại ' + currentHost + ':' + STREAM_PORT +
      ' — kiểm tra board còn bật và cùng mạng LAN.';
    showOnly(errorState);
  });

  retryBtn.addEventListener('click', function () {
    if (currentHost) connect(currentHost);
  });

  fetch('/api/settings')
    .then(function (r) { return r.json(); })
    .then(function (s) {
      var host = (s.station_host || '').trim();
      if (!host) {
        showOnly(emptyState);
        return;
      }
      connect(host);
    })
    .catch(function () {
      errorMsg.textContent = 'Không đọc được cấu hình từ server.';
      showOnly(errorState);
    });
})();
