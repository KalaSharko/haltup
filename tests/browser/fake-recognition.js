/* Simulation de la reconnaissance vocale et espions réseau / audio / stockage, pour les tests. */
(function () {
  "use strict";
  var spies = { fetch: 0, xhr: 0, beacon: 0, mediaRecorder: 0, getUserMedia: 0, submits: 0 };
  window.__spies = spies;

  // Aucune requête réseau, aucun MediaRecorder, aucun accès direct au micro ne doivent venir de la dictée.
  var realFetch = window.fetch;
  window.fetch = function () { spies.fetch++; return realFetch.apply(this, arguments); };
  var RealXHR = window.XMLHttpRequest;
  window.XMLHttpRequest = function () { spies.xhr++; return new RealXHR(); };
  if (navigator.sendBeacon) navigator.sendBeacon = function () { spies.beacon++; return true; };
  window.MediaRecorder = function () { spies.mediaRecorder++; throw new Error("MediaRecorder ne doit pas être utilisé"); };
  if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = function () { spies.getUserMedia++; return Promise.reject(new Error("interdit")); };

  // Permission du micro contrôlée par les tests (la vraie peut être « denied » dans ce navigateur).
  var perm = { state: "prompt", onchange: null };
  window.__perm = perm;
  try {
    Object.defineProperty(navigator, "permissions", { configurable: true,
      value: { query: function () { return Promise.resolve(perm); } } });
  } catch (e) { /* ignoré */ }

  function makeResults(list) {
    return list.map(function (r) { var res = [{ transcript: r.t, confidence: 0.9 }]; res.isFinal = !!r.final; return res; });
  }

  function FakeRecognition() {
    FakeRecognition.instances.push(this);
    FakeRecognition.last = this;
    this.lang = ""; this.started = false; this.stopped = false; this.aborted = false;
  }
  FakeRecognition.instances = [];
  FakeRecognition.prototype.start = function () { this.started = true; if (FakeRecognition.throwOnStart) throw new Error("start"); };
  FakeRecognition.prototype.stop = function () {
    var self = this; this.stopped = true;
    if (FakeRecognition.finalOnStop) {
      var fin = FakeRecognition.finalOnStop; FakeRecognition.finalOnStop = null;
      setTimeout(function () { self.fireResult(fin); self.fireEnd(); }, 5);
    } else if (!FakeRecognition.silentStop) {
      setTimeout(function () { self.fireEnd(); }, 5);
    }
  };
  FakeRecognition.prototype.abort = function () {
    var self = this; this.aborted = true;
    // Comme un vrai navigateur : erreur « aborted » puis fin, de façon asynchrone.
    setTimeout(function () { self.fireError("aborted"); self.fireEnd(); }, 5);
  };
  FakeRecognition.prototype.fireStart = function () { if (this.onstart) this.onstart({}); };
  FakeRecognition.prototype.fireResult = function (list) { if (this.onresult) this.onresult({ results: makeResults(list), resultIndex: 0 }); };
  FakeRecognition.prototype.fireError = function (code) { if (this.onerror) this.onerror({ error: code }); };
  FakeRecognition.prototype.fireEnd = function () { if (this.onend) this.onend({}); };

  window.FakeRecognition = FakeRecognition;
  window.SpeechRecognition = FakeRecognition;
  window.webkitSpeechRecognition = undefined;

  document.addEventListener("submit", function (ev) { spies.submits++; ev.preventDefault(); }, true);
})();
