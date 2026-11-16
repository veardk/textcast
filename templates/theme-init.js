(function () {
  // A review host (textcast-chat-axi) frames this page in a sandbox without storage and passes
  // the reader's theme as ?textcast_theme=, so the page opens in the same theme every reload.
  var m = /[?&]textcast_theme=(light|dark|sepia)(?:&|$)/.exec(location.search);
  var t = m ? m[1] : null;
  if (!t) { try { t = localStorage.getItem('textcast_theme'); } catch (e) {} }
  if (t !== 'light' && t !== 'dark' && t !== 'sepia') {
    t = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', t);
})();
