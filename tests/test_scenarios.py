"""Tests automatisés du moteur HALTUP (bibliothèque standard).

Lancement : python3 -m unittest discover -s tests -v

Ces tests vérifient le comportement du moteur ; ils ne remplacent pas la validation
manuelle de l'interface décrite dans docs/06-scenarios-validation.md.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from altup import ai, assistant  # noqa: E402
from altup.assistant import handle_generate, handle_message, new_state  # noqa: E402
from altup.knowledge import EXERCISES, available_equipment, is_feasible  # noqa: E402

OK = "J'ai 18 ans ou plus et aucune douleur ni blessure."


def chat(*messages, state=None):
    state = state or new_state()
    result = None
    for m in messages:
        result = handle_message(m, state)
        state = result["state"]
    return result


def session_of(result):
    for m in result["messages"]:
        if m["kind"] == "session":
            return m["session"]
    return None


def form(**kw):
    base = {"sport": "autre", "goal": "forme", "level": "debutant", "duration": 45, "place": "maison",
            "equipment": ["aucun"], "pain": False, "adult": True,
            "other_equipment_none": True, "fatigue_none": True}
    base.update(kw)
    if base.get("fatigue_next") or base.get("fatigue_recent"):
        base["fatigue_none"] = False
    return base


class Scenarios(unittest.TestCase):
    def assert_feasible(self, session, equipment):
        avail = available_equipment(equipment)
        for ex in session["main"]["exercises"]:
            self.assertTrue(is_feasible(EXERCISES[ex["id"]], avail), ex["id"])

    def test_01_football_debutant_explosivite_halteres_40(self):
        r = chat("Je joue au foot, je débute, je veux plus d'explosivité, j'ai des haltères et 40 minutes.", OK)
        s = session_of(r)
        self.assertIsNotNone(s)
        self.assertEqual(s["summary"]["sport"], "Football")
        self.assertLessEqual(s["summary"]["duration_estimated"], 40)
        self.assert_feasible(s, ["halteres"])
        for ex in s["main"]["exercises"]:
            self.assertEqual(EXERCISES[ex["id"]]["level"], 1, "débutant : exercices de niveau 1 uniquement")

    def test_02_maison_sans_materiel(self):
        s = session_of(handle_generate(form(equipment=["aucun"]), new_state()))
        for ex in s["main"]["exercises"]:
            self.assertEqual(ex["equipment"], "Poids du corps")

    def test_03_prise_de_muscle_salle(self):
        eq = ["halteres", "barre", "banc", "machines"]
        s = session_of(handle_generate(form(sport="rugby", goal="muscle", level="intermediaire", duration=60,
                                            place="salle", equipment=eq), new_state()))
        self.assertGreaterEqual(len(s["main"]["exercises"]), 4)
        self.assertLessEqual(s["summary"]["duration_estimated"], 60)
        self.assert_feasible(s, eq)

    def test_04_information_manquante_puis_hypotheses(self):
        r = chat("Bonjour, je veux une séance")
        self.assertIsNone(session_of(r))
        self.assertIn("préciser", r["messages"][-1]["text"])
        r = handle_message("je suis majeur, pas de douleur", r["state"])
        s = session_of(r)
        self.assertIsNotNone(s)
        self.assertTrue(s["assumptions"], "les hypothèses doivent être annoncées")
        # La question de profil n'est pas reposée.
        self.assertEqual(r["state"]["asked"].count("profile"), 1)

    def test_05_pas_de_banc(self):
        eq = ["halteres", "barre", "banc", "machines"]
        r = handle_generate(form(goal="muscle", level="intermediaire", duration=60, place="salle", equipment=eq), new_state())
        before = [e["id"] for e in session_of(r)["main"]["exercises"]]
        r = handle_message("Je n'ai pas de banc.", r["state"])
        s = session_of(r)
        self.assertNotIn("banc", r["state"]["profile"]["equipment"])
        self.assert_feasible(s, ["halteres", "barre", "machines"])
        after = [e["id"] for e in s["main"]["exercises"]]
        untouched = [i for i in before if "banc" not in str(EXERCISES[i]["equipment"])]
        for i in untouched:
            self.assertIn(i, after, "les exercices sans banc doivent être conservés")

    def test_06_duree_reduite(self):
        r = handle_generate(form(goal="muscle", duration=60, place="salle", equipment=["halteres", "banc", "machines"]), new_state())
        r = handle_message("Réduis la séance à 30 minutes.", r["state"])
        s = session_of(r)
        self.assertEqual(s["summary"]["duration_requested"], 30)
        self.assertLessEqual(s["summary"]["duration_estimated"], 30)
        self.assertGreaterEqual(len(s["main"]["exercises"]), 3)

    def test_07_douleur_zone_connue_seance_prudente(self):
        r = chat("Je fais du tennis, débutant, 30 min, salle, haltères et élastiques, j'ai 30 ans",
                 "j'ai une douleur à l'épaule")
        s = session_of(r)
        self.assertIsNotNone(s)
        self.assertIn("professionnel de santé", r["messages"][0]["text"])
        self.assertIn("épaule", s["caution"]["title"])
        self.assertIn("ne garantit pas", s["caution"]["text"])
        for ex in s["main"]["exercises"]:
            self.assertNotIn("epaule", EXERCISES[ex["id"]]["zones"], ex["id"])
            self.assertFalse(EXERCISES[ex["id"]].get("impact"))

    def test_07b_douleur_sans_zone_demande_la_zone(self):
        r = chat("J'ai 30 ans et j'ai une douleur")
        self.assertIsNone(session_of(r))
        self.assertIn("zone", r["messages"][-1]["text"])
        r = handle_message("Je préfère ne pas préciser la zone.", r["state"])
        self.assertIsNone(session_of(r))
        self.assertIn("ne pas vous proposer de programme", r["messages"][-1]["text"])

    def test_07c_signes_d_alerte_et_formulaire(self):
        r = chat("j'ai mal au genou, il est gonflé depuis ma chute")
        self.assertIsNone(session_of(r))
        self.assertIn("professionnel de santé", r["messages"][-1]["text"])
        r = handle_generate(form(pain=True), new_state())
        self.assertTrue(r.get("errors"), "zone manquante : erreur de formulaire explicite")
        r = handle_generate(form(pain=True, pain_zones=["genou", "epaule", "dos_bas"]), new_state())
        self.assertIsNone(session_of(r))
        r = handle_generate(form(pain=True, pain_zones=["genou"]), new_state())
        s = session_of(r)
        for ex in s["main"]["exercises"]:
            self.assertNotIn("genou", EXERCISES[ex["id"]]["zones"])

    def test_remplacer_et_retirer(self):
        r = handle_generate(form(goal="muscle", level="intermediaire", duration=60, place="salle",
                                 equipment=["halteres", "banc", "machines"]), new_state())
        st = r["state"]
        target = st["spec"]["ids"][0]
        r = assistant.handle_adapt("replace", target, st)
        s = session_of(r)
        new_ids = [e["id"] for e in s["main"]["exercises"]]
        self.assertNotIn(target, new_ids)
        self.assertTrue(any("remplacé" in c for c in s["changes"]))
        self.assert_feasible(s, ["halteres", "banc", "machines"])
        before = len(new_ids)
        r = assistant.handle_adapt("remove", r["state"]["spec"]["ids"][-1], r["state"])
        self.assertEqual(len(session_of(r)["main"]["exercises"]), before - 1)

    def test_scenarios_de_demo(self):
        from altup.constants import DEMO_SCENARIOS
        for sc in DEMO_SCENARIOS:
            p = dict(sc["profile"], adult=True)
            s = session_of(handle_generate(p, new_state()))
            self.assertIsNotNone(s, sc["id"])
            self.assert_feasible(s, p["equipment"])
            self.assertLessEqual(s["summary"]["duration_estimated"], p["duration"])
            if p["fatigue_next"]:
                for ex in s["main"]["exercises"]:
                    self.assertEqual(ex["sets"], 2)
                    self.assertNotEqual(ex["equipment"], "Barre et poids")
                    self.assertFalse(EXERCISES[ex["id"]].get("impact"))

    def test_08_sport_non_liste(self):
        r = chat("Je fais de l'escalade, objectif force, intermédiaire, 45 min à la salle, j'ai 30 ans, pas de blessure")
        s = session_of(r)
        self.assertIn("Escalade", s["summary"]["sport"])
        self.assertEqual(s["sport_note"]["confidence"], "aucune spécificité")

    def test_09_hors_sujet(self):
        r = chat("Quelle est la capitale du Pérou ?")
        self.assertIn("se concentre", r["messages"][-1]["text"])
        self.assertIsNone(session_of(r))

    def test_10a_sans_cle_ia_mode_demo(self):
        with mock.patch.object(ai.settings, "ai_provider", "anthropic"), \
             mock.patch.object(ai.settings, "anthropic_api_key", ""):
            self.assertEqual(ai.status()["mode"], "demo")
            s = session_of(chat("foot, débutant, explosivité, haltères, 40 min", OK))
            self.assertIsNotNone(s)

    def test_10b_echec_connexion_ia(self):
        with mock.patch.object(ai, "status", return_value={"mode": "ai", "provider": "Test", "model": "x"}), \
             mock.patch.object(ai, "complete_json", side_effect=ai.AIError("connexion impossible au service")):
            r = chat("foot, débutant, explosivité, haltères, 40 min", OK)
            self.assertIsNotNone(session_of(r))
            self.assertIn("moteur de règles", r.get("notice", ""))

    def test_10c_reponse_ia_invalide_revalidee(self):
        fake = {"reply": "Voici.", "profile_patch": {"equipment": ["machines", "inconnu"], "adult": True, "pain": False},
                "exercise_ids": ["developpe_couche_barre", "n_importe_quoi", "squat_barre"]}
        with mock.patch.object(ai, "status", return_value={"mode": "ai", "provider": "Test", "model": "x"}), \
             mock.patch.object(ai, "complete_json", return_value=fake):
            r = chat("foot, débutant, explosivité, haltères, 40 min")
            # L'IA ne peut pas confirmer l'âge ni l'absence de douleur à la place de l'utilisateur.
            self.assertIsNone(session_of(r))
            r = handle_message(OK, r["state"])
            s = session_of(r)
            for ex in s["main"]["exercises"]:
                self.assertNotIn(ex["id"], ("developpe_couche_barre", "squat_barre"))

    def test_10d_douleur_jamais_transmise_a_l_ia(self):
        import json as _json
        sent = []

        def fake(system, user):
            sent.append(_json.loads(user))
            return {"reply": "ok", "profile_patch": {}, "exercise_ids": []}
        with mock.patch.object(ai, "status", return_value={"mode": "ai", "provider": "Test", "model": "x"}), \
             mock.patch.object(ai, "complete_json", side_effect=fake):
            r = chat("foot, débutant, force, 30 min, haltères", "J'ai mal au genou", "j'ai 30 ans", "réduis à 20 minutes")
        self.assertTrue(sent)
        for payload in sent:
            payload.pop("CANDIDATES")
            text = _json.dumps(payload, ensure_ascii=False).lower()
            self.assertNotIn("mal au genou", text)
            self.assertNotIn("pain", payload["CURRENT_PROFILE"])

    def test_formulaire_dix_rubriques_obligatoires(self):
        r = handle_generate(form(other_equipment_none=False, fatigue_none=False), new_state())
        self.assertIsNone(session_of(r) if "messages" in r else None)
        self.assertTrue(any("Autre matériel" in e for e in r["errors"]))
        self.assertTrue(any("Charge sportive" in e for e in r["errors"]))
        r = handle_generate(form(other_equipment_none=False, other_equipment="step"), new_state())
        self.assertIsNotNone(session_of(r), "un autre matériel précisé suffit")
        r = handle_generate(form(fatigue_none=True, fatigue_next=True), new_state())
        self.assertIsNotNone(session_of(r))

    def test_mineur(self):
        r = chat("J'ai 16 ans et je veux faire de la muscu pour le basket")
        self.assertIn("18 ans", r["messages"][-1]["text"])
        self.assertIsNone(session_of(r))

    def test_match_demain_retire_les_sauts(self):
        r = chat("Je joue au foot, je débute, je veux plus d'explosivité, j'ai des haltères et 40 minutes.", OK)
        r = handle_message("J'ai un match ou un entraînement demain.", r["state"])
        s = session_of(r)
        self.assertEqual(r["state"]["profile"]["sport"], "football")
        for ex in s["main"]["exercises"]:
            self.assertFalse(EXERCISES[ex["id"]].get("impact"))

    def test_toutes_combinaisons_respectent_materiel_et_duree(self):
        from altup.constants import GOALS, SPORTS
        kits = [["aucun"], ["halteres"], ["elastiques"], ["halteres", "banc"], ["machines"],
                ["barre", "banc", "halteres", "machines", "elastiques", "kettlebell", "medecine_ball"]]
        for sport in SPORTS:
            for goal in GOALS:
                for level in ("debutant", "intermediaire", "avance"):
                    for kit in kits:
                        for duration in (15, 30, 45, 75):
                            p = form(sport=sport["id"], goal=goal["id"], level=level, equipment=kit, duration=duration)
                            s = session_of(handle_generate(p, new_state()))
                            self.assertGreaterEqual(len(s["main"]["exercises"]), 2, p)
                            self.assert_feasible(s, kit)
                            self.assertLessEqual(s["summary"]["duration_estimated"], duration + 2, p)


if __name__ == "__main__":
    unittest.main()
