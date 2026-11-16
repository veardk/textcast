// Template preview only — generated pages never include this file.
// When a template in templates/ is opened directly, swap {{name|sample}} for its sample text
// (and a bare {{name}} for nothing) so the layout shows realistic content.
(function () {
  var SLOT = /\{\{\w+(?:\|([\s\S]*?))?\}\}/g;
  // a sample containing markup (e.g. <strong>) is split across nodes: drop the stray "{{name|" and "}}" halves too
  var fill = function (s) {
    return s.replace(SLOT, function (_, sample) { return sample || ''; }).replace(/\{\{\w+\|/g, '').replace(/\}\}/g, '');
  };
  var walk = function (el) {
    for (var i = 0; i < el.attributes.length; i++) {
      var a = el.attributes[i];
      if (a.value.indexOf('{{') !== -1) el.setAttribute(a.name, fill(a.value));
    }
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3 && /\{\{|\}\}/.test(n.nodeValue)) n.nodeValue = fill(n.nodeValue);
      else if (n.nodeType === 1 && n.tagName !== 'SCRIPT' && n.tagName !== 'STYLE') walk(n);
    }
  };
  // alternate branches of @if / @if ! pairs would show twice; templates mark the extra one
  Array.prototype.forEach.call(document.querySelectorAll('[data-preview="hide"]'), function (e) { e.remove(); });
  walk(document.documentElement);
  document.title = fill(document.title);
})();
