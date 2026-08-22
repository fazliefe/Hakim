import os
import tempfile

os.environ.setdefault("HAKIM_OLLAMA_ENABLED", "0")
os.environ["HAKIM_LLM_API_KEY"] = ""

_fd, _auth_db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["HAKIM_AUTH_DB"] = _auth_db
