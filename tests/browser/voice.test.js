/* Tests ciblés de la dictée vocale HALTUP (exécutés dans le navigateur, reconnaissance simulée).
 * Ouvrir http://127.0.0.1:8000/__tests__/voice.html : le titre de l'onglet indique le résultat. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms || 20); }); };
  var F = window.FakeRecognition;
  var announced = [];
  var storageBefore = JSON.stringify([localStorage.length, sessionStorage.length]);

  HaltupVoice.init({ textarea: $("msg"), announce: function (t) { announced.push(t); },
                     config: { startTimeoutMs: 120, stopTimeoutMs: 120, maxDurationMs: 60000 } });

  var results = [], failures = 0;
  function check(cond, label) { if (!cond) { failures++; results.push("  ✗ " + label); } else results.push("  ✓ " + label); }
  function eq(a, b, label) { check(a === b, label + (a === b ? "" : " — obtenu « " + a + " », attendu « " + b + " »")); }
  function btn(label) { return Array.prototype.find.call(document.querySelectorAll("#voice-actions button"), function (b) { return b.textContent === label; }); }
  function mic() { return $("mic-btn"); }
  function title() { return $("voice-title").textContent; }
  function reset(text) { HaltupVoice.reset(); $("msg").value = text || ""; window.SpeechRecognition = F; window.__perm.state = "prompt"; if (window.__perm.onchange) window.__perm.onchange(); F.finalOnStop = null; F.silentStop = false; F.throwOnStart = false; }

  var tests = [
    ["Démarrage au clic, sans faux mode écoute, puis passage visible en écoute", async function () {
      reset();
      mic().click();
      var r = F.last;
      check(r.started, "la reconnaissance démarre dès le clic");
      eq(r.lang, "fr-FR", "langue fr-FR");
      check(r.interimResults === true, "résultats provisoires demandés");
      check(title() !== "Écoute en cours", "pas d'état « écoute » avant le démarrage réel");
      r.fireStart(); await wait();
      eq(title(), "Écoute en cours", "état « Écoute en cours » affiché");
      check(mic().classList.contains("is-recording"), "bouton micro en mode écoute");
      eq(mic().getAttribute("aria-label"), "Arrêter l'écoute et insérer le texte", "nom accessible indiquant l'arrêt");
      eq(mic().getAttribute("aria-pressed"), "true", "aria-pressed=true");
      check(!!btn("Arrêter") && !!btn("Annuler"), "boutons Arrêter et Annuler visibles");
      await wait(50);
      check(/Écoute en cours/.test($("voice-live").textContent), "état d'écoute annoncé aux technologies d'assistance");
    }],
    ["Aperçu provisoire sans envoi, puis texte final dans le champ", async function () {
      var fetchBefore = window.__spies.fetch;
      r = F.last;
      r.fireResult([{ t: "je fais du", final: false }]); await wait();
      eq($("voice-interim").textContent.trim(), "je fais du", "mots provisoires dans l'aperçu");
      eq($("msg").value, "", "le champ n'est pas modifié pendant l'écoute");
      F.finalOnStop = [{ t: "je fais du foot", final: true }];
      btn("Arrêter").click(); await wait(40);
      eq($("msg").value, "Je fais du foot", "texte final inséré (majuscule initiale)");
      check($("voice-panel").hidden, "panneau refermé");
      eq(mic().getAttribute("aria-label"), "Dicter un message vocal en français", "micro de nouveau disponible");
      eq(window.__spies.fetch, fetchBefore, "aucune requête réseau");
      eq(window.__spies.submits, 0, "aucune soumission du message");
    }],
    ["Ajout au texte déjà saisi, sans le remplacer", async function () {
      reset("Bonjour.");
      mic().click(); F.last.fireStart(); F.last.fireResult([{ t: "j'ai 30 minutes", final: true }]);
      mic().click(); await wait(40);  // arrêt par le bouton micro
      eq($("msg").value, "Bonjour. J'ai 30 minutes", "ajout après une phrase terminée");
      reset("je joue au");
      mic().click(); F.last.fireStart(); F.last.fireResult([{ t: "rugby", final: true }]); mic().click(); await wait(40);
      eq($("msg").value, "je joue au rugby", "suite naturelle d'une phrase en cours");
      reset("Ligne 1\n");
      mic().click(); F.last.fireStart(); F.last.fireResult([{ t: "ligne deux", final: true }]); mic().click(); await wait(40);
      eq($("msg").value, "Ligne 1\nLigne deux", "ajout après un retour à la ligne");
    }],
    ["Pas de doublon ni de perte", async function () {
      var m = HaltupVoice._utils.mergeSegments;
      eq(m(["je fais", "je fais du foot"]), "je fais du foot", "résultats cumulatifs fusionnés");
      eq(m(["je fais du foot", "je fais du foot"]), "je fais du foot", "même résultat répété ignoré");
      eq(m(["je vais à la salle", "le"]), "je vais à la salle le", "pas de suppression d'un mot court légitime");
      eq(m(["deux séances", "par semaine"]), "deux séances par semaine", "segments distincts conservés");
      reset();
      mic().click(); var r = F.last; r.fireStart();
      r.fireResult([{ t: "match", final: false }]);
      r.fireResult([{ t: "match demain", final: true }]);
      r.fireResult([{ t: "match demain", final: true }, { t: "à", final: false }]);
      r.fireResult([{ t: "match demain", final: true }, { t: "à 18 heures", final: true }]);
      r.stop(); await wait(40);
      r.fireEnd(); r.fireEnd(); await wait(20);   // événements de fin répétés
      eq($("msg").value, "Match demain à 18 heures", "texte inséré une seule fois, complet");
    }],
    ["Annuler abandonne la dictée et laisse le texte intact", async function () {
      reset("Texte déjà saisi");
      mic().click(); var r = F.last; r.fireStart(); r.fireResult([{ t: "à ignorer", final: true }]);
      btn("Annuler").click(); await wait(40);
      r.fireResult([{ t: "résultat tardif", final: true }]); r.fireEnd(); await wait(20);
      eq($("msg").value, "Texte déjà saisi", "texte existant intact, rien ajouté");
      check($("voice-panel").hidden, "panneau refermé");
      await wait(50);
      check(/annulée/i.test($("voice-live").textContent), "annulation annoncée aux technologies d'assistance");
      // Échap annule aussi
      mic().click(); F.last.fireStart();
      $("voice-panel").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await wait(40);
      eq($("msg").value, "Texte déjà saisi", "Échap annule sans rien ajouter");
      // Nouvelle dictée ensuite
      mic().click(); F.last.fireStart(); F.last.fireResult([{ t: "nouvelle dictée", final: true }]); mic().click(); await wait(40);
      eq($("msg").value, "Texte déjà saisi nouvelle dictée", "nouvelle dictée possible après annulation");
    }],
    ["Clic pendant le démarrage = annulation (rien n'a été capté)", async function () {
      reset();
      mic().click(); mic().click(); await wait(40);
      check(F.last.aborted, "reconnaissance interrompue");
      check($("voice-panel").hidden && $("msg").value === "", "aucun texte, panneau fermé");
    }],
    ["Erreurs : permission, système, service, langue, réseau, silence, arrêt inattendu", async function () {
      var cases = [
        ["not-allowed", /refusé ou bloqué/],
        ["service-not-allowed", /Siri/],
        ["audio-capture", /Aucun microphone/],
        ["network", /injoignable/],
        ["language-not-supported", /français n'est pas disponible/],
        ["no-speech", /n'a pas compris/],
        ["aborted", /inattendue/],
        ["bad-grammar", /inattendue/]
      ];
      for (var i = 0; i < cases.length; i++) {
        reset();
        mic().click(); var r = F.last; if (cases[i][0] !== "not-allowed") r.fireStart();
        r.fireError(cases[i][0]); r.fireEnd(); await wait();
        check(cases[i][1].test($("voice-status").textContent), "« " + cases[i][0] + " » → message adapté");
        eq($("msg").value, "", "« " + cases[i][0] + " » → champ intact");
        eq(mic().getAttribute("aria-pressed"), "false", "« " + cases[i][0] + " » → micro réutilisable");
      }
      reset();
      mic().click(); F.last.fireStart(); F.last.fireEnd(); await wait();
      check(/n'a pas compris/.test($("voice-status").textContent), "fin sans aucun mot → « n'a pas compris »");
      check(!!btn("Réessayer"), "possibilité de réessayer");
    }],
    ["Capacités vérifiées avant d'écouter (pas de faux mode écoute)", async function () {
      reset();
      var n = F.instances.length;
      window.__perm.state = "denied"; if (window.__perm.onchange) window.__perm.onchange();
      mic().click(); await wait();
      eq(F.instances.length, n, "micro déjà refusé → aucune écoute lancée");
      check(/refusé ou bloqué/.test($("voice-status").textContent), "message de refus immédiat");
      reset();
      window.SpeechRecognition = undefined;
      mic().click(); await wait();
      check(/pas prise en charge/.test($("voice-status").textContent), "navigateur incompatible → message clair");
      check(title() !== "Écoute en cours", "pas d'état d'écoute");
      reset();
      var online = Object.getOwnPropertyDescriptor(Navigator.prototype, "onLine");
      Object.defineProperty(navigator, "onLine", { configurable: true, get: function () { return false; } });
      n = F.instances.length; mic().click(); await wait();
      eq(F.instances.length, n, "hors ligne → aucune écoute lancée");
      check(/hors ligne/.test($("voice-status").textContent), "message hors ligne");
      delete navigator.onLine; if (online) Object.defineProperty(Navigator.prototype, "onLine", online);
      reset();
      mic().click(); await wait(200);  // le navigateur ne démarre jamais
      check(/inattendue/.test($("voice-status").textContent), "démarrage qui n'aboutit pas → message, micro libéré");
    }],
    ["Aucun audio enregistré, téléversé ou sauvegardé par HALTUP", async function () {
      eq(window.__spies.mediaRecorder, 0, "MediaRecorder jamais utilisé");
      eq(window.__spies.getUserMedia, 0, "getUserMedia jamais appelé directement");
      eq(window.__spies.xhr + window.__spies.beacon, 0, "aucun XMLHttpRequest ni sendBeacon");
      eq(JSON.stringify([localStorage.length, sessionStorage.length]), storageBefore, "rien d'enregistré dans le navigateur");
      eq(window.__spies.submits, 0, "aucune soumission automatique sur l'ensemble des tests");
    }]
  ];

  var r;
  (async function run() {
    for (var i = 0; i < tests.length; i++) {
      results.push(tests[i][0]);
      try { await tests[i][1](); } catch (e) { failures++; results.push("  ✗ exception : " + e.message); }
    }
    HaltupVoice.reset();
    var total = results.filter(function (l) { return /^  [✓✗]/.test(l); }).length;
    $("results").textContent = results.join("\n");
    $("summary").textContent = failures ? "ÉCHEC : " + failures + " vérification(s) sur " + total : "OK : " + total + " vérifications";
    document.title = (failures ? "ÉCHEC " : "OK ") + (total - failures) + "/" + total;
  })();
})();
