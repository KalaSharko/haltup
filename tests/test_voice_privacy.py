"""Tests ciblés de la dictée vocale côté projet : pas d'audio enregistré, téléversé ni sauvegardé.

Le comportement de l'interface (écoute, aperçu, insertion, annulation, erreurs) est vérifié par
tests/browser/voice.html, à ouvrir dans un navigateur (voir README).
"""
import json
import os
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import server  # noqa: E402

VOICE_JS = open(os.path.join(ROOT, "public", "voice.js"), encoding="utf-8").read()
APP_JS = open(os.path.join(ROOT, "public", "app.js"), encoding="utf-8").read()


def _code(js):
    """Code sans les commentaires (les commentaires peuvent citer MediaRecorder pour l'expliquer)."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", js)


class VoiceSourceTests(unittest.TestCase):
    def test_reconnaissance_du_navigateur_en_francais(self):
        code = _code(VOICE_JS)
        self.assertIn("window.SpeechRecognition || window.webkitSpeechRecognition", code)
        self.assertIn('rec.lang = "fr-FR"', code)
        self.assertIn("rec.interimResults = true", code)

    def test_aucune_capture_ni_envoi_audio_par_haltup(self):
        code = _code(VOICE_JS) + _code(APP_JS)
        for forbidden in ("MediaRecorder", "getUserMedia", "AudioContext", "sendBeacon", "FormData",
                          "new Blob", "indexedDB", "WebSocket"):
            self.assertNotIn(forbidden, code, forbidden)
        voice = _code(VOICE_JS)
        for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage"):
            self.assertNotIn(forbidden, voice, forbidden)

    def test_pas_de_soumission_depuis_la_dictee(self):
        voice = _code(VOICE_JS)
        self.assertNotIn("requestSubmit", voice)
        self.assertNotIn(".submit(", voice)
        self.assertNotIn("sendMessage", voice)


class ServerAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _req(self, path, data=None, ctype="application/json"):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=data,
                                     headers={"Content-Type": ctype} if data is not None else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_audio_refuse_par_le_serveur(self):
        audio = b"\x1aE\xdf\xa3" + os.urandom(2048)  # en-tête WebM + octets aléatoires
        self.assertEqual(self._req("/api/chat", audio, "audio/webm"), 400)
        self.assertIn(self._req("/api/upload", audio, "audio/webm"), (400, 404))  # aucune route d'envoi audio
        self.assertEqual(self._req("/api/chat", os.urandom(70 * 1024), "audio/webm"), 413)

    def test_page_de_test_servie_seulement_en_local(self):
        self.assertEqual(self._req("/__tests__/voice.html"), 200)
        with mock.patch.object(server.settings, "host", "0.0.0.0"):
            self.assertEqual(self._req("/__tests__/voice.html"), 404)
        self.assertEqual(self._req("/__tests__/../server.py"), 404)


if __name__ == "__main__":
    unittest.main()
