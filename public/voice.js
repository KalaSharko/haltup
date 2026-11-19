/* HALTUP — dictée vocale (sans dépendance).
 *
 * Méthode : reconnaissance vocale intégrée au navigateur (Web Speech API :
 * SpeechRecognition ou webkitSpeechRecognition), en français de France (fr-FR).
 *
 * - HALTUP ne capte, ne reçoit, ne téléverse ni ne conserve aucun audio : le navigateur fournit
 *   directement du texte. Aucun MediaRecorder, aucun envoi au serveur HALTUP.
 * - Selon le navigateur, l'audio peut être traité en ligne par le service de son éditeur
 *   (Google pour Chrome, Microsoft pour Edge, Apple pour Safari). Si le navigateur permet de
 *   vérifier qu'une transcription locale du français est disponible, elle est utilisée.
 * - Un clic sur le micro démarre l'écoute, sans étape propre à HALTUP (le navigateur peut
 *   demander l'autorisation du micro). Le texte va dans le champ de message ; il n'est jamais
 *   envoyé automatiquement.
 */
(function () {
  "use strict";

  var cfg = { startTimeoutMs: 15000, maxDurationMs: 60000, stopTimeoutMs: 5000 };
  var ui = null;
  var opts = null;
  var session = null;          // dictée en cours (une seule à la fois)
  var nextId = 1;
  var micPermission = "unknown";   // mis à jour sans bloquer le clic (Permissions API, si disponible)
  var localFr = false;             // transcription locale du français vérifiée par le navigateur
  var frUnavailable = false;       // français déclaré indisponible par le navigateur

  var MESSAGES = {
    "unsupported": "La dictée vocale n'est pas prise en charge par ce navigateur. Écrivez votre message au clavier.",
    "not-allowed": "Le microphone est refusé ou bloqué pour ce site. Autorisez-le dans les réglages du navigateur, ou écrivez au clavier.",
    "service-not-allowed": "La reconnaissance vocale est désactivée ou refusée par le navigateur ou le système (sur Safari, la dictée ou Siri doit être activée). Écrivez au clavier.",
    "audio-capture": "Aucun microphone accessible : il est absent, utilisé par une autre application ou bloqué par le système. Écrivez au clavier.",
    "network": "Le service de reconnaissance vocale est injoignable (une connexion est en général nécessaire). Réessayez ou écrivez au clavier.",
    "offline": "Vous semblez hors ligne : la reconnaissance vocale de ce navigateur a besoin d'une connexion. Écrivez au clavier.",
    "language-not-supported": "Le français n'est pas disponible pour la reconnaissance vocale de ce navigateur. Écrivez au clavier.",
    "no-speech": "La dictée n'a pas compris la phrase. Réessayez en parlant près du micro, ou écrivez au clavier.",
    "unexpected": "La dictée s'est arrêtée de façon inattendue. Réessayez ou écrivez au clavier."
  };
  var RETRYABLE = { "network": true, "no-speech": true, "unexpected": true };

  function Recognition() { return window.SpeechRecognition || window.webkitSpeechRecognition || null; }

  /* ---------------- Texte : fusion des résultats et ajout au champ ---------------- */
  function norm(t) { return String(t || "").replace(/\s+/g, " ").trim(); }

  // Fusionne des segments sans doublon : certains navigateurs (Chrome sur Android, par exemple)
  // renvoient des résultats cumulatifs (« je fais », puis « je fais du foot »).
  function mergeSegments(segments) {
    var out = "";
    segments.forEach(function (raw) {
      var seg = norm(raw);
      if (!seg) return;
      var o = out.toLowerCase(), sl = seg.toLowerCase();
      if (!out) out = seg;
      else if (sl.indexOf(o) === 0) out = seg;                       // nouveau résultat qui contient l'ancien
      else if (o === sl || o.slice(-(sl.length + 1)) === " " + sl) { /* même segment répété à la fin : ignoré */ }
      else out = out + " " + seg;
    });
    return out;
  }

  function capitalize(t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; }

  // Ajoute la dictée au texte existant, sans jamais le remplacer.
  function joinText(existing, dictated) {
    dictated = norm(dictated);
    if (!dictated) return existing;
    if (!existing || !existing.trim()) return capitalize(dictated);
    if (/\n\s*$/.test(existing)) return existing.replace(/[ \t]+$/, "") + capitalize(dictated);
    var base = existing.replace(/\s+$/, "");
    return base + " " + (/[.!?…]$/.test(base) ? capitalize(dictated) : dictated);
  }

  /* ---------------- Interface ---------------- */
  function button(label, cls, onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }

  function announce(text) { ui.live.textContent = ""; window.setTimeout(function () { ui.live.textContent = text; }, 30); }

  function setMic(mode) {
    // mode : "idle", "starting" ou "listening" — l'icône, le nom accessible et l'action changent ensemble.
    var active = mode !== "idle";
    ui.mic.classList.toggle("is-recording", mode === "listening");
    ui.mic.classList.toggle("is-starting", mode === "starting");
    ui.mic.setAttribute("aria-pressed", active ? "true" : "false");
    var name = mode === "listening" ? "Arrêter l'écoute et insérer le texte"
             : mode === "starting" ? "Annuler le démarrage de la dictée"
             : "Dicter un message vocal en français";
    ui.mic.setAttribute("aria-label", name);
    ui.mic.title = name;
  }

  function panel(state, title, status, actions) {
    ui.panel.hidden = false;
    ui.panel.className = "voice voice--" + state;
    ui.title.textContent = title;
    ui.status.textContent = status;
    ui.actions.textContent = "";
    (actions || []).forEach(function (a) { ui.actions.appendChild(a); });
    ui.mic.setAttribute("aria-expanded", "true");
  }

  function hidePanel(focusMic) {
    ui.panel.hidden = true;
    ui.preview.hidden = true;
    ui.previewFinal.textContent = "";
    ui.previewInterim.textContent = "";
    ui.mic.setAttribute("aria-expanded", "false");
    setMic("idle");
    if (focusMic) ui.mic.focus();
  }

  function showError(code) {
    var msg = MESSAGES[code] || MESSAGES.unexpected;
    var actions = [];
    if (RETRYABLE[code]) actions.push(button("Réessayer", "btn btn--primary voice__primary", function () { start(); }));
    actions.push(button("Fermer", "mini-btn" + (actions.length ? " mini-btn--quiet" : ""), function () { hidePanel(true); }));
    setMic("idle");
    panel("error", "Dictée impossible", msg, actions);
    announce("Dictée impossible. " + msg);
    actions[0].focus();
  }

  function updatePreview() {
    if (!session) return;
    ui.preview.hidden = false;
    ui.previewFinal.textContent = session.finalText;
    ui.previewInterim.textContent = (session.finalText && session.interimText ? " " : "") + session.interimText;
    ui.preview.classList.toggle("is-empty", !session.finalText && !session.interimText);
  }

  /* ---------------- Cycle de la dictée ---------------- */
  function start() {
    if (session) return;
    var R = Recognition();
    if (!R) { showError("unsupported"); return; }
    // Capacités vérifiables avant d'écouter : pas de faux mode « écoute ».
    if (micPermission === "denied") { showError("not-allowed"); return; }
    if (frUnavailable) { showError("language-not-supported"); return; }
    if (navigator.onLine === false && !localFr) { showError("offline"); return; }

    var rec;
    try { rec = new R(); } catch (e) { showError("unsupported"); return; }
    var id = nextId++;
    session = { id: id, rec: rec, finalText: "", interimText: "", error: null, cancelled: false,
                started: false, stopping: false, settled: false, timers: [] };
    rec.lang = "fr-FR";
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    if (localFr) { try { rec.processLocally = true; } catch (e) { /* propriété non prise en charge */ } }

    var current = function () { return session && session.id === id ? session : null; };
    var onStarted = function () {
      var s = current();
      if (!s || s.started || s.cancelled) return;
      s.started = true;
      setMic("listening");
      panel("listening", "Écoute en cours",
        "Parlez en français. « Arrêter » (ou le micro) insère le texte dans le champ ; « Annuler » l'abandonne." +
        (localFr ? " Transcription locale sur cet appareil." : ""),
        [button("Arrêter", "btn btn--primary voice__primary", stop),
         button("Annuler", "mini-btn mini-btn--quiet", cancel)]);
      updatePreview();
      announce("Écoute en cours. Parlez, puis appuyez sur Arrêter.");
      ui.actions.firstChild.focus();
    };
    rec.onstart = onStarted;
    rec.onaudiostart = onStarted;
    rec.onresult = function (ev) {
      var s = current();
      if (!s || s.cancelled) return;
      if (!s.started) onStarted();
      // La liste ev.results contient tous les résultats de la dictée : on la relit entièrement,
      // ce qui évite d'ajouter deux fois un même résultat.
      var finals = [], interims = [];
      for (var i = 0; i < ev.results.length; i++) {
        var r = ev.results[i], alt = r && r[0];
        if (!alt) continue;
        (r.isFinal ? finals : interims).push(alt.transcript);
      }
      s.finalText = mergeSegments(finals);
      s.interimText = mergeSegments(interims);
      updatePreview();
    };
    rec.onerror = function (ev) {
      var s = current();
      if (s && !s.cancelled) s.error = (ev && ev.error) || "unexpected";
    };
    rec.onend = function () { finish(id); };

    setMic("starting");
    panel("starting", "Démarrage de l'écoute…", "", [button("Annuler", "mini-btn mini-btn--quiet", cancel)]);
    try {
      rec.start();
    } catch (e) {
      session.error = "unexpected";
      finish(id);
      return;
    }
    session.timers.push(window.setTimeout(function () {
      var s = current();
      if (s && !s.started) { s.error = "unexpected"; abortRec(s); finish(id); }
    }, cfg.startTimeoutMs));
    session.timers.push(window.setTimeout(function () { if (current()) stop(); }, cfg.maxDurationMs));
  }

  function abortRec(s) {
    try { s.rec.abort(); } catch (e) { /* déjà arrêté */ }
  }

  function stop() {
    var s = session;
    if (!s) return;
    if (!s.started) { cancel(); return; }       // rien n'a encore été capté
    if (s.stopping) return;
    s.stopping = true;
    ui.status.textContent = "Transcription en cours…";
    ui.actions.textContent = "";
    try { s.rec.stop(); } catch (e) { finish(s.id); return; }
    var id = s.id;
    // Certains navigateurs n'envoient pas toujours l'événement de fin : on termine quand même.
    s.timers.push(window.setTimeout(function () { finish(id); }, cfg.stopTimeoutMs));
  }

  function cancel() {
    var s = session;
    if (!s) return;
    s.cancelled = true;
    abortRec(s);
    finish(s.id);  // immédiat : les événements tardifs de cette dictée seront ignorés
  }

  function finish(id) {
    var s = session;
    if (!s || s.id !== id || s.settled) return;   // une seule conclusion par dictée
    s.settled = true;
    s.timers.forEach(function (t) { window.clearTimeout(t); });
    var rec = s.rec;
    rec.onstart = rec.onaudiostart = rec.onresult = rec.onerror = rec.onend = null;
    var text = s.cancelled ? "" : mergeSegments([s.finalText, s.interimText]);
    var error = s.error, cancelled = s.cancelled;
    session = null;  // rien n'est conservé après la dictée

    if (cancelled) {
      hidePanel(true);
      announce("Dictée annulée. Votre texte n'a pas été modifié.");
      return;
    }
    if (text) {
      var ta = opts.textarea;
      var max = Number(ta.maxLength) > 0 ? Number(ta.maxLength) : 1000;
      var joined = joinText(ta.value, text);
      var truncated = joined.length > max;
      ta.value = joined.slice(0, max);
      ta.dispatchEvent(new Event("input", { bubbles: true }));
      hidePanel(false);
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
      var note = "Texte dicté ajouté au champ de message : relisez-le, corrigez-le si besoin, puis appuyez sur « Envoyer »." +
        (truncated ? " Le texte a été coupé à " + max + " caractères." : "") +
        (error && error !== "no-speech" ? " La dictée s'est interrompue avant la fin." : "");
      opts.announce(note);
      announce(note);
      return;
    }
    if (error === "aborted") error = "unexpected";
    if (!error) error = "no-speech";
    if (!MESSAGES[error]) error = "unexpected";
    showError(error);
  }

  /* ---------------- Capacités vérifiées sans bloquer le clic ---------------- */
  function watchCapabilities() {
    try {
      if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: "microphone" }).then(function (st) {
          micPermission = st.state;
          st.onchange = function () { micPermission = st.state; };
        }).catch(function () { /* non pris en charge : on le saura au démarrage */ });
      }
    } catch (e) { /* ignoré */ }
    var R = Recognition();
    if (R && typeof R.available === "function") {
      // API récente (Chrome) : vérifie la disponibilité du français, en local puis en ligne.
      try {
        R.available({ langs: ["fr-FR"], processLocally: true }).then(function (st) { localFr = st === "available"; }).catch(function () {});
        R.available({ langs: ["fr-FR"], processLocally: false }).then(function (st) {
          frUnavailable = st === "unavailable" && !localFr;
        }).catch(function () {});
      } catch (e) { /* ignoré */ }
    }
  }

  window.HaltupVoice = {
    supported: function () { return !!Recognition(); },
    init: function (options) {
      opts = options;
      if (options.config) Object.keys(options.config).forEach(function (k) { cfg[k] = options.config[k]; });
      ui = {
        panel: document.getElementById("voice-panel"),
        title: document.getElementById("voice-title"),
        status: document.getElementById("voice-status"),
        preview: document.getElementById("voice-transcript"),
        previewFinal: document.getElementById("voice-final"),
        previewInterim: document.getElementById("voice-interim"),
        actions: document.getElementById("voice-actions"),
        live: document.getElementById("voice-live"),
        mic: document.getElementById("mic-btn")
      };
      setMic("idle");
      ui.mic.addEventListener("click", function () {
        if (!session) start();
        else if (session.started) stop();
        else cancel();
      });
      ui.panel.addEventListener("keydown", function (ev) {
        if (ev.key !== "Escape") return;
        ev.preventDefault();
        if (session) cancel(); else hidePanel(true);
      });
      watchCapabilities();
    },
    // Utilisé par « Recommencer » : coupe une dictée éventuelle sans rien ajouter ni annoncer.
    reset: function () {
      if (session) {
        var s = session;
        s.cancelled = true; s.settled = true;
        s.timers.forEach(function (t) { window.clearTimeout(t); });
        s.rec.onstart = s.rec.onaudiostart = s.rec.onresult = s.rec.onerror = s.rec.onend = null;
        abortRec(s);
        session = null;
      }
      if (ui) hidePanel(false);
    },
    // Exposé pour les tests ciblés.
    _utils: { mergeSegments: mergeSegments, joinText: joinText }
  };
})();
