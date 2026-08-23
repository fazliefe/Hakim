import os
import tempfile

os.environ.setdefault("HAKIM_OLLAMA_ENABLED", "0")
os.environ["HAKIM_LLM_API_KEY"] = ""
os.environ["HAKIM_SMTP_HOST"] = ""
os.environ["HAKIM_SMTP_PASSWORD"] = ""

_fd, _auth_db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["HAKIM_AUTH_DB"] = _auth_db

_fd, _auth_db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["HAKIM_AUTH_DB"] = _auth_db
