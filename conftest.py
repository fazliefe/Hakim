import os
import tempfile

os.environ.setdefault("HAKIM_OLLAMA_ENABLED", "0")
os.environ["HAKIM_LLM_API_KEY"] = ""
os.environ["HAKIM_SMTP_HOST"] = ""
os.environ["HAKIM_SMTP_PASSWORD"] = ""
# apps/api/tests/test_auth.py sabit "admin1234" ile giriş yapıyor — her test
# oturumu aşağıda yeni/boş bir HAKIM_AUTH_DB aldığından, admin hesabı burada
# HER SEFERİNDE yeniden bootstrap edilir (bkz. services/auth/store.py::
# _bootstrap_admin_password). Bu satır olmadan bootstrap rastgele bir parola
# üretir ve testler kırılır.
os.environ["HAKIM_ADMIN_PASSWORD"] = "admin1234"

_fd, _auth_db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["HAKIM_AUTH_DB"] = _auth_db

_fd, _auth_db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["HAKIM_AUTH_DB"] = _auth_db
