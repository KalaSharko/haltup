"""Serveur HALTUP — Python 3.9+, bibliothèque standard uniquement.

Lancement :  python3 server.py   puis ouvrir http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from altup import ai
from altup.assistant import handle_adapt, handle_generate, handle_message, new_state
from altup.config import ROOT, settings
from altup.constants import public_config

PUBLIC_DIR = os.path.join(ROOT, "public")
BROWSER_TESTS_DIR = os.path.join(ROOT, "tests", "browser")
MAX_BODY = 64 * 1024
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def mode_info() -> dict:
    st = ai.status()
    if st["mode"] == "ai":
        return {"mode": "ai", "label": "Mode IA", "provider": st["provider"], "model": st["model"],
                "privacy": "Vos messages du chat sont envoyés à %s pour être interprétés. Les messages repérés "
                           "localement comme évoquant une douleur, une blessure ou un âge de moins de 18 ans sont "
                           "traités par les règles d'HALTUP et ne sont pas transmis. La dictée vocale facultative fait exception : elle est transcrite par votre navigateur, dont l'éditeur peut recevoir l'audio pour le transcrire (Google pour Chrome, Microsoft pour Edge, Apple pour Safari)." % st["provider"]}
    return {"mode": "demo", "label": "Mode démonstration",
            "reason": st["reason"],
            "privacy": "HALTUP n'envoie aucune donnée à un service externe : les séances sont générées par ses règles locales. "
                       "La dictée vocale facultative fait exception : elle est transcrite par votre navigateur, dont l'éditeur peut recevoir l'audio pour le transcrire (Google pour Chrome, Microsoft pour Edge, Apple pour Safari)."}


class Handler(BaseHTTPRequestHandler):
    server_version = "HALTUP/0.1"

    def log_message(self, fmt, *args):  # journal sobre, sans contenu des messages
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def _send(self, status, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/config":
            cfg = public_config()
            cfg["mode"] = mode_info()
            cfg["initialState"] = new_state()
            return self._json(200, cfg)
        if path == "/":
            path = "/index.html"
        base = PUBLIC_DIR
        # Tests de la dictée dans le navigateur : servis uniquement quand le serveur écoute en local.
        if path.startswith("/__tests__/") and settings.host in ("127.0.0.1", "localhost", "::1"):
            base, path = BROWSER_TESTS_DIR, path[len("/__tests__"):]
        full = os.path.normpath(os.path.join(base, path.lstrip("/")))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return self._json(404, {"error": "Page introuvable."})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._json(413, {"error": "Requête vide ou trop volumineuse."})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._json(400, {"error": "Requête illisible."})
        try:
            if path == "/api/chat":
                result = handle_message(body.get("message", ""), body.get("state"))
            elif path == "/api/generate":
                result = handle_generate(body.get("profile"), body.get("state"))
            elif path == "/api/adapt":
                result = handle_adapt(body.get("action"), body.get("exercise_id"), body.get("state"))
            else:
                return self._json(404, {"error": "Route inconnue."})
        except Exception:  # réponse de secours claire plutôt qu'une interface cassée
            traceback.print_exc()
            return self._json(500, {"error": "Une erreur interne est survenue. Réessayez ou recommencez la séance."})
        result["mode"] = mode_info()
        return self._json(200, result)


def main():
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    httpd = ThreadingHTTPServer((settings.host, settings.port), Handler)
    info = mode_info()
    print("HALTUP — http://%s:%d  (%s%s)" % (settings.host, settings.port, info["label"],
                                            " : " + info.get("reason", "") if info["mode"] == "demo" else ""))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")


if __name__ == "__main__":
    main()
