/* HALTUP — interface (JavaScript sans framework).
 * Les listes (sports, objectifs, matériel…) viennent du serveur (/api/config) : rien n'est dupliqué ici.
 * La conversation est conservée en mémoire, dans cet onglet uniquement.
 */
(function () {
  "use strict";

  var LEGACY_STORAGE_KEY = "altup.profil.v1";
  var config = null;
  var state = null;
  var busy = false;
  var lastRequest = null;

  var $ = function (id) { return document.getElementById(id); };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "text") node.textContent = attrs[k];
        else if (k === "class") node.className = attrs[k];
        else if (k.indexOf("on") === 0) node.addEventListener(k.slice(2), attrs[k]);
        else node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  /* ---------------- Ancienne mémorisation locale (retirée) ----------------
   * Les versions précédentes pouvaient enregistrer le profil dans le navigateur.
   * Cette option n'existe plus : on supprime l'éventuelle trace laissée par une visite antérieure. */
  function removeLegacyStorage() {
    try { window.localStorage.removeItem(LEGACY_STORAGE_KEY); } catch (e) { /* stockage indisponible : rien à faire */ }
  }

  /* ---------------- Appels serveur ---------------- */
  function api(path, body) {
    return fetch(path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || "Le serveur a répondu avec une erreur (" + res.status + ").");
        return data;
      });
    });
  }

  /* ---------------- Formulaire de profil ---------------- */
  function optionChip(type, name, item, cls) {
    return el("label", { class: cls || "chip" }, [
      el("input", { type: type, name: name, value: item.id }),
      el("span", { text: item.label })
    ]);
  }

  function buildForm() {
    var sport = $("f-sport");
    sport.appendChild(el("option", { value: "", text: "Choisir un sport…" }));
    config.sports.forEach(function (s) { sport.appendChild(el("option", { value: s.id, text: s.label })); });
    config.athleticsFocus.forEach(function (a) { $("f-athletics").appendChild(optionChip("radio", "athletics_focus", a, "seg__opt")); });
    config.goals.forEach(function (g) { $("f-goal").appendChild(optionChip("radio", "goal", g)); });
    config.levels.forEach(function (lv) { $("f-level").appendChild(optionChip("radio", "level", lv, "seg__opt")); });
    config.places.forEach(function (p) { $("f-place").appendChild(optionChip("radio", "place", p, "seg__opt")); });
    config.equipment.forEach(function (e) { $("f-equipment").appendChild(optionChip("checkbox", "equipment", e)); });
    var dur = $("f-duration");
    dur.appendChild(el("option", { value: "", text: "Choisir…" }));
    config.durations.forEach(function (d) { dur.appendChild(el("option", { value: String(d), text: d + " minutes" })); });

    config.painZones.forEach(function (z) { $("f-pain-zones").appendChild(optionChip("checkbox", "pain_zones", z)); });
    document.querySelectorAll('input[name="pain"]').forEach(function (r) { r.addEventListener("change", syncPainFields); });
    // « Je ne sais pas » est exclusif ; deux zones au maximum.
    $("f-pain-zones").addEventListener("change", function (ev) {
      if (!ev.target.checked) return;
      var boxes = Array.prototype.slice.call(document.querySelectorAll('input[name="pain_zones"]'));
      boxes.forEach(function (b) {
        if (ev.target.value === "inconnu" && b.value !== "inconnu") b.checked = false;
        if (ev.target.value !== "inconnu" && b.value === "inconnu") b.checked = false;
      });
      var checked = boxes.filter(function (b) { return b.checked && b.value !== "inconnu"; });
      if (checked.length > config.maxPainZones) {
        ev.target.checked = false;
        showFormErrors(["Deux zones au maximum. Si plusieurs zones sont concernées, choisissez « Je ne sais pas / je préfère ne pas préciser » : HALTUP ne proposera pas de séance et vous recommandera un avis professionnel."]);
      }
    });
    // Toute modification manuelle du formulaire détache le scénario chargé.
    $("profile-form").addEventListener("input", function (ev) {
      if (ev.isTrusted && ev.target.id !== "f-adult") clearScenario();
    });
    // Réponses explicites « aucun » : exclusives des autres réponses de la même rubrique.
    $("f-other-eq-none").addEventListener("change", function (ev) { if (ev.target.checked) $("f-other-eq").value = ""; });
    $("f-other-eq").addEventListener("input", function (ev) { if (ev.target.value.trim()) $("f-other-eq-none").checked = false; });
    $("f-fatigue-none").addEventListener("change", function (ev) {
      if (ev.target.checked) { $("f-fatigue-recent").checked = false; $("f-fatigue-next").checked = false; }
    });
    ["f-fatigue-recent", "f-fatigue-next"].forEach(function (id) {
      $(id).addEventListener("change", function (ev) { if (ev.target.checked) $("f-fatigue-none").checked = false; });
    });
    // La progression est recalculée à chaque modification (après les exclusivités ci-dessus).
    $("profile-form").addEventListener("input", updateProgress);
    $("profile-form").addEventListener("change", updateProgress);
    sport.addEventListener("change", syncSportFields);
    // « Aucun matériel » est exclusif.
    $("f-equipment").addEventListener("change", function (ev) {
      if (ev.target.name !== "equipment" || !ev.target.checked) return;
      var boxes = document.querySelectorAll('input[name="equipment"]');
      boxes.forEach(function (b) {
        if (ev.target.value === "aucun" && b.value !== "aucun") b.checked = false;
        if (ev.target.value !== "aucun" && b.value === "aucun") b.checked = false;
      });
    });
    $("profile-form").addEventListener("submit", onGenerate);
  }

  function syncSportFields() {
    var v = $("f-sport").value;
    $("field-athletics").hidden = v !== "athletisme";
    $("field-other-sport").hidden = v !== "autre";
  }

  function syncPainFields() {
    var yes = checkedValue("pain") === "oui";
    $("field-pain-zones").hidden = !yes;
    if (!yes) document.querySelectorAll('input[name="pain_zones"]').forEach(function (b) { b.checked = false; });
  }

  function checkedValue(name) {
    var c = document.querySelector('input[name="' + name + '"]:checked');
    return c ? c.value : null;
  }

  function setRadio(name, value) {
    document.querySelectorAll('input[name="' + name + '"]').forEach(function (r) { r.checked = r.value === value; });
  }

  function readForm() {
    var pain = checkedValue("pain");
    return {
      sport: $("f-sport").value || null,
      athletics_focus: checkedValue("athletics_focus"),
      other_sport: $("f-other-sport").value,
      goal: checkedValue("goal"),
      level: checkedValue("level"),
      duration: $("f-duration").value ? Number($("f-duration").value) : null,
      place: checkedValue("place"),
      equipment: Array.prototype.map.call(document.querySelectorAll('input[name="equipment"]:checked'), function (b) { return b.value; }),
      other_equipment: $("f-other-eq").value,
      other_equipment_none: $("f-other-eq-none").checked,
      fatigue_recent: $("f-fatigue-recent").checked,
      fatigue_next: $("f-fatigue-next").checked,
      fatigue_none: $("f-fatigue-none").checked,
      pain: pain === "oui" ? true : pain === "non" ? false : null,
      pain_zones: Array.prototype.map.call(document.querySelectorAll('input[name="pain_zones"]:checked'), function (b) { return b.value; }),
      adult: $("f-adult").checked ? true : null
    };
  }

  function fillForm(p) {
    if (!p) return;
    $("f-sport").value = p.sport || "";
    syncSportFields();
    setRadio("athletics_focus", p.athletics_focus);
    $("f-other-sport").value = p.other_sport || "";
    setRadio("goal", p.goal);
    setRadio("level", p.level);
    var dur = $("f-duration");
    if (p.duration && !dur.querySelector('option[value="' + p.duration + '"]')) {
      dur.appendChild(el("option", { value: String(p.duration), text: p.duration + " minutes" }));
    }
    dur.value = p.duration ? String(p.duration) : "";
    setRadio("place", p.place);
    document.querySelectorAll('input[name="equipment"]').forEach(function (b) { b.checked = (p.equipment || []).indexOf(b.value) >= 0; });
    $("f-other-eq").value = p.other_equipment || "";
    $("f-other-eq-none").checked = p.other_equipment_none === true;
    if (typeof p.fatigue_recent === "boolean") $("f-fatigue-recent").checked = p.fatigue_recent;
    if (typeof p.fatigue_next === "boolean") $("f-fatigue-next").checked = p.fatigue_next;
    $("f-fatigue-none").checked = p.fatigue_none === true && !p.fatigue_recent && !p.fatigue_next;
    setRadio("pain", p.pain === true ? "oui" : p.pain === false ? "non" : null);
    $("field-pain-zones").hidden = p.pain !== true;
    document.querySelectorAll('input[name="pain_zones"]').forEach(function (b) { b.checked = (p.pain_zones || []).indexOf(b.value) >= 0; });
    $("f-adult").checked = p.adult === true;
    updateProgress();
  }

  function showFormErrors(errors) {
    var box = $("form-errors");
    box.textContent = "";
    if (!errors || !errors.length) { box.hidden = true; return; }
    box.appendChild(el("strong", { text: "Pour générer la séance, corrigez ces points :" }));
    var ul = el("ul");
    errors.forEach(function (e) { ul.appendChild(el("li", { text: e })); });
    box.appendChild(ul);
    box.hidden = false;
    box.setAttribute("tabindex", "-1");
    box.focus({ preventScroll: true });
  }

  /* ---------------- Progression du profil (10 rubriques) ---------------- */
  function anyChecked(name) { return !!document.querySelector('input[name="' + name + '"]:checked'); }

  // Une rubrique compte une seule fois, quel que soit le nombre d'options cochées.
  function rubrics() {
    var pain = checkedValue("pain");
    var zones = Array.prototype.filter.call(document.querySelectorAll('input[name="pain_zones"]:checked'), function () { return true; });
    return [
      { done: !!$("f-sport").value, hint: "Sport : choisissez un sport (ou « Autre sport »)." },
      { done: anyChecked("goal"), hint: "Objectif principal : choisissez un objectif." },
      { done: anyChecked("level"), hint: "Niveau : indiquez votre niveau." },
      { done: !!$("f-duration").value, hint: "Durée disponible : choisissez une durée." },
      { done: anyChecked("place"), hint: "Lieu : indiquez où vous vous entraînez." },
      { done: anyChecked("equipment"), hint: "Matériel réellement disponible : cochez au moins une option (ou « Aucun matériel »)." },
      { done: !!$("f-other-eq").value.trim() || $("f-other-eq-none").checked, hint: "Autre matériel : précisez-le ou cochez « Aucun autre matériel »." },
      { done: $("f-fatigue-none").checked || $("f-fatigue-recent").checked || $("f-fatigue-next").checked, hint: "Charge sportive : cochez une situation ou « Aucun entraînement ni match à signaler »." },
      { done: pain === "non" || (pain === "oui" && zones.length > 0), hint: "Douleur, blessure ou restriction : répondez Non ou Oui (et, si Oui, choisissez la zone)." },
      { done: $("f-adult").checked, hint: "Confirmez avoir 18 ans ou plus." }
    ];
  }

  function updateProgress() {
    if (!config) return;
    var list = rubrics();
    var done = list.filter(function (r) { return r.done; }).length;
    var text = "Profil complété : " + done + " sur " + list.length;
    $("progress-bar").style.width = (done / list.length * 100) + "%";
    var bar = $("profile-progress");
    bar.setAttribute("aria-valuenow", String(done));
    bar.setAttribute("aria-valuetext", text);
    bar.classList.toggle("is-complete", done === list.length);
    $("progress-label").textContent = text;
  }

  function onGenerate(ev) {
    ev.preventDefault();
    if (busy) return;
    var profile = readForm();
    showFormErrors(null);
    var missing = rubrics().filter(function (r) { return !r.done; });
    if (missing.length) {
      showFormErrors(missing.map(function (r) { return r.hint; }));
      $("form-errors").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    pendingScenario = activeScenario;
    send("/api/generate", { profile: profile, state: state }, true);
  }

  /* ---------------- Fil de conversation ---------------- */
  function scrollToBottom(node) {
    (node || $("thread").lastElementChild).scrollIntoView({ behavior: "smooth", block: node ? "start" : "end" });
  }

  function addMessage(who, text) {
    var node = el("div", { class: "msg msg--" + who, text: text });
    $("thread").appendChild(node);
    scrollToBottom();
    return node;
  }

  function addNotice(text) {
    $("thread").appendChild(el("div", { class: "msg msg--notice", role: "note", text: text }));
  }

  function addError(text) {
    var node = el("div", { class: "msg msg--error", role: "alert" }, [
      el("div", { text: text }),
      el("button", { type: "button", class: "btn btn--ghost", text: "Réessayer", onclick: function () {
        node.remove();
        if (lastRequest) send(lastRequest.path, lastRequest.body, lastRequest.fromForm);
      } })
    ]);
    $("thread").appendChild(node);
    scrollToBottom();
  }

  function renderQuick(replies) {
    var box = $("quick");
    box.textContent = "";
    (replies || []).forEach(function (q) {
      box.appendChild(el("button", { type: "button", text: q.label, onclick: function () { sendMessage(q.message); } }));
    });
  }

  function setBusy(on) {
    busy = on;
    $("send-btn").disabled = on;
    $("generate-btn").disabled = on;
    $("generate-btn").textContent = on ? "Génération en cours…" : "Générer ma séance";
    var typing = document.querySelector(".msg--typing");
    if (on && !typing) {
      $("thread").appendChild($("tpl-typing").content.cloneNode(true));
      scrollToBottom();
    } else if (!on && typing) {
      typing.remove();
    }
  }

  function send(path, body, fromForm) {
    lastRequest = { path: path, body: body, fromForm: fromForm };
    setBusy(true);
    renderQuick([]);
    return api(path, body).then(function (data) {
      setBusy(false);
      if (data.mode) renderMode(data.mode);
      if (data.errors) {
        pendingScenario = null;  // pas d'explication de scénario sur une séance future sans rapport
        showFormErrors(data.errors);
        $("form-errors").scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      if (fromForm) addMessage("user", activeScenario ? "Scénario « " + activeScenario.title + " » lancé depuis le formulaire." : "Profil envoyé depuis le formulaire.");
      state = data.state;
      fillForm(state.profile);
      if (data.notice) addNotice(data.notice);
      var sessionNode = null;
      (data.messages || []).forEach(function (m) {
        if (m.kind === "text") addMessage("bot", m.text);
        else if (m.kind === "session") sessionNode = renderSession(m.session);
      });
      renderQuick(data.quickReplies);
      // Le serveur n'a plus de séance active (ex. : douleur sans zone) : l'ancienne carte n'est plus valable.
      if (!state.spec) markOutdated("Cette séance n'est plus active.");
      syncSessionUi();
      if (fromForm) clearScenario();  // l'explication du scénario est désormais dans la carte
      if (sessionNode) {
        if (window.matchMedia("(max-width: 900px)").matches) collapseProfile(true);
        scrollToBottom(sessionNode.previousElementSibling || sessionNode);
      }
    }).catch(function (err) {
      setBusy(false);
      addError("Impossible d'obtenir une réponse : " + (err.message || "erreur réseau") + ". Vérifiez que le serveur HALTUP est lancé.");
    });
  }

  function sendMessage(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    addMessage("user", text);
    send("/api/chat", { message: text, state: state }, false);
  }

  /* ---------------- Séance active : effacement et anciennes versions ---------------- */
  function markOutdated(text) {
    document.querySelectorAll("#thread .session:not(.is-outdated)").forEach(function (n) {
      n.classList.add("is-outdated");
      n.classList.remove("is-last");
      n.setAttribute("aria-label", "Séance précédente (inactive)");
      n.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      n.insertBefore(el("p", { class: "session__outdated", text: text }), n.firstChild);
    });
  }

  function syncSessionUi() {
    var active = !!(state && state.spec) && !!document.querySelector("#thread .session.is-last");
    $("clear-session-btn").disabled = !active;
    $("clear-session-hint").hidden = active;
  }

  // Retire la séance de l'interface et de l'état, sans toucher au profil ni à la conversation.
  function clearSession() {
    if (busy) return;
    document.querySelectorAll("#thread .session").forEach(function (n) { n.remove(); });
    state.spec = null;
    state.seed = (state.seed || 1) + 1;  // la prochaine séance propose d'autres exercices
    pendingScenario = null;
    lastRequest = null;
    renderQuick([]);
    showFormErrors(null);
    collapseProfile(false);
    syncSessionUi();
    addNotice("Séance supprimée. Votre profil est conservé : modifiez-le si besoin, puis générez une nouvelle séance ou chargez un scénario.");
    $("profile-form").scrollIntoView({ behavior: "smooth", block: "start" });
    $("generate-btn").focus({ preventScroll: true });
  }

  /* ---------------- Carte de séance ---------------- */
  function section(num, title, minutes, children) {
    return el("section", { class: "block" }, [
      el("h3", { class: "block__title" }, [
        el("span", { class: "block__num", "aria-hidden": "true", text: num }),
        el("span", { class: "block__label", text: title }),
        minutes != null ? el("span", { class: "block__time", text: "≈ " + minutes + " min" }) : null
      ])
    ].concat(children));
  }

  function prose(text, cls) { return el("p", { class: "prose" + (cls ? " " + cls : ""), text: text }); }

  function stepList(items) {
    return el("ol", { class: "steps-list" }, items.map(function (i) {
      return el("li", null, [el("span", { class: "steps-list__name", text: i.name }), el("span", { class: "steps-list__detail", text: i.detail })]);
    }));
  }

  function dose(label, value) {
    return el("div", { class: "dose__item" }, [el("span", { class: "dose__label", text: label }), el("span", { class: "dose__value", text: value })]);
  }

  function exerciseCard(ex, index) {
    var wo = ex.without_equipment;
    var noEquip = !ex.needs_equipment
      ? el("p", { class: "exercise__line" }, [el("strong", { text: "Matériel : " }), "aucun, au poids du corps."])
      : el("p", { class: "exercise__line" }, [
          el("strong", { text: "Matériel : " }), ex.equipment.toLowerCase() + ". ",
          wo && wo.name
            ? el("span", null, ["Sans ce matériel, faites plutôt ", el("em", { text: wo.name }), " : " + lowerFirst(wo.cue)])
            : el("span", { text: wo ? wo.cue : "" })
        ]);
    return el("li", { class: "exercise" }, [
      el("div", { class: "exercise__head" }, [
        el("span", { class: "exercise__index", "aria-hidden": "true", text: String(index + 1) }),
        el("div", null, [
          el("h4", { class: "exercise__name", text: ex.name }),
          el("p", { class: "exercise__orig", text: ex.original_name + " · " + ex.muscles.join(", ") })
        ])
      ]),
      el("div", { class: "dose", role: "group", "aria-label": "Dosage" }, [
        dose("Séries", String(ex.sets)),
        dose(ex.is_timed ? "Durée" : "Répétitions", ex.reps),
        dose("Repos", ex.rest_label)
      ]),
      el("p", { class: "exercise__line" }, [el("strong", { text: "Comment faire : " }), ex.cue]),
      noEquip,
      el("details", { class: "exercise__more" }, [
        el("summary", { text: "Variante plus facile et erreurs à éviter" }),
        el("p", null, [el("strong", { text: ex.easier.name + ". " }), ex.easier.cue]),
        el("p", { text: "À éviter : " + ex.errors.map(lowerFirst).join(" ; ") + "." })
      ]),
      el("div", { class: "exercise__actions" }, [
        el("button", { type: "button", class: "mini-btn", text: "Remplacer", "aria-label": "Remplacer « " + ex.name + " » par une variante",
          onclick: function () { adapt("replace", ex.id, ex.name); } }),
        el("button", { type: "button", class: "mini-btn mini-btn--quiet", text: "Retirer", "aria-label": "Retirer « " + ex.name + " » de la séance",
          onclick: function () { adapt("remove", ex.id, ex.name); } })
      ])
    ]);
  }

  function lowerFirst(t) { return t ? t.charAt(0).toLowerCase() + t.slice(1) : t; }

  function renderSession(s) {
    markOutdated("Version précédente : remplacée par la séance ci-dessous.");
    var su = s.summary;
    var head = el("header", { class: "session__head" }, [
      el("p", { class: "session__kicker", text: "Votre séance" }),
      el("h3", { class: "session__title", text: su.goal }),
      el("div", { class: "session__meta" }, [su.sport, su.level, su.place, su.equipment].map(function (t) { return el("span", { class: "tag", text: t }); })),
      el("p", { class: "session__time" }, [
        "Durée estimée ", el("strong", { text: su.duration_estimated + " min" }), " pour " + su.duration_requested + " min disponibles.",
        su.duration_note ? el("span", { text: " " + su.duration_note }) : null
      ])
    ]);

    var body = el("div", { class: "session__body" });
    if (s.caution) {
      body.appendChild(el("div", { class: "caution", role: "note" }, [
        el("p", { class: "caution__title", text: s.caution.title }),
        el("p", { text: s.caution.text })
      ]));
    }
    var scenario = pendingScenario;
    pendingScenario = null;
    if (scenario) {
      body.appendChild(el("div", { class: "why" }, [
        el("p", { class: "why__title", text: "Pourquoi cette séance correspond au scénario « " + scenario.title + " »" }),
        prose(scenario.why.join(" ")),
        prose(scenario.caveat, "prose--muted")
      ]));
    }
    if (s.changes && s.changes.length) {
      body.appendChild(el("div", { class: "changes", role: "status" }, [
        el("p", { class: "changes__title", text: "Ce qui a changé" }),
        prose(s.changes.join(" "))
      ]));
    }
    body.appendChild(prose(s.intro, "prose--lead"));

    body.appendChild(section("1", "Échauffement", s.warmup.minutes, [
      prose(s.warmup.intro), stepList(s.warmup.items), prose(s.warmup.tip, "prose--muted")
    ]));
    body.appendChild(section("2", "Corps de séance", s.main.minutes, [
      prose(s.main.intro),
      el("p", { class: "effort", text: s.main.effort }),
      el("ol", { class: "exercises" }, s.main.exercises.map(exerciseCard)),
      prose(s.main.timing_rule, "prose--muted")
    ]));
    body.appendChild(section("3", "Retour au calme", s.cooldown.minutes, [
      prose(s.cooldown.intro), stepList(s.cooldown.items)
    ]));
    body.appendChild(el("section", { class: "block block--soft" }, [
      el("h3", { class: "block__title" }, [el("span", { class: "block__label", text: "Pour vous entraîner prudemment" })]),
      prose(s.safety.join(" "))
    ]));

    var meta = [];
    if (s.assumptions.length) {
      meta.push(el("details", { class: "meta-details", open: "" }, [
        el("summary", { text: "Hypothèses retenues" }), prose(s.assumptions.join(" "))
      ]));
    }
    meta.push(el("details", { class: "meta-details" }, [
      el("summary", { text: "Adaptation au sport : " + s.sport_note.name + " (confiance : " + s.sport_note.confidence + ")" }),
      prose(s.sport_note.specifics + " Limite : " + lowerFirst(s.sport_note.limits))
    ]));
    meta.push(el("details", { class: "meta-details" }, [
      el("summary", { text: "Sources et licences" }),
      el("ul", null, s.sources.map(function (src) {
        return el("li", null, [el("strong", { text: src.title }), el("br"), src.detail, el("br"),
          "Licence : " + src.license + " · Rédaction : " + src.date, el("br"), src.status]);
      }))
    ]));
    meta.push(el("p", { class: "origin", text: originText(s.generated_by) }));
    body.appendChild(el("section", { class: "block block--meta" }, meta));

    var requested = su.duration_requested;
    var actions = el("div", { class: "session__actions" }, [
      el("p", { class: "session__actions-label", text: "Adapter la séance" }),
      el("div", { class: "session__actions-row" }, [
        requested > config.minDuration ? el("button", { type: "button", class: "btn btn--ghost", text: "Raccourcir de 10 min",
          onclick: function () { sendMessage("Réduis la séance à " + Math.max(config.minDuration, requested - 10) + " minutes."); } }) : null,
        el("button", { type: "button", class: "btn btn--ghost", text: "Plus facile", onclick: function () { sendMessage("Donne-moi une variante plus facile."); } }),
        el("button", { type: "button", class: "btn btn--ghost", text: "Autres exercices", onclick: function () { sendMessage("Propose-moi d'autres exercices."); } })
      ]),
      el("div", { class: "session__actions-row session__actions-row--secondary" }, [
        el("button", { type: "button", class: "link-btn small", text: "Modifier mes informations", onclick: function () { collapseProfile(false); $("profile-form").scrollIntoView({ behavior: "smooth" }); $("f-sport").focus({ preventScroll: true }); } }),
        el("button", { type: "button", class: "link-btn small", text: "Supprimer la séance", onclick: clearSession }),
        el("button", { type: "button", class: "link-btn small", text: "Imprimer", onclick: function () { window.print(); } }),
        el("button", { type: "button", class: "link-btn small", text: "Recommencer", onclick: restart })
      ])
    ]);
    var card = el("article", { class: "session is-last", "aria-label": "Séance générée" }, [head, body, actions]);
    $("thread").appendChild(card);
    return card;
  }

  function originText(by) {
    if (by === "ai") return "Exercices proposés par le modèle d'IA configuré, puis vérifiés et dosés par les règles d'HALTUP.";
    return "Séance construite par les règles locales d'HALTUP, sans modèle d'IA.";
  }

  function adapt(action, id, name) {
    if (busy) return;
    addMessage("user", (action === "replace" ? "Remplacer « " : "Retirer « ") + name + " ».");
    send("/api/adapt", { action: action, exercise_id: id, state: state }, false);
  }

  /* ---------------- Scénarios de démonstration ---------------- */
  var activeScenario = null;
  var pendingScenario = null;

  function renderScenarios(container, fromHome) {
    config.scenarios.forEach(function (sc) {
      container.appendChild(el("article", { class: "scenario-card" }, [
        el("h3", { class: "scenario-card__title", text: sc.title }),
        el("p", { class: "scenario-card__summary", text: sc.summary }),
        el("button", { type: "button", class: "btn btn--ghost scenario-card__btn", text: "Charger ce scénario",
          onclick: function () { if (fromHome) openWorkspace(); loadScenario(sc); } })
      ]));
    });
  }

  function labelOf(list, id) {
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i].label;
    return id;
  }

  function loadScenario(sc) {
    var adult = $("f-adult").checked;
    var p = Object.assign({}, config.initialState.profile, sc.profile, { adult: adult ? true : null });
    fillForm(p);
    showFormErrors(null);
    activeScenario = sc;
    var eq = sc.profile.equipment.map(function (e) { return labelOf(config.equipment, e); }).join(", ");
    var choices = labelOf(config.sports, sc.profile.sport) + ", " + labelOf(config.goals, sc.profile.goal).toLowerCase() +
      ", niveau " + labelOf(config.levels, sc.profile.level).toLowerCase() + ", " + sc.profile.duration + " minutes, " +
      labelOf(config.places, sc.profile.place).toLowerCase() + ", matériel : " + eq.toLowerCase() +
      (sc.profile.fatigue_next ? ", match ou entraînement dans les prochaines 24–48 h" : "") + ".";
    var box = $("scenario-box");
    box.textContent = "";
    box.appendChild(el("p", { class: "scenario-box__kicker", text: "Scénario chargé" }));
    box.appendChild(el("p", { class: "scenario-box__title", text: sc.title }));
    box.appendChild(prose("Choix retenus : " + choices));
    box.appendChild(prose(sc.why.join(" ")));
    box.appendChild(prose(sc.caveat, "prose--muted"));
    box.appendChild(prose("Hypothèse du scénario : aucune douleur ni blessure. Si ce n'est pas votre cas, modifiez la réponse ci-dessous." +
      (adult ? "" : " Confirmez avoir 18 ans ou plus, puis cliquez sur « Générer ma séance »."), "prose--strong"));
    box.appendChild(el("button", { type: "button", class: "link-btn small", text: "Retirer le scénario", onclick: function () { clearScenario(); } }));
    box.hidden = false;
    collapseProfile(false);
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    (adult ? $("generate-btn") : $("f-adult")).focus({ preventScroll: true });
  }

  function clearScenario() {
    activeScenario = null;
    $("scenario-box").hidden = true;
  }

  /* ---------------- Mode IA / démonstration ---------------- */
  function renderMode(mode) {
    var badge = $("mode-badge");
    badge.textContent = mode.label;
    badge.className = "mode-badge " + (mode.mode === "ai" ? "mode-badge--ai" : "mode-badge--demo");
    badge.title = mode.mode === "ai" ? mode.provider + " · " + mode.model : mode.reason;
    $("privacy-line").textContent = mode.privacy;
    $("about-privacy").textContent = mode.privacy;
  }

  /* ---------------- Navigation ---------------- */
  function collapseProfile(collapsed) {
    var panel = document.querySelector(".profile-panel");
    panel.classList.toggle("is-collapsed", collapsed);
    $("toggle-profile").setAttribute("aria-expanded", String(!collapsed));
    $("toggle-profile").textContent = collapsed ? "Afficher" : "Masquer";
  }

  function openWorkspace() {
    $("home").hidden = true;
    $("workspace").hidden = false;
    if (!$("thread").children.length) addMessage("bot", welcomeText());
    $("msg").focus();
  }

  function goHome(ev) {
    if (ev) ev.preventDefault();
    $("workspace").hidden = true;
    $("home").hidden = false;
    window.scrollTo(0, 0);
  }

  function welcomeText() {
    return "Bonjour, je suis l'assistant HALTUP. Décrivez votre sport, votre objectif, votre niveau, votre matériel et votre temps disponible — en une phrase si vous voulez — ou remplissez le formulaire.\nExemple : « Je joue au foot, je débute, je veux plus d'explosivité, j'ai des haltères et 40 minutes. »";
  }

  function restart() {
    if (window.HaltupVoice) window.HaltupVoice.reset();
    state = JSON.parse(JSON.stringify(config.initialState));
    $("thread").textContent = "";
    renderQuick([]);
    showFormErrors(null);
    clearScenario();
    fillForm(state.profile);
    collapseProfile(false);
    syncSessionUi();
    addMessage("bot", welcomeText());
  }

  function init() {
    removeLegacyStorage();
    api("/api/config").then(function (cfg) {
      config = cfg;
      state = JSON.parse(JSON.stringify(cfg.initialState));
      $("hero-pitch").textContent = cfg.brand.pitch;
      $("home-disclaimer").textContent = cfg.brand.disclaimer;
      renderMode(cfg.mode);
      buildForm();
      renderScenarios($("scenarios-list"), false);
      updateProgress();
    }).catch(function () {
      $("hero-pitch").textContent = "Le serveur HALTUP ne répond pas. Lancez « python3 server.py » puis rechargez la page.";
      $("start-btn").disabled = true;
    });

    $("start-btn").addEventListener("click", openWorkspace);
    $("nav-session").addEventListener("click", openWorkspace);
    $("logo-link").addEventListener("click", goHome);
    $("restart-btn").addEventListener("click", restart);
    $("clear-session-btn").addEventListener("click", clearSession);
    $("toggle-profile").addEventListener("click", function () {
      collapseProfile(!document.querySelector(".profile-panel").classList.contains("is-collapsed"));
    });
    $("composer").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var text = $("msg").value;
      $("msg").value = "";
      autoGrow();
      sendMessage(text);
    });
    // Entrée envoie, Maj+Entrée fait un retour à la ligne.
    $("msg").addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
        ev.preventDefault();
        $("composer").requestSubmit ? $("composer").requestSubmit() : $("send-btn").click();
      }
    });
    function autoGrow() { var t = $("msg"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 160) + "px"; }
    $("msg").addEventListener("input", autoGrow);
    // Dictée vocale : le texte reconnu est placé dans le champ, jamais envoyé automatiquement.
    if (window.HaltupVoice) window.HaltupVoice.init({ textarea: $("msg"), announce: addNotice });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
