from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pydantic import BaseModel
import sqlite3
import json
import asyncio
import os
import time
import re
import httpx
from pathlib import Path
from datetime import datetime

app = FastAPI(title="KeGhost - X ShadowBan Checker")
BASE_DIR = Path(__file__).resolve().parent

# Vercel filesystem is read-only except /tmp
ON_VERCEL = bool(os.environ.get("VERCEL"))
DB_PATH = "/tmp/shadowban.db" if ON_VERCEL else str(BASE_DIR / "shadowban.db")
INDEX_PATH = BASE_DIR / "index.html"
AVATAR_DIR = Path("/tmp/keghost-avatars" if ON_VERCEL else BASE_DIR / ".avatar-cache")
AVATAR_TTL_SEC = 60  # foto temp: 1 menit lalu hilang

# AgentX config (cookies live in AGENTX_HOME/accounts.json — never commit)
# On Vercel: set TWITTER_AUTH_TOKEN + TWITTER_CT0 as Environment Variables

def _load_dotenv():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


_load_dotenv()

AGENTX_BIN = os.environ.get(
    "AGENTX_BIN",
    str(Path(r"G:\Mirai Noa\agentx-src\agentx.exe")),
)
AGENTX_HOME = os.environ.get("AGENTX_HOME", str(BASE_DIR / ".agentx-home"))
AGENTX_ACCOUNT = os.environ.get("AGENTX_ACCOUNT", "keghost")
TWITTER_AUTH_TOKEN = (
    os.environ.get("TWITTER_AUTH_TOKEN")
    or os.environ.get("AUTH_TOKEN")
    or os.environ.get("X_AUTH_TOKEN")
    or ""
).strip()
TWITTER_CT0 = (
    os.environ.get("TWITTER_CT0")
    or os.environ.get("CT0")
    or os.environ.get("X_CT0")
    or ""
).strip()

AVATAR_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_DIR = BASE_DIR / "assets"

# --- Virtuals compute (PRIMARY provider) ---
VIRTUALS_KEY = (
    os.environ.get("VIRTUALS_KEY")
    or os.environ.get("VIRTUALS_API_KEY")
    or os.environ.get("VIRTU_KEY")
    or "acp-83a76573584e058953aa"
).strip()
VIRTUALS_URL = os.environ.get(
    "VIRTUALS_URL", "https://compute.virtuals.io/v1/chat/completions"
)
# Deep analysis: minimax-m3 (matches chat). Public label = "Claude Opus 4.8".
VIRTUALS_MODEL = os.environ.get("VIRTUALS_MODEL", "minimax-minimax-m3")
# CapyAi chat
VIRTUALS_CHAT_MODEL = os.environ.get("VIRTUALS_CHAT_MODEL", "minimax-minimax-m3")

# --- Cline provider (disabled by default; opt-in via CLINE_FORCE=1) ---
CLINE_API_KEY = os.environ.get("CLINE_API_KEY", "").strip()
CLINE_COOKIE = os.environ.get("CLINE_COOKIE", "").strip()
CLINE_URL = os.environ.get(
    "CLINE_URL", "https://api.cline.bot/api/v1/chat/completions"
)
CLINE_CHAT_MODEL = os.environ.get("CLINE_CHAT_MODEL", "cline-pass/mimo-2.5")
CLINE_DEEP_MODEL = os.environ.get("CLINE_DEEP_MODEL", "cline-pass/mimo-2.5")
CLINE_FORCE = os.environ.get("CLINE_FORCE", "").strip() in ("1", "true", "yes")

# Public-facing model name shown to users everywhere. NEVER expose the real
# chat backend model name — always report this instead.
PUBLIC_MODEL_NAME = "Claude Opus 4.8 Fast"

# --- CapyAi chat quota / follow-gate ---
BRAND_HANDLE = os.environ.get("BRAND_HANDLE", "hyaerina").lstrip("@")
CHAT_LIMIT_FOLLOWER = int(os.environ.get("CHAT_LIMIT_FOLLOWER", "20"))
CHAT_LIMIT_GUEST = int(os.environ.get("CHAT_LIMIT_GUEST", "5"))
WIB_OFFSET_SEC = 7 * 3600  # UTC+7

# Deep-analysis cache: username -> (expiry_epoch, payload). TTL 10 min.
DEEP_CACHE: dict = {}
DEEP_TTL_SEC = 600

# --- Supabase (shared, persistent scan history) ---
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or ""
).strip()
SUPABASE_ON = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


async def sb_insert_scan(row: dict) -> None:
    """Persist one scan to Supabase (shared history). Silent on failure."""
    if not SUPABASE_ON:
        return
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/scans",
                headers=_sb_headers({"Prefer": "return=minimal"}),
                json=row,
            )
    except Exception:
        pass


async def sb_recent(limit: int = 5) -> list:
    """Last N distinct-ish scans for the recent chips."""
    if not SUPABASE_ON:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans"
                f"?select=username,overall,avatar_url,created_at"
                f"&order=created_at.desc&limit={int(limit)}",
                headers=_sb_headers(),
            )
        if 200 <= r.status_code < 300:
            return r.json() or []
    except Exception:
        pass
    return []


async def sb_history(limit: int = 40) -> list:
    if not SUPABASE_ON:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans"
                f"?select=id,username,overall,avatar_url,search_vis,reply_rate,quote_rate,engagement,created_at"
                f"&order=created_at.desc&limit={int(limit)}",
                headers=_sb_headers(),
            )
        if 200 <= r.status_code < 300:
            return r.json() or []
    except Exception:
        pass
    return []


async def sb_scan_detail(scan_id: int) -> dict | None:
    if not SUPABASE_ON:
        return None
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans?select=*&id=eq.{int(scan_id)}&limit=1",
                headers=_sb_headers(),
            )
        if 200 <= r.status_code < 300:
            rows = r.json() or []
            return rows[0] if rows else None
    except Exception:
        pass
    return None


async def sb_user_history(username: str, limit: int = 20) -> list:
    """All scans for one username, oldest first — for timeline view."""
    if not SUPABASE_ON:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans"
                f"?select=id,username,overall,search_vis,reply_rate,quote_rate,engagement,layers,avatar_url,created_at"
                f"&username=eq.{_safe_username(username)}"
                f"&order=created_at.asc&limit={int(limit)}",
                headers=_sb_headers(),
            )
        if 200 <= r.status_code < 300:
            return r.json() or []
    except Exception:
        pass
    return []


def wib_today() -> str:
    """Current date string in WIB (UTC+7). Quota resets at 00:00 WIB."""
    return datetime.utcfromtimestamp(time.time() + WIB_OFFSET_SEC).strftime("%Y-%m-%d")


async def check_follows_brand(username: str) -> bool:
    """Does @username follow the brand handle? Uses cookie GraphQL/v1.1.
    Returns False on any error (fail-closed → treated as guest)."""
    uname = _safe_username(username)
    if not uname:
        return False
    headers = _cookie_headers()
    if not headers:
        return False
    import urllib.parse
    qs = urllib.parse.urlencode(
        {"source_screen_name": uname, "target_screen_name": BRAND_HANDLE}
    )
    url = f"https://api.x.com/1.1/friendships/show.json?{qs}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return False
        rel = (r.json() or {}).get("relationship", {})
        return bool(rel.get("source", {}).get("following"))
    except Exception:
        return False


async def sb_chat_quota_get(username: str, day: str) -> int:
    """How many chats this username has used today (WIB). 0 if none/unavailable."""
    if not SUPABASE_ON:
        return 0
    import urllib.parse
    uq = urllib.parse.quote(username, safe="")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/chat_usage"
                f"?select=count&username=eq.{uq}&day=eq.{day}&limit=1",
                headers=_sb_headers(),
            )
        if 200 <= r.status_code < 300:
            rows = r.json() or []
            return int(rows[0]["count"]) if rows else 0
    except Exception:
        pass
    return 0


async def sb_chat_quota_incr(username: str, day: str) -> None:
    """Atomically increment today's chat count via Postgres RPC (upsert)."""
    if not SUPABASE_ON:
        return
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/bump_chat_usage",
                headers=_sb_headers(),
                json={"p_username": username, "p_day": day},
            )
    except Exception:
        pass


# Cline refresh support (optional). Some Cline OAuth tokens are short-lived.
# Set these env vars to enable background refresh on 401:
#   CLINE_REFRESH_URL  = full URL to hit for a new token
#   CLINE_REFRESH_BODY = JSON body to POST (e.g. {"refresh_token": "..."})
#   CLINE_REFRESH_HEADER = optional extra header (e.g. 'X-Api-Key: ...')
# If the refresh succeeds, the new token is written to a small cache file
# (CLINE_REFRESH_CACHE_FILE, default /tmp/cline_token.json) and used for the
# rest of the request. This avoids needing a redeploy when the token rotates.
CLINE_REFRESH_URL = os.environ.get("CLINE_REFRESH_URL", "").strip()
CLINE_REFRESH_BODY = os.environ.get("CLINE_REFRESH_BODY", "").strip()
CLINE_REFRESH_HEADER = os.environ.get("CLINE_REFRESH_HEADER", "").strip()
CLINE_REFRESH_CACHE_FILE = os.environ.get(
    "CLINE_REFRESH_CACHE_FILE", "/tmp/cline_token.json" if ON_VERCEL else str(BASE_DIR / ".cline_token.json")
)


def _read_cached_token() -> str | None:
    """Use refreshed token from cache if it overrides the env-provided one."""
    if not CLINE_REFRESH_URL:
        return None
    try:
        import json as _json
        p = Path(CLINE_REFRESH_CACHE_FILE)
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8"))
            tok = (data.get("access_token") or data.get("token") or "").strip()
            if tok:
                return tok
    except Exception:
        pass
    return None


def _write_cached_token(tok: str) -> None:
    if not CLINE_REFRESH_URL or not tok:
        return
    try:
        import json as _json
        Path(CLINE_REFRESH_CACHE_FILE).write_text(
            _json.dumps({"access_token": tok}), encoding="utf-8"
        )
    except Exception:
        pass


async def _refresh_cline_token() -> str | None:
    """Try to mint a new Cline access token. Returns None on failure."""
    if not CLINE_REFRESH_URL or not CLINE_REFRESH_BODY:
        return None
    try:
        import json as _json
        body = _json.loads(CLINE_REFRESH_BODY)
    except Exception:
        body = CLINE_REFRESH_BODY
    hdrs = {"Content-Type": "application/json"}
    if CLINE_REFRESH_HEADER:
        # format: "Key: Value"
        if ":" in CLINE_REFRESH_HEADER:
            k, v = CLINE_REFRESH_HEADER.split(":", 1)
            hdrs[k.strip()] = v.strip()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(CLINE_REFRESH_URL, headers=hdrs, json=body if isinstance(body, dict) else None)
        if not (200 <= r.status_code < 300):
            return None
        data = r.json()
        tok = (data.get("access_token") or data.get("token") or "").strip()
        if tok:
            _write_cached_token(tok)
            return tok
    except Exception:
        return None
    return None


async def _cline_chat(
    model: str,
    messages: list,
    *,
    timeout: float = 60.0,
    max_retries: int = 2,
) -> str:
    """Call Cline /v1/chat/completions. Retry on 429/5xx; refresh-on-401 once.
    Returns the assistant text. Raises RuntimeError on hard failure."""
    if not (CLINE_API_KEY or CLINE_COOKIE or _read_cached_token()):
        raise RuntimeError(
            "Cline auth not set (set CLINE_COOKIE or CLINE_API_KEY in env)"
        )

    last_err = "unknown"
    refreshed = False
    for attempt in range(max_retries + 1):
        # Cline Pass web: cookie session. Cline CLI/API: Bearer token.
        use_cookie = bool(CLINE_COOKIE)
        cred = (
            CLINE_COOKIE
            if use_cookie
            else (_read_cached_token() or CLINE_API_KEY)
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if use_cookie:
            headers["Cookie"] = cred
            # Cline web also expects a referer + UA — copy browser defaults.
            headers["Referer"] = "https://app.cline.bot/"
            headers["Origin"] = "https://app.cline.bot"
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        else:
            headers["Authorization"] = f"Bearer {cred}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    CLINE_URL,
                    headers=headers,
                    json={"model": model, "messages": messages, "stream": False},
                )
            if 200 <= r.status_code < 300:
                data = r.json()
                return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            # Auth: try to refresh token once, then retry (only for Bearer path)
            if r.status_code in (401, 403) and not refreshed and not use_cookie:
                new_tok = await _refresh_cline_token()
                if new_tok:
                    refreshed = True
                    continue
                raise RuntimeError(
                    f"Cline auth expired (HTTP {r.status_code}). "
                    "Set ulang CLINE_API_KEY di Vercel env, atau konfig refresh."
                )
            if r.status_code in (401, 403) and use_cookie:
                raise RuntimeError(
                    f"Cline cookie expired (HTTP {r.status_code}). "
                    "Login ulang ke Cline, copy cookie baru, set CLINE_COOKIE di Vercel."
                )
            # retry only on transient overload / rate
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                await asyncio.sleep(0.6 * (attempt + 1))
                continue
            last_err = f"Cline HTTP {r.status_code}: {r.text[:160]}"
            break
        except RuntimeError:
            raise
        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            last_err = f"Cline timeout: {e}"
            if attempt < max_retries:
                await asyncio.sleep(0.6 * (attempt + 1))
                continue
            break
        except Exception as e:
            last_err = f"Cline error: {e}"
            break
    raise RuntimeError(last_err)


async def _virtuals_chat(
    model: str,
    messages: list,
    *,
    timeout: float = 90.0,
    max_retries: int = 2,
) -> str:
    """Call Virtuals with retry on transient 5xx/429. Returns assistant text."""
    if not VIRTUALS_KEY:
        raise RuntimeError("VIRTUALS_KEY not set")
    last_err = "unknown"
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    VIRTUALS_URL,
                    headers={
                        "Authorization": f"Bearer {VIRTUALS_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "messages": messages},
                )
            if 200 <= r.status_code < 300:
                data = r.json()
                return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            last_err = f"Virtuals HTTP {r.status_code}: {r.text[:160]}"
            break
        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            last_err = f"Virtuals timeout: {e}"
            if attempt < max_retries:
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            break
        except Exception as e:
            last_err = f"Virtuals error: {e}"
            break
    raise RuntimeError(last_err)


def ensure_agentx_account_from_env() -> None:
    """Bootstrap agentx account from env cookies when binary is present."""
    if not TWITTER_AUTH_TOKEN or not TWITTER_CT0:
        return
    if not Path(AGENTX_BIN).exists():
        return
    Path(AGENTX_HOME).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AGENTX_HOME"] = AGENTX_HOME
    try:
        import subprocess
        subprocess.run(
            [
                AGENTX_BIN,
                "account",
                "add",
                "--name",
                AGENTX_ACCOUNT,
                "--auth-token",
                TWITTER_AUTH_TOKEN,
                "--ct0",
                TWITTER_CT0,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
    except Exception:
        pass


ensure_agentx_account_from_env()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        overall TEXT,
        search_vis INTEGER,
        reply_rate INTEGER,
        quote_rate INTEGER,
        engagement INTEGER,
        tests TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )"""
    )
    # Migration: add avatar_url column for /api/recent
    cols = [r[1] for r in c.execute("PRAGMA table_info(checks)").fetchall()]
    if "avatar_url" not in cols:
        c.execute("ALTER TABLE checks ADD COLUMN avatar_url TEXT")
    conn.commit()
    conn.close()


init_db()


class CheckRequest(BaseModel):
    username: str


def _safe_username(username: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (username or "").lower().lstrip("@"))[:40]


def cleanup_expired_avatars() -> None:
    """Hapus foto cache yang sudah lewat 1 menit."""
    now = time.time()
    try:
        for p in AVATAR_DIR.glob("*"):
            if not p.is_file():
                continue
            try:
                if now - p.stat().st_mtime > AVATAR_TTL_SEC:
                    p.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass


def find_avatar_file(username: str):
    uname = _safe_username(username)
    if not uname:
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        candidate = AVATAR_DIR / f"{uname}{ext}"
        if candidate.exists() and candidate.is_file():
            age = time.time() - candidate.stat().st_mtime
            if age <= AVATAR_TTL_SEC:
                return candidate
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
    return None


async def cache_avatar(username: str, source_url: str):
    """Download avatar ke temp. Hidup 1 menit. Return path API lokal."""
    cleanup_expired_avatars()
    uname = _safe_username(username)
    if not uname or not source_url:
        return None

    existing = find_avatar_file(uname)
    if existing:
        try:
            os.utime(existing, None)  # re-check → TTL restart 1 menit
        except OSError:
            pass
        return f"/api/avatar/{uname}?t={int(time.time())}"

    url = source_url
    for old, new in (
        ("_normal.", "_400x400."),
        ("_bigger.", "_400x400."),
        ("_mini.", "_400x400."),
    ):
        if old in url:
            url = url.replace(old, new)
            break

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            r = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Referer": "https://x.com/",
                },
            )
        if r.status_code != 200 or not r.content:
            return None

        ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
        ext = ".jpg"
        if "png" in ctype or url.lower().endswith(".png"):
            ext = ".png"
        elif "webp" in ctype:
            ext = ".webp"
        elif "gif" in ctype:
            ext = ".gif"

        for old in AVATAR_DIR.glob(f"{uname}.*"):
            try:
                old.unlink(missing_ok=True)
            except OSError:
                pass

        dest = AVATAR_DIR / f"{uname}{ext}"
        dest.write_bytes(r.content)
        return f"/api/avatar/{uname}?t={int(time.time())}"
    except Exception:
        return None


@app.get("/api/avatar/{username}")
async def serve_avatar(username: str):
    """Serve foto profil temp. >1 menit → 404 (hilang)."""
    cleanup_expired_avatars()
    path = find_avatar_file(username)
    if not path:
        return Response(status_code=404, content=b"avatar expired or missing")

    media = "image/jpeg"
    suf = path.suffix.lower()
    if suf == ".png":
        media = "image/png"
    elif suf == ".webp":
        media = "image/webp"
    elif suf == ".gif":
        media = "image/gif"

    return FileResponse(
        path,
        media_type=media,
        headers={
            "Cache-Control": f"public, max-age={AVATAR_TTL_SEC}",
            "X-Avatar-TTL": str(AVATAR_TTL_SEC),
        },
    )


async def run_agentx(*args: str, timeout: float = 35.0) -> dict:
    """Run agentx CLI and parse the JSON envelope."""
    if not Path(AGENTX_BIN).exists():
        return {"ok": False, "error": {"code": "missing_binary", "message": f"agentx not found: {AGENTX_BIN}"}}

    env = os.environ.copy()
    env["AGENTX_HOME"] = AGENTX_HOME
    # Prefer browser-like TLS when available
    env.setdefault("AGENTX_UTLS", "1")

    cmd = [AGENTX_BIN, "-a", AGENTX_ACCOUNT, *args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"ok": False, "error": {"code": "timeout", "message": "agentx timed out"}}
    except Exception as e:
        return {"ok": False, "error": {"code": "spawn_error", "message": str(e)}}

    text = (stdout or b"").decode("utf-8", errors="replace").strip()
    if not text:
        err = (stderr or b"").decode("utf-8", errors="replace").strip()
        return {"ok": False, "error": {"code": "empty_output", "message": err or "no output from agentx"}}

    # agentx prints one JSON object (may be pretty multi-line)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try last JSON object in stream
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"ok": False, "error": {"code": "bad_json", "message": text[:300]}}


def _screen(u: dict) -> str:
    return (u.get("screenName") or u.get("screen_name") or u.get("username") or "").lstrip("@").lower()


def _author_screen(item: dict) -> str:
    author = item.get("author") or {}
    if isinstance(author, dict):
        return _screen(author)
    return ""


def _metrics_of(posts: list) -> dict:
    if not posts:
        return {"avg_views": 0, "avg_likes": 0, "avg_replies": 0, "avg_rts": 0, "avg_quotes": 0, "reply_ratio": 0, "quote_ratio": 0}
    views = likes = replies = rts = quotes = 0
    for p in posts:
        m = p.get("metrics") or {}
        views += int(m.get("views") or 0)
        likes += int(m.get("likes") or 0)
        replies += int(m.get("replies") or 0)
        rts += int(m.get("retweets") or 0)
        quotes += int(m.get("quotes") or 0)
    n = len(posts)
    avg_views = views / n
    return {
        "avg_views": avg_views,
        "avg_likes": likes / n,
        "avg_replies": replies / n,
        "avg_rts": rts / n,
        "avg_quotes": quotes / n,
        "reply_ratio": (replies / max(views, 1)),
        "quote_ratio": (quotes / max(views, 1)),
        "total_views": views,
    }


def _clamp(n, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def build_profile(user: dict) -> dict:
    img = user.get("profileImageUrl") or user.get("profile_image_url") or ""
    # prefer higher-res avatar
    if img.endswith("_normal.jpg"):
        img = img.replace("_normal.jpg", "_400x400.jpg")
    elif img.endswith("_normal.png"):
        img = img.replace("_normal.png", "_400x400.png")
    return {
        "id": str(user.get("id") or ""),
        "name": user.get("name") or "",
        "username": _screen(user),
        "bio": user.get("bio") or user.get("description") or "",
        "followers": int(user.get("followersCount") or user.get("followers_count") or 0),
        "following": int(user.get("followingCount") or user.get("following_count") or 0),
        "tweets": int(user.get("tweetsCount") or user.get("statuses_count") or 0),
        "verified": bool(user.get("verified") or False),
        "protected": bool(user.get("protected") or False),
        "avatar": img,
        "createdAt": user.get("createdAt") or user.get("created_at") or "",
    }



# --- Cookie HTTP fallback (works on Vercel without agentx binary) ---
X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
X_QID = {
    # 2026-07-12 (KIRA): updated QIDs from main.4b8dc5fa.js bundle.
    # Old QIDs: UserByScreenName=1VOOyvKkiI3FMmkeDNxM9A, UserTweets=q6xj5bs0hapm9309hexA_g
    # SearchTimeline=VhUd6vHVmLBcw0uX-6jMLA (deprecated by X — returns 404 for all accounts)
    "UserByScreenName": os.environ.get("AGENTX_QID_UserByScreenName", "2qvSHpkWTMS9i0zJAwDNiA"),
    "UserTweets": os.environ.get("AGENTX_QID_UserTweets", "hr4gzZONlq23okjU8fIe_A"),
    "SearchTimeline": os.environ.get("AGENTX_QID_SearchTimeline", "Bcw3RzK-PatNAmbnw54hFw"),
    # 2026-07-13 (KIRA): Following/Followers QIDs from main.4b8dc5fa.js
    # REST friends/list.json is deprecated (404), GraphQL Following still works.
    # GraphQL Followers is 404 — use REST followers/list.json instead.
    "Following": os.environ.get("AGENTX_QID_Following", "eNoXdfXv5rU75RBzlmfuPA"),
}
X_FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}


def _cookie_headers() -> dict:
    if not TWITTER_AUTH_TOKEN or not TWITTER_CT0:
        return {}
    return {
        "authorization": f"Bearer {X_BEARER}",
        "x-csrf-token": TWITTER_CT0,
        "cookie": f"auth_token={TWITTER_AUTH_TOKEN}; ct0={TWITTER_CT0}",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "accept": "*/*",
        "content-type": "application/json",
        "referer": "https://x.com/",
    }


async def x_typeahead(username: str) -> dict:
    """REST typeahead check — does @username appear in search suggestions?

    Works on free-tier cookie auth (SearchTimeline GraphQL is deprecated, but
    this REST endpoint still returns 200). Returns:
      {"available": True/False, "found": True/False, "hits": int, "err": str}

    - available=False → endpoint failed (auth/network), can't test
    - found=True → username appears in typeahead → NOT suggestion banned
    - found=False → username absent from suggestions → suggestion banned
    """
    headers = _cookie_headers()
    if not headers:
        return {"available": False, "found": False, "hits": 0, "err": "no cookies"}
    uname = _safe_username(username)
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(
                "https://x.com/i/api/1.1/search/typeahead.json",
                params={"q": uname, "src": "search_box", "result_type": "users"},
                headers=headers,
            )
        if r.status_code != 200:
            return {"available": False, "found": False, "hits": 0,
                    "err": f"typeahead HTTP {r.status_code}"}
        users = (r.json() or {}).get("users") or []
        found = any((u.get("screen_name") or "").lower() == uname for u in users)
        return {"available": True, "found": found, "hits": len(users), "err": ""}
    except Exception as e:
        return {"available": False, "found": False, "hits": 0, "err": str(e)[:80]}


async def x_graphql(op: str, variables: dict, extra_features: dict | None = None) -> dict:
    headers = _cookie_headers()
    if not headers:
        raise RuntimeError("TWITTER_AUTH_TOKEN / TWITTER_CT0 missing on this host")
    qid = X_QID.get(op)
    if not qid:
        raise RuntimeError(f"unknown graphql op {op}")
    features = dict(X_FEATURES)
    if extra_features:
        features.update(extra_features)
    import urllib.parse
    qs = urllib.parse.urlencode(
        {
            "variables": json.dumps(variables, separators=(",", ":")),
            "features": json.dumps(features, separators=(",", ":")),
        }
    )
    url = f"https://x.com/i/api/graphql/{qid}/{op}?{qs}"
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
    if r.status_code == 404:
        raise RuntimeError(f"graphql {op} query id expired (404) — set AGENTX_QID_{op}")
    if r.status_code in (401, 403):
        raise RuntimeError(f"graphql auth failed ({r.status_code}) — refresh TWITTER_AUTH_TOKEN/CT0")
    if r.status_code != 200:
        raise RuntimeError(f"graphql {op} HTTP {r.status_code}: {r.text[:180]}")
    return r.json()


def _walk(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _parse_user_result(result: dict) -> dict | None:
    if not isinstance(result, dict):
        return None
    if result.get("__typename") == "UserUnavailable":
        return None
    legacy = result.get("legacy") or {}
    core = result.get("core") or {}
    screen = (
        legacy.get("screen_name")
        or core.get("screen_name")
        or result.get("screen_name")
        or ""
    )
    if not screen and not result.get("rest_id"):
        return None
    avatar = legacy.get("profile_image_url_https") or legacy.get("profile_image_url") or ""
    return {
        "id": str(result.get("rest_id") or legacy.get("id_str") or ""),
        "name": legacy.get("name") or core.get("name") or "",
        "screenName": screen,
        "bio": legacy.get("description") or "",
        "followersCount": int(legacy.get("followers_count") or 0),
        "followingCount": int(legacy.get("friends_count") or 0),
        "tweetsCount": int(legacy.get("statuses_count") or 0),
        "verified": bool(result.get("is_blue_verified") or legacy.get("verified")),
        "protected": bool(legacy.get("protected")),
        "profileImageUrl": avatar,
        "createdAt": legacy.get("created_at") or "",
    }


def _extract_tweets_from_timeline(data: dict) -> list:
    """Pull tweet objects from GraphQL timeline instructions."""
    out = []
    # common path: data.user.result.timeline.timeline.instructions
    instructions = (
        _walk(data, "data", "user", "result", "timeline", "timeline", "instructions")
        or _walk(data, "data", "user", "result", "timeline_v2", "timeline", "instructions")
        or _walk(data, "data", "search_by_raw_query", "search_timeline", "timeline", "instructions")
        or _walk(data, "data", "threaded_conversation_with_injections_v2", "instructions")
        or []
    )
    if not isinstance(instructions, list):
        return out

    def add_tweet(tr: dict):
        if not isinstance(tr, dict):
            return
        # unwrap TweetWithVisibilityResults
        if tr.get("__typename") == "TweetWithVisibilityResults":
            tr = tr.get("tweet") or {}
        legacy = tr.get("legacy") or {}
        if not legacy and tr.get("result"):
            return add_tweet(tr.get("result") or {})
        rest_id = str(tr.get("rest_id") or legacy.get("id_str") or "")
        if not rest_id:
            return
        user_res = _walk(tr, "core", "user_results", "result") or {}
        u_legacy = user_res.get("legacy") or {}
        views = 0
        try:
            views = int((tr.get("views") or {}).get("count") or 0)
        except Exception:
            views = 0
        # 2026-07-13 (KIRA): media type detection for analytics
        entities = legacy.get("entities") or {}
        media_list = entities.get("media") or []
        urls_list = entities.get("urls") or []
        if media_list:
            mtype = media_list[0].get("type") or "photo"
            media_type = "video" if mtype in ("video", "animated_gif") else "image"
        elif urls_list:
            media_type = "link"
        elif legacy.get("full_text", "").startswith("RT @"):
            media_type = "retweet"
        else:
            media_type = "text"

        out.append(
            {
                "id": rest_id,
                "text": legacy.get("full_text") or legacy.get("text") or "",
                "mediaType": media_type,
                "author": {
                    "screenName": u_legacy.get("screen_name") or "",
                    "name": u_legacy.get("name") or "",
                    "id": str(user_res.get("rest_id") or ""),
                },
                "metrics": {
                    "likes": int(legacy.get("favorite_count") or 0),
                    "retweets": int(legacy.get("retweet_count") or 0),
                    "replies": int(legacy.get("reply_count") or 0),
                    "quotes": int(legacy.get("quote_count") or 0),
                    "views": views,
                    "bookmarks": int(legacy.get("bookmark_count") or 0),
                },
                "createdAt": legacy.get("created_at") or "",
            }
        )

    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        entries = []
        if inst.get("type") == "TimelineAddEntries":
            entries = inst.get("entries") or []
        elif inst.get("type") == "TimelinePinEntry" and inst.get("entry"):
            entries = [inst.get("entry")]
        for ent in entries:
            content = (ent or {}).get("content") or {}
            item = content.get("itemContent") or {}
            tr = _walk(item, "tweet_results", "result")
            if tr:
                add_tweet(tr)
            # module items
            for it in (content.get("items") or []):
                ic = ((it or {}).get("item") or {}).get("itemContent") or {}
                tr2 = _walk(ic, "tweet_results", "result")
                if tr2:
                    add_tweet(tr2)
    # dedupe by id
    seen = set()
    uniq = []
    for t in out:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        uniq.append(t)
    return uniq


async def fetch_via_cookies(username: str) -> dict | None:
    """Fetch profile+posts(+optional search) using TWITTER cookies on Vercel."""
    if not TWITTER_AUTH_TOKEN or not TWITTER_CT0:
        return None
    username = username.lower().replace("@", "").strip()
    try:
        user_json = await x_graphql(
            "UserByScreenName",
            {"screen_name": username, "withSafetyModeUserFields": True},
            {
                "hidden_profile_subscriptions_enabled": True,
                "subscriptions_verification_info_is_identity_verified_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "highlights_tweets_tab_ui_enabled": True,
                "responsive_web_twitter_article_notes_tab_enabled": True,
                "subscriptions_feature_can_gift_premium": True,
            },
        )
    except Exception as e:
        # fallback: fxtwitter public profile
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(f"https://api.fxtwitter.com/{username}")
            if r.status_code != 200:
                raise RuntimeError(str(e))
            fx = r.json().get("user") or {}
            if not fx:
                raise RuntimeError(str(e))
            profile = {
                "id": str(fx.get("id") or ""),
                "name": fx.get("name") or "",
                "username": (fx.get("screen_name") or username).lower(),
                "bio": fx.get("description") or "",
                "followers": int(fx.get("followers") or 0),
                "following": int(fx.get("following") or 0),
                "tweets": int(fx.get("tweets") or 0),
                "verified": bool((fx.get("verification") or {}).get("verified") if isinstance(fx.get("verification"), dict) else False),
                "protected": bool(fx.get("protected")),
                "avatar": (fx.get("avatar_url") or "").replace("_normal", "_400x400"),
                "createdAt": fx.get("joined") or "",
            }
            local_avatar = await cache_avatar(username, profile.get("avatar") or "")
            if local_avatar:
                profile["avatar"] = local_avatar
                profile["avatar_cached"] = True
                profile["avatar_ttl_sec"] = AVATAR_TTL_SEC
            return {
                "profile": profile,
                "posts": [],
                "from_own": [],
                "people_own": [],
                "bare_own": [],
                "mentioned": [],
                "hashtag": None,
                "hashtag_own": [],
                "source": {"engine": "fxtwitter", "account": "public", "note": "cookie graphql failed; public profile only"},
            }
        except Exception:
            raise RuntimeError(f"cookie fetch failed: {e}")

    result = _walk(user_json, "data", "user", "result") or {}
    if result.get("__typename") == "UserUnavailable" or not result:
        return {
            "profile": None,
            "not_found": True,
            "posts": [],
            "from_own": [],
            "people_own": [],
            "bare_own": [],
            "mentioned": [],
            "hashtag": None,
            "hashtag_own": [],
            "source": {"engine": "x-cookie", "account": "env"},
        }

    user = _parse_user_result(result)
    if not user:
        return None
    profile = build_profile(user)
    uid = user.get("id") or ""

    posts = []
    if uid:
        try:
            tw_json = await x_graphql(
                "UserTweets",
                {
                    "userId": uid,
                    "count": 12,
                    "includePromotedContent": False,
                    "withQuickPromoteEligibilityTweetFields": True,
                    "withVoice": True,
                    "withV2Timeline": True,
                },
            )
            posts = _extract_tweets_from_timeline(tw_json)
        except Exception:
            posts = []

    # Search probes (optional — query ids rotate)
    from_own = []
    people_own = []
    bare_own = []
    # 2026-07-12 (KIRA): track whether SearchTimeline probe actually
    # succeeded. If the QID is expired (404) or GraphQL fails, search
    # results are empty NOT because the account is shadowbanned — but
    # because we couldn't run the test. audit_8_layers must distinguish
    # "search failed" (warning: untested) from "search returned empty"
    # (banned: genuinely deindexed). Old code conflated both → every
    # account showed "banned" when QID rotated.
    search_available = True
    search_err_msg = ""

    try:
        s1 = await x_graphql(
            "SearchTimeline",
            {"rawQuery": f"from:{username}", "count": 10, "querySource": "typed_query", "product": "Latest"},
        )
        from_own = [t for t in _extract_tweets_from_timeline(s1) if _author_screen(t) == username]
    except Exception as e:
        from_own = []
        search_available = False
        search_err_msg = str(e)[:120]

    try:
        s2 = await x_graphql(
            "SearchTimeline",
            {"rawQuery": f"@{username}", "count": 10, "querySource": "typed_query", "product": "Latest"},
        )
        people_hits_raw = _extract_tweets_from_timeline(s2)
        people_own = [t for t in people_hits_raw if _author_screen(t) == username]
    except Exception as e:
        people_hits_raw = []
        people_own = []
        if not search_err_msg:
            search_err_msg = str(e)[:120]
        # don't set search_available=False again if already set

    # Bare username search (for INDEX layer)
    try:
        s_bare = await x_graphql(
            "SearchTimeline",
            {"rawQuery": username, "count": 10, "querySource": "typed_query", "product": "Latest"},
        )
        bare_hits_raw = _extract_tweets_from_timeline(s_bare)
        bare_own = [t for t in bare_hits_raw if _author_screen(t) == username]
    except Exception:
        bare_hits_raw = []
        bare_own = []

    hashtag = None
    hashtag_own = []
    for p in posts:
        for token in (p.get("text") or "").split():
            if token.startswith("#") and len(token) > 2:
                hashtag = token
                break
        if hashtag:
            break
    if hashtag:
        try:
            s3 = await x_graphql(
                "SearchTimeline",
                {"rawQuery": hashtag, "count": 15, "querySource": "typed_query", "product": "Latest"},
            )
            hashtag_own = [t for t in _extract_tweets_from_timeline(s3) if _author_screen(t) == username]
        except Exception:
            hashtag_own = []

    # 2026-07-12 (KIRA): Mentioned by others — use RAW search hits
    # (people_hits_raw + bare_hits_raw), NOT the _own filtered lists.
    # Old code used (people_own + bare_own) which were already filtered to
    # target's own tweets, so `mentioned` only contained self-mentions.
    # SUGGEST layer always got 0 mention_hits → always "warning" on cookie
    # path (Vercel). Now correctly counts tweets by OTHERS mentioning user.
    mentioned = [
        t for t in (people_hits_raw + bare_hits_raw)
        if username in ((t.get("text") or "").lower())
        and _author_screen(t) != username
    ]

    # 2026-07-13 (KIRA): Typeahead probe — REST endpoint still works on
    # free tier (SearchTimeline GraphQL deprecated). This is our primary
    # suggestion/search visibility signal when search_available=False.
    typeahead = await x_typeahead(username)

    local_avatar = await cache_avatar(username, profile.get("avatar") or "")
    if local_avatar:
        profile["avatar"] = local_avatar
        profile["avatar_cached"] = True
        profile["avatar_ttl_sec"] = AVATAR_TTL_SEC
    else:
        profile["avatar_cached"] = False

    return {
        "profile": profile,
        "posts": posts,
        "from_own": from_own,
        "people_own": people_own,
        "bare_own": bare_own,
        # 2026-07-12 (KIRA): raw count for INDEX layer
        "bare_hits_count": len(bare_hits_raw),
        # 2026-07-12 (KIRA): search probe health — distinguish "QID expired
        # / GraphQL failed" from "search genuinely returned 0 results."
        "search_available": search_available,
        "search_err": search_err_msg,
        # 2026-07-13 (KIRA): typeahead REST probe — works even when
        # SearchTimeline GraphQL is 404. Primary signal for SUGGEST layer
        # and fallback inference for SEARCH/POST/INDEX.
        "typeahead_available": typeahead["available"],
        "typeahead_found": typeahead["found"],
        "typeahead_hits": typeahead["hits"],
        "typeahead_err": typeahead["err"],
        "mentioned": mentioned,
        "hashtag": hashtag,
        "hashtag_own": hashtag_own,
        "source": {
            "engine": "x-cookie",
            "account": "env",
            "env_auth": True,
            "posts": len(posts),
        },
    }


# ============================================================
# 8-LAYER AUDIT SYSTEM
# ============================================================
# Layers:
#   1. PROFILE — does profile exist, is it protected/suspended, basic info
#   2. SEARCH  — does from:username appear in search results
#   3. SUGGEST — does @username appear in search/typeahead (mention visibility)
#   4. QRT     — quote tweet visibility (check quote metrics on recent posts)
#   5. SPAM    — spam pattern detection (repetitive content, link spam, mention spam)
#   6. RANK    — engagement ranking (views vs followers ratio, like ratio)
#   7. POST    — recent post visibility (do posts appear, are they indexable)
#   8. INDEX   — search index presence (does username search return the account)
#
# Each layer: {name, status: "safe"|"warning"|"banned", confidence: 0-100, desc}
# ============================================================


def _layer(name: str, status: str, confidence, desc: str) -> dict:
    return {"name": name, "status": status, "confidence": _clamp(confidence), "desc": desc}


def _status_health(status: str, confidence: int) -> int:
    """Convert layer status+confidence to 0-100 health score (higher = better)."""
    if status == "safe":
        return _clamp(72 + confidence // 5, 70, 98)
    elif status == "warning":
        return _clamp(42 + confidence // 5, 40, 68)
    else:  # banned
        return _clamp(33 - confidence // 6, 5, 35)


def _spam_analysis(posts: list) -> dict:
    """Detect spam patterns: repetitive content, link spam, mention spam."""
    if not posts:
        return {"dupe_ratio": 0.0, "link_ratio": 0.0, "mention_ratio": 0.0, "desc": "no posts", "n": 0}
    texts = [(p.get("text") or "") for p in posts]
    n = len(texts)
    seen = set()
    dupes = 0
    for t in texts:
        # 2026-07-12 (KIRA): prefix 120 → 200 chars for dupe key. 120 was
        # too short — tweets sharing a common opening phrase (RT prefix,
        # "Breaking:", thread starters) but diverging later were flagged.
        key = re.sub(r"\s+", " ", t.lower().strip())[:200]
        if not key:
            continue
        if key in seen:
            dupes += 1
        seen.add(key)
    # 2026-07-12 (KIRA): link spam = 2+ distinct links per tweet, not just
    # any link. News/media accounts post 1 link per tweet (normal). Spam
    # accounts post multiple links to dodge filters. Single-link tweets
    # no longer count toward link_posts.
    link_posts = sum(
        1 for t in texts
        if len(re.findall(r"https?://\S+|t\.co/\S+", t)) >= 2
    )
    mention_posts = sum(1 for t in texts if t.startswith("@") or t.count("@") >= 3)
    dupe_ratio = dupes / max(n, 1)
    link_ratio = link_posts / max(n, 1)
    mention_ratio = mention_posts / max(n, 1)
    parts = []
    if dupes:
        parts.append(f"{dupes} dup post")
    if link_posts:
        parts.append(f"{link_posts} post dgn link")
    if mention_posts:
        parts.append(f"{mention_posts} post mention-heavy")
    desc = ", ".join(parts) if parts else "bersih"
    return {
        "dupe_ratio": dupe_ratio,
        "link_ratio": link_ratio,
        "mention_ratio": mention_ratio,
        "desc": desc,
        "n": n,
    }


def audit_8_layers(username: str, bundle: dict, sources: dict) -> dict:
    """
    Run the 8-layer audit on a data bundle (shared by agentx + cookie paths).
    Returns the full result dict: layers, overall, metrics, profile, recent_posts, probes, source, timestamp.
    """
    # --- Not found / suspended ---
    if bundle.get("not_found") or not bundle.get("profile"):
        layers = [
            _layer("PROFILE", "banned", 95, "Akun tidak ketemu / suspended di X"),
            _layer("SEARCH", "banned", 90, "Tidak bisa diuji — profil hilang"),
            _layer("SUGGEST", "banned", 85, "Username tidak resolve di typeahead"),
            _layer("QRT", "banned", 75, "Tidak ada data quote"),
            _layer("SPAM", "warning", 40, "Tidak bisa diuji — profil hilang"),
            _layer("RANK", "banned", 80, "Tidak ada data engagement"),
            _layer("POST", "banned", 90, "Tidak ada post terlihat"),
            _layer("INDEX", "banned", 88, "Akun tidak ada di search index"),
        ]
        return _assemble_result(username, layers, None, [], bundle, sources, _metrics_of([]))

    profile = bundle["profile"]
    posts = bundle.get("posts") or []
    from_own = bundle.get("from_own") or []
    people_own = bundle.get("people_own") or []
    bare_own = bundle.get("bare_own") or []
    # 2026-07-12 (KIRA): bare_hits_count = total results from bare username
    # search (before authored_by_target filter). INDEX layer needs to know
    # if ANY results came back (username is indexed), not just target's own
    # tweets in those results (which is 0 for most accounts — they don't
    # mention their own username in tweets).
    bare_hits_count = bundle.get("bare_hits_count") or len(bare_own)
    # 2026-07-12 (KIRA): search_available — did the search probe actually
    # succeed? If False, empty search results mean "we couldn't test" not
    # "the account is shadowbanned." This is the difference between a
    # genuine deindex and an expired GraphQL query ID.
    search_available = bundle.get("search_available", True)
    search_err = bundle.get("search_err") or ""
    # 2026-07-13 (KIRA): typeahead REST probe — works even when
    # SearchTimeline GraphQL is 404 (deprecated for free tier). Primary
    # signal for SUGGEST layer; fallback inference for SEARCH/POST/INDEX
    # when search_available=False.
    ta_available = bundle.get("typeahead_available", False)
    ta_found = bundle.get("typeahead_found", False)
    ta_hits = bundle.get("typeahead_hits", 0)
    ta_err = bundle.get("typeahead_err") or ""
    hashtag = bundle.get("hashtag") or None
    hashtag_own = bundle.get("hashtag_own") or []

    mentioned = bundle.get("mentioned")
    if mentioned is None:
        mentioned = list(people_own + bare_own)

    mstats = _metrics_of(posts)
    avg_views = mstats.get("avg_views") or 0
    avg_likes = mstats.get("avg_likes") or 0
    avg_quotes = mstats.get("avg_quotes") or 0
    followers = max(profile.get("followers") or 0, 1)
    # 2026-07-12 (KIRA): tiered expected_floor — mega-accounts naturally have
    # lower view:follower ratio (inactive followers, algorithmic distribution
    # limits, time zones). Flat 1% flagged Elon Musk (1.4M views/241M followers)
    # as "warning" which is absurd. Log-scaled: 30 floor for micro accounts,
    # scales sub-linearly so 100M followers → ~3K expected, not 1M.
    import math
    _log_f = math.log10(max(followers, 10))
    expected_floor = max(30, int(_log_f ** 3 * 5))
    is_protected = bool(profile.get("protected"))
    has_posts = len(posts) > 0
    has_from = len(from_own) > 0

    # --- Layer 1: PROFILE ---
    if is_protected:
        L1 = _layer("PROFILE", "warning", 60, "Akun protected — visibilitas terbatas by design")
    else:
        L1 = _layer("PROFILE", "safe", 92, "Profil ada dan publik")

    # --- Layer 2: SEARCH — from:username appears in search ---
    # 2026-07-13 (KIRA): when SearchTimeline GraphQL is 404 (deprecated),
    # fall back to typeahead REST probe. If username appears in typeahead
    # suggestions, it's NOT search banned (high correlation between
    # suggestion ban and search ban — they almost always co-occur).
    if is_protected:
        L2 = _layer("SEARCH", "warning", 50, "Protected — from: search terbatas secara normal")
    elif has_from:
        L2 = _layer("SEARCH", "safe", _clamp(80 + len(from_own) * 3, 80, 97),
                     f"from:{username} muncul di search ({len(from_own)} hit)")
    elif ta_available and ta_found:
        L2 = _layer("SEARCH", "safe", 78,
                     f"Typeahead OK ({ta_hits} suggestions, @{username} muncul) — search visibility aman")
    elif ta_available and not ta_found and has_posts:
        L2 = _layer("SEARCH", "banned", 80,
                     f"Post ada ({len(posts)}) tapi @{username} tidak muncul di typeahead — search ban")
    elif not search_available and not ta_available:
        L2 = _layer("SEARCH", "warning", 35, f"Search + typeahead probe gagal — tidak bisa konfirmasi: {search_err[:50]}")
    elif not has_posts and not has_from:
        L2 = _layer("SEARCH", "warning", 45, "Tidak ada post publik terbaru untuk diuji di search")
    elif has_posts:
        L2 = _layer("SEARCH", "banned", _clamp(82 - len(posts) * 2, 72, 88),
                     f"Post ada ({len(posts)}) tapi from:{username} kosong — search suggestion ban")
    else:
        L2 = _layer("SEARCH", "warning", 50, "Sampel tipis — tidak bisa konfirmasi")

    # --- Layer 3: SUGGEST — @username mention visibility / typeahead ---
    # 2026-07-13 (KIRA): typeahead REST is now the PRIMARY signal for this
    # layer. SearchTimeline GraphQL is 404 (deprecated), but typeahead
    # still works. If username appears in typeahead suggestions = NOT
    # suggestion banned. This is the same method XGrind uses.
    mention_hits = len([m for m in mentioned if _author_screen(m) != username])
    if ta_available and ta_found:
        L3 = _layer("SUGGEST", "safe", _clamp(80 + min(ta_hits * 2, 15), 80, 96),
                     f"@{username} muncul di typeahead ({ta_hits} suggestions) — suggestion ban: TIDAK")
    elif mention_hits >= 1:
        L3 = _layer("SUGGEST", "safe", _clamp(78 + mention_hits * 3, 78, 95),
                     f"@{username} muncul di mention search ({mention_hits} hit)")
    elif has_from:
        L3 = _layer("SUGGEST", "safe", 72, "Username resolve lewat search observer")
    elif is_protected:
        L3 = _layer("SUGGEST", "warning", 50, "Protected — mention search terbatas")
    elif ta_available and not ta_found and has_posts:
        L3 = _layer("SUGGEST", "banned", 82,
                     f"@{username} tidak muncul di typeahead ({ta_hits} suggestions) — suggestion ban")
    elif not search_available and not ta_available:
        L3 = _layer("SUGGEST", "warning", 35, "Search + typeahead probe gagal — tidak bisa konfirmasi mention visibility")
    elif has_posts:
        L3 = _layer("SUGGEST", "warning", 55, "Profil ada tapi @mention tidak muncul di search surface")
    else:
        L3 = _layer("SUGGEST", "warning", 45, "Sampel tipis — tidak bisa konfirmasi typeahead")

    # --- Layer 4: QRT — quote tweet visibility ---
    if not has_posts:
        L4 = _layer("QRT", "warning", 40, "Tidak ada sampel post untuk cek quote metrics")
    elif avg_quotes > 0:
        L4 = _layer("QRT", "safe", _clamp(75 + min(avg_quotes * 5, 20), 75, 95),
                     f"Quote metrics normal (avg {avg_quotes:.1f} quote/post)")
    # 2026-07-12 (KIRA): demoted "banned" → "warning". 0 quotes with 500+
    # views is normal for most accounts — quoting is a rare interaction
    # (only ~1-3% of tweets get quoted). Old logic called this "banned"
    # with 72 confidence, producing false positives on medium accounts.
    # Also removed `not has_from` gate — quote visibility is independent
    # of search visibility.
    elif avg_views > 500 and not has_from:
        L4 = _layer("QRT", "warning", 52, "Quote kosong + search lemah — mungkin partial quote limit")
    elif avg_views > 5000:
        L4 = _layer("QRT", "warning", 55, "Quote kosong meski views lumayan — mungkin partial limit")
    else:
        L4 = _layer("QRT", "safe", 70, "Quote visibility terlihat normal (views rendah, wajar quote kecil)")

    # --- Layer 5: SPAM — spam pattern detection ---
    spam = _spam_analysis(posts)
    if not has_posts:
        L5 = _layer("SPAM", "warning", 35, "Tidak ada post untuk analisis spam")
    elif spam["dupe_ratio"] >= 0.5 or (spam["link_ratio"] >= 0.5 and spam["mention_ratio"] >= 0.5):
        L5 = _layer("SPAM", "banned", _clamp(70 + int(spam["dupe_ratio"] * 20), 70, 90),
                     f"Pola spam terdeteksi: {spam['desc']}")
    # 2026-07-12 (KIRA): link_ratio threshold 0.6 → 0.4. Now that link_posts
    # only counts 2+-link tweets, a 40% rate of multi-link tweets is a
    # genuine spam signal. Old 0.6 with single-link counting flagged CNN.
    elif spam["dupe_ratio"] >= 0.3 or spam["link_ratio"] >= 0.4 or spam["mention_ratio"] >= 0.4:
        L5 = _layer("SPAM", "warning", _clamp(55 + int(spam["dupe_ratio"] * 15), 55, 70),
                     f"Sinyal spam moderat: {spam['desc']}")
    else:
        L5 = _layer("SPAM", "safe", 85, "Tidak ada pola spam yang menonjol")

    # --- Layer 6: RANK — engagement ranking ---
    like_ratio = avg_likes / max(avg_views, 1)
    view_follower_ratio = avg_views / followers
    if not has_posts:
        L6 = _layer("RANK", "warning", 40, "Tidak ada post untuk ukur engagement")
    # 2026-07-12 (KIRA): removed `and not has_from` gate — views below floor
    # is a rank signal regardless of search visibility. has_from was True for
    # ~all active accounts, so this "banned" path NEVER fired.
    elif avg_views < expected_floor:
        severity = (expected_floor - avg_views) / max(expected_floor, 1)
        if severity > 0.7:
            L6 = _layer("RANK", "banned",
                         _clamp(70 + int(severity * 18), 70, 88),
                         f"Views sangat rendah ({int(avg_views)}) vs expected {int(expected_floor)} (followers {followers}) — rank ditekan")
        else:
            L6 = _layer("RANK", "warning",
                         _clamp(55 + int(avg_views / max(expected_floor, 1) * 10), 50, 68),
                         f"Views rendah ({int(avg_views)}) vs expected {int(expected_floor)} — mungkin partial limit")
    # 2026-07-12 (KIRA): removed `avg_views > 1000` gate — low like_ratio is
    # a suppression signal at ANY view count. An account with 200 avg views
    # and 0.1% like ratio has terrible engagement but old logic said "safe".
    elif like_ratio < 0.005:
        L6 = _layer("RANK", "warning", 58,
                     f"Like ratio sangat rendah ({like_ratio:.4f}) — engagement lemah")
    else:
        L6 = _layer("RANK", "safe", _clamp(78 + min(view_follower_ratio * 10, 18), 75, 96),
                     f"Engagement wajar (avg views {int(avg_views)}, like ratio {like_ratio:.3f})")

    # --- Layer 7: POST — recent post visibility / indexability ---
    # 2026-07-13 (KIRA): when search_available=False, use typeahead as
    # fallback inference. If typeahead found = posts are likely indexed
    # (suggestion visibility and post indexability are correlated).
    if not has_posts:
        L7 = _layer("POST", "warning", 45, "Tidak ada post terbaru terlihat")
    elif has_from:
        L7 = _layer("POST", "safe", _clamp(80 + len(from_own) * 2, 80, 96),
                     f"Post terlihat & terindeks ({len(posts)} post, {len(from_own)} di search)")
    elif is_protected:
        L7 = _layer("POST", "warning", 50, "Protected — post visibility terbatas")
    elif ta_available and ta_found:
        L7 = _layer("POST", "safe", 76,
                     f"Post ada ({len(posts)}), typeahead OK — post visibility aman (inferred)")
    elif ta_available and not ta_found:
        L7 = _layer("POST", "banned", _clamp(72 + min(len(posts) * 2, 15), 72, 85),
                     f"Post ada ({len(posts)}) tapi typeahead kosong — post tidak terindeks (inferred)")
    elif not search_available:
        L7 = _layer("POST", "warning", 40, f"Post ada ({len(posts)}) tapi search probe gagal — tidak bisa konfirmasi index")
    else:
        L7 = _layer("POST", "banned", _clamp(72 + min(len(posts) * 2, 15), 72, 85),
                     f"Post ada ({len(posts)}) tapi tidak muncul di search — ghost/index ban")

    # --- Layer 8: INDEX — search index presence ---
    # 2026-07-13 (KIRA): when SearchTimeline is 404 (bare_hits_count=0
    # because search failed, not because username is deindexed), use
    # typeahead as fallback. If typeahead found = username IS in search
    # index (typeahead pulls from the same index).
    if bare_hits_count >= 1:
        L8 = _layer("INDEX", "safe", _clamp(78 + min(bare_hits_count * 3, 17), 78, 95),
                     f"Username muncul di search index ({bare_hits_count} hit)")
    elif is_protected:
        L8 = _layer("INDEX", "warning", 50, "Protected — index terbatas")
    elif ta_available and ta_found:
        L8 = _layer("INDEX", "safe", 77,
                     f"@{username} muncul di typeahead — search index OK (inferred)")
    elif ta_available and not ta_found and has_posts:
        L8 = _layer("INDEX", "banned", _clamp(70 + min(len(posts) * 2, 15), 70, 85),
                     f"Profil ada tapi @{username} tidak di typeahead — deindex (inferred)")
    elif not search_available and not ta_available:
        L8 = _layer("INDEX", "warning", 35, "Search + typeahead probe gagal — tidak bisa konfirmasi index presence")
    elif has_from:
        L8 = _layer("INDEX", "warning", 60, "from: search OK tapi username search kosong — mungkin partial deindex")
    elif has_posts:
        L8 = _layer("INDEX", "banned", _clamp(70 + min(len(posts) * 2, 15), 70, 85),
                     "Profil ada tapi tidak muncul di search index — deindex")
    else:
        L8 = _layer("INDEX", "warning", 45, "Tidak bisa konfirmasi index presence")

    layers = [L1, L2, L3, L4, L5, L6, L7, L8]
    return _assemble_result(username, layers, profile, posts, bundle, sources, mstats)


def _health_score(layers: list) -> int:
    """Aggregate 8-layer status to 0-100 score. 8 layers tetap ada, ini bonus."""
    if not layers:
        return 0
    total = 0
    for l in layers:
        s = l.get("status", "warning")
        c = l.get("confidence", 50) / 100.0
        if s == "safe":
            total += int(100 * c)
        elif s == "warning":
            total += int(50 * c)
        else:  # banned
            total += int(5 * c)
    return min(100, max(0, total // len(layers)))


def _compute_analytics(posts: list, profile: dict) -> dict:
    """Compute engagement metrics, content type, best time, schedule from posts."""
    if not posts:
        return {}

    from datetime import datetime
    import calendar

    total_likes = total_replies = total_reposts = total_bookmarks = total_views = total_quotes = 0
    content_types = {"text": 0, "image": 0, "video": 0, "link": 0, "retweet": 0}
    hour_engagement = {}  # hour -> total engagement
    day_hour_count = {}   # (day, hour) -> tweet count
    day_names = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]

    for p in posts:
        mm = p.get("metrics") or {}
        total_likes += int(mm.get("likes") or 0)
        total_replies += int(mm.get("replies") or 0)
        total_reposts += int(mm.get("retweets") or 0)
        total_bookmarks += int(mm.get("bookmarks") or 0)
        total_views += int(mm.get("views") or 0)
        total_quotes += int(mm.get("quotes") or 0)

        mt = p.get("mediaType") or "text"
        content_types[mt] = content_types.get(mt, 0) + 1

        # Parse timestamp
        ca = p.get("createdAt") or ""
        if ca:
            try:
                dt = datetime.strptime(ca, "%a %b %d %H:%M:%S %z %Y")
                h = dt.hour
                dow = dt.weekday()  # 0=Monday
                engagement = int(mm.get("likes") or 0) + int(mm.get("replies") or 0) + int(mm.get("retweets") or 0) + int(mm.get("bookmarks") or 0)
                hour_engagement[h] = hour_engagement.get(h, 0) + engagement
                day_hour_count[(dow, h)] = day_hour_count.get((dow, h), 0) + 1
            except Exception:
                pass

    n = len(posts)
    total_engagement = total_likes + total_replies + total_reposts + total_bookmarks
    engagement_rate = round((total_engagement / total_views * 100), 2) if total_views > 0 else 0
    avg_views = total_views // n if n > 0 else 0

    # Best time to post: sort hours by avg engagement per tweet
    best_time = []
    for h, eng in sorted(hour_engagement.items(), key=lambda x: x[1], reverse=True):
        best_time.append({"hour": h, "engagement": eng})
    best_time = best_time[:5]  # top 5 hours

    # Schedule heatmap: 7 days x 24 hours
    schedule = []
    for dow in range(7):
        row = []
        for h in range(24):
            row.append(day_hour_count.get((dow, h), 0))
        schedule.append({"day": day_names[dow], "hours": row})

    # Verified follower estimate from profile
    verified_pct = 0
    if profile and profile.get("followers"):
        # Rough estimate: blue verified typically 5-15% for mid accounts
        verified_pct = min(15, max(1, (profile.get("verified", 0) or 0) * 100 // max(profile["followers"], 1)))

    return {
        "tweet_count": n,
        "total_likes": total_likes,
        "total_replies": total_replies,
        "total_reposts": total_reposts,
        "total_bookmarks": total_bookmarks,
        "total_quotes": total_quotes,
        "total_views": total_views,
        "total_engagement": total_engagement,
        "avg_views": avg_views,
        "engagement_rate": engagement_rate,
        "content_types": content_types,
        "best_time": best_time,
        "schedule": schedule,
    }


def _assemble_result(username: str, layers: list, profile, posts: list,
                     bundle: dict, sources: dict, mstats: dict) -> dict:
    """Assemble final result dict from 8 layers + raw data."""
    banned_count = sum(1 for l in layers if l["status"] == "banned")
    warn_count = sum(1 for l in layers if l["status"] == "warning")
    if banned_count >= 3:
        overall = "banned"
    elif banned_count >= 1 or warn_count >= 3:
        overall = "warning"
    else:
        overall = "safe"

    # Map layers to legacy metrics dict (backward compat for DB + history endpoint)
    by_name = {l["name"]: l for l in layers}
    metrics = {
        "search": _status_health(by_name.get("SEARCH", {}).get("status", "warning"),
                                  by_name.get("SEARCH", {}).get("confidence", 50)),
        "reply": _status_health(by_name.get("SUGGEST", {}).get("status", "warning"),
                                 by_name.get("SUGGEST", {}).get("confidence", 50)),
        "quote": _status_health(by_name.get("QRT", {}).get("status", "warning"),
                                 by_name.get("QRT", {}).get("confidence", 50)),
        "engagement": _status_health(by_name.get("RANK", {}).get("status", "warning"),
                                      by_name.get("RANK", {}).get("confidence", 50)),
    }

    avg_views = mstats.get("avg_views") or 0

    # Recent posts summary for UI
    recent = []
    for p in (posts or [])[:5]:
        mm = p.get("metrics") or {}
        recent.append({
            "id": str(p.get("id") or ""),
            "text": (p.get("text") or "")[:180],
            "likes": int(mm.get("likes") or 0),
            "views": int(mm.get("views") or 0),
            "replies": int(mm.get("replies") or 0),
            "createdAt": p.get("createdAt") or "",
        })

    return {
        "username": username,
        "overall": overall,
        "health_score": _health_score(layers),
        "analytics": _compute_analytics(posts or [], profile),
        "metrics": metrics,
        "layers": layers,
        "tests": layers,  # backward compat alias for old frontend
        "profile": profile,
        "recent_posts": recent,
        "probes": {
            "posts_count": len(posts or []),
            "from_search_hits": len(bundle.get("from_own") or []),
            # 2026-07-12 (KIRA): count mentions BY OTHERS, not target's own
            # tweets. Old formula counted people_own+bare_own (target's own
            # tweets in @username/bare search) which was always ~0 for
            # normal accounts, contradicting the SUGGEST layer's hit count.
            "mention_search_hits": len([
                m for m in (bundle.get("mentioned") or [])
                if _author_screen(m) != username
            ]),
            "hashtag": bundle.get("hashtag"),
            "hashtag_hits": len(bundle.get("hashtag_own") or []),
            "avg_views": int(avg_views),
        },
        "source": sources,
        "timestamp": datetime.now().isoformat(),
    }


async def check_with_agentx(username: str) -> dict:
    """
    Real-ish visibility check via AgentX + cookie GraphQL fallback.
    Runs the 8-layer audit on live X data from the observer account.
    """
    username = username.lower().replace("@", "").strip()
    sources = {"engine": "agentx", "account": AGENTX_ACCOUNT}

    # Vercel / no-binary path: use cookie GraphQL directly (env TWITTER_*)
    if not Path(AGENTX_BIN).exists():
        bundle = await fetch_via_cookies(username)
        if bundle is None:
            raise RuntimeError("AgentX binary missing and TWITTER_AUTH_TOKEN/CT0 not set")
        return audit_8_layers(username, bundle, bundle.get("source") or sources)

    # 1) Profile
    user_env = await run_agentx("user", username)
    if not user_env.get("ok"):
        err = (user_env.get("error") or {})
        code = err.get("code") or "api_error"
        msg = err.get("message") or "failed to fetch user"
        # Only treat real missing users as banned.
        if code in ("not_found", "user_not_found"):
            not_found_bundle = {
                "not_found": True,
                "profile": None,
                "posts": [],
                "from_own": [],
                "people_own": [],
                "bare_own": [],
                "mentioned": [],
                "hashtag": None,
                "hashtag_own": [],
                "source": sources,
            }
            result = audit_8_layers(username, not_found_bundle, sources)
            result["error"] = msg
            return result
        # auth / network / missing binary → try cookie HTTP fallback
        if code in ("missing_binary", "spawn_error", "empty_output", "timeout", "api_error", "not_authenticated"):
            cookie_bundle = await fetch_via_cookies(username)
            if cookie_bundle is not None:
                return audit_8_layers(username, cookie_bundle, cookie_bundle.get("source") or sources)
        raise RuntimeError(f"live X fetch failed: {code}: {msg}")

    user = user_env.get("data") or {}
    profile = build_profile(user)
    sources["rateLimit"] = user_env.get("rateLimit")

    # 2) Posts + search probes + avatar cache in parallel
    posts_task = run_agentx("posts", username, "-n", "12")
    from_task = run_agentx("search", "--type", "Latest", f"from:{username}", "-n", "10")
    people_task = run_agentx("search", "--type", "Latest", f"@{username}", "-n", "10")
    bare_task = run_agentx("search", "--type", "Latest", username, "-n", "10")
    avatar_task = cache_avatar(username, profile.get("avatar") or "")

    posts_env, from_env, people_env, bare_env, local_avatar = await asyncio.gather(
        posts_task, from_task, people_task, bare_task, avatar_task
    )

    if local_avatar:
        profile["avatar"] = local_avatar
        profile["avatar_cached"] = True
        profile["avatar_ttl_sec"] = AVATAR_TTL_SEC
    else:
        profile["avatar_cached"] = False

    posts = posts_env.get("data") if posts_env.get("ok") else []
    if not isinstance(posts, list):
        posts = []

    from_hits = from_env.get("data") if from_env.get("ok") else []
    people_hits = people_env.get("data") if people_env.get("ok") else []
    bare_hits = bare_env.get("data") if bare_env.get("ok") else []
    if not isinstance(from_hits, list):
        from_hits = []
    if not isinstance(people_hits, list):
        people_hits = []
    if not isinstance(bare_hits, list):
        bare_hits = []

    # Count how many search hits are authored by the target
    def authored_by_target(items):
        return [i for i in items if _author_screen(i) == username]

    from_own = authored_by_target(from_hits)
    people_own = authored_by_target(people_hits)
    bare_own = authored_by_target(bare_hits)

    # Mentions of the user by others (typeahead/search visibility proxy)
    mentioned = [
        i for i in (people_hits + bare_hits)
        if username in ((i.get("text") or "").lower()) or _author_screen(i) == username
    ]

    # Hashtag probe: find a hashtag in recent posts, search it
    hashtag = None
    for p in posts:
        text = p.get("text") or ""
        for token in text.split():
            if token.startswith("#") and len(token) > 2:
                hashtag = token
                break
        if hashtag:
            break

    hashtag_own = []
    if hashtag:
        tag_env = await run_agentx("search", "--type", "Latest", hashtag, "-n", "15")
        tag_hits = tag_env.get("data") if tag_env.get("ok") else []
        if not isinstance(tag_hits, list):
            tag_hits = []
        hashtag_own = authored_by_target(tag_hits)

    # 2026-07-13 (KIRA): Typeahead REST probe — works even when
    # SearchTimeline GraphQL is 404. Also add to AgentX path for parity.
    typeahead = await x_typeahead(username)

    # Build bundle and run 8-layer audit
    bundle = {
        "profile": profile,
        "posts": posts,
        "from_own": from_own,
        "people_own": people_own,
        "bare_own": bare_own,
        # 2026-07-12 (KIRA): raw count for INDEX layer — total bare username
        # search results (by anyone), not just target's own tweets.
        "bare_hits_count": len(bare_hits),
        # 2026-07-12 (KIRA): AgentX path — search is available unless all
        # search probes failed. Check if any probe returned ok.
        "search_available": from_env.get("ok") or people_env.get("ok") or bare_env.get("ok"),
        "search_err": "",
        # 2026-07-13 (KIRA): typeahead REST probe
        "typeahead_available": typeahead["available"],
        "typeahead_found": typeahead["found"],
        "typeahead_hits": typeahead["hits"],
        "typeahead_err": typeahead["err"],
        "mentioned": mentioned,
        "hashtag": hashtag,
        "hashtag_own": hashtag_own,
        "source": sources,
    }
    return audit_8_layers(username, bundle, sources)


@app.post("/api/check")
async def api_check(request: CheckRequest):
    username = request.username.lower().replace("@", "").strip()
    if not username:
        return JSONResponse({"error": "username required"}, status_code=400)

    try:
        result = await check_with_agentx(username)
    except Exception as e:
        return JSONResponse(
            {
                "username": username,
                "overall": "warning",
                "metrics": {"search": 0, "reply": 0, "quote": 0, "engagement": 0},
                "layers": [],
                "tests": [],
                "profile": None,
                "error": f"Yah capybara-nya bingung nih: {e}",
                "timestamp": datetime.now().isoformat(),
            },
            status_code=502,
        )

    # Extract avatar_url for /api/recent
    avatar_url = ""
    if result.get("profile"):
        avatar_url = result["profile"].get("avatar") or ""

    # Persist to Supabase (shared, permanent history — survives cold starts)
    await sb_insert_scan(
        {
            "username": username,
            "overall": result["overall"],
            "search_vis": result["metrics"]["search"],
            "reply_rate": result["metrics"]["reply"],
            "quote_rate": result["metrics"]["quote"],
            "engagement": result["metrics"]["engagement"],
            "layers": result.get("layers") or [],
            "profile": result.get("profile") or {},
            "avatar_url": avatar_url,
        }
    )

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """INSERT INTO checks (username, overall, search_vis, reply_rate, quote_rate, engagement, tests, avatar_url)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                result["overall"],
                result["metrics"]["search"],
                result["metrics"]["reply"],
                result["metrics"]["quote"],
                result["metrics"]["engagement"],
                json.dumps(result["layers"]),
                avatar_url,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # 2026-07-13 (KIRA): embed recovery checklist in scan result
    result["recovery"] = _build_recovery(result.get("layers") or [])

    return JSONResponse(result)


@app.get("/api/history")
async def get_history(limit: int = 40):
    # Prefer Supabase (shared history visible to all users)
    rows_sb = await sb_history(limit)
    if rows_sb:
        history = []
        for row in rows_sb:
            uname = row.get("username") or ""
            avatar_url = row.get("avatar_url") or ""
            if not avatar_url and uname:
                avatar_url = f"/api/avatar/{_safe_username(uname)}"
            history.append(
                {
                    "id": row.get("id"),
                    "username": uname,
                    "overall": row.get("overall") or "warning",
                    "avatar_url": avatar_url,
                    "metrics": {
                        "search": row.get("search_vis") or 0,
                        "reply": row.get("reply_rate") or 0,
                        "quote": row.get("quote_rate") or 0,
                        "engagement": row.get("engagement") or 0,
                    },
                    "timestamp": row.get("created_at") or "",
                }
            )
        return history

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM checks ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append(
            {
                "id": row[0],
                "username": row[1],
                "overall": row[2],
                "metrics": {"search": row[3], "reply": row[4], "quote": row[5], "engagement": row[6]},
                "timestamp": row[8],
            }
        )
    return history


@app.get("/api/recent")
async def get_recent():
    """Return last 5 checked accounts: {username, overall, avatar_url, timestamp}."""
    # Prefer Supabase (shared + persistent); fall back to local SQLite.
    rows_sb = await sb_recent(5)
    if rows_sb:
        recent = []
        for row in rows_sb:
            uname = row.get("username") or ""
            avatar_url = row.get("avatar_url") or ""
            if not avatar_url and uname:
                avatar_url = f"/api/avatar/{_safe_username(uname)}"
            recent.append({
                "username": uname,
                "overall": row.get("overall") or "warning",
                "avatar_url": avatar_url,
                "timestamp": row.get("created_at") or "",
            })
        return recent

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT username, overall, avatar_url, timestamp "
        "FROM checks ORDER BY timestamp DESC LIMIT 5"
    )
    rows = c.fetchall()
    conn.close()

    recent = []
    for row in rows:
        uname = row[0] or ""
        avatar_url = row[2] or ""
        # If avatar cache expired, construct a fresh path (serve_avatar will 404 if gone)
        if not avatar_url and uname:
            avatar_url = f"/api/avatar/{_safe_username(uname)}"
        recent.append({
            "username": uname,
            "overall": row[1] or "warning",
            "avatar_url": avatar_url,
            "timestamp": row[3] or "",
        })
    return recent


@app.get("/api/history-detail/{scan_id}")
async def history_detail(scan_id: int):
    """Full stored scan (layers + profile) so other users can view someone's analysis."""
    row = await sb_scan_detail(scan_id)
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "overall": row.get("overall") or "warning",
        "metrics": {
            "search": row.get("search_vis") or 0,
            "reply": row.get("reply_rate") or 0,
            "quote": row.get("quote_rate") or 0,
            "engagement": row.get("engagement") or 0,
        },
        "layers": row.get("layers") or [],
        "profile": row.get("profile") or {},
        "timestamp": row.get("created_at") or "",
        "from_history": True,
    }


# ============================================================
# RECOVERY CHECKLIST — actionable steps based on layer status
# ============================================================

_RECOVERY_RULES = {
    "SEARCH_banned": {
        "priority": "critical",
        "title": "Search ban terdeteksi",
        "steps": [
            "Hentikan semua mass reply/mass mention selama 3-7 hari",
            "Post konten original (bukan RT/quote) minimal 1x/hari",
            "Jangan gunakan hashtag berulang di setiap tweet",
            "Tunggu reindex 3-7 hari, cek lagi dengan KeGhost",
        ],
    },
    "SEARCH_warning": {
        "priority": "medium",
        "title": "Search visibility lemah",
        "steps": [
            "Kurangi frekuensi reply ke akun besar (terlihat seperti bot)",
            "Post konten original dengan engagement natural",
            "Hindari tweet dengan link-only tanpa konteks",
        ],
    },
    "SUGGEST_banned": {
        "priority": "critical",
        "title": "Suggestion ban terdeteksi",
        "steps": [
            "Username tidak muncul di typeahead — sinyal kuat shadowban",
            "Hapus tweet yang berulang/duplikat (spam pattern)",
            "Jangan mass mention 5+ orang dalam 1 tweet",
            "Hentikan aktivitas bot-like 7-14 hari untuk reset algoritma",
        ],
    },
    "SUGGEST_warning": {
        "priority": "medium",
        "title": "Suggestion visibility lemah",
        "steps": [
            "Bangun engagement natural: reply bermakna, bukan sekedar emoji",
            "Hindari follow/unfollow massal",
            "Post di jam aktif followers (cek analytics X)",
        ],
    },
    "QRT_warning": {
        "priority": "low",
        "title": "Quote visibility terbatas",
        "steps": [
            "Kurangi quote tweet, buat original content lebih banyak",
            "Jika quote, tambahkan opini/konteks bukan sekedar repost",
        ],
    },
    "SPAM_banned": {
        "priority": "critical",
        "title": "Pola spam terdeteksi",
        "steps": [
            "Hapus tweet duplikat/berulang secara manual",
            "Kurangi tweet dengan multiple link (2+ link per tweet)",
            "Beri jeda 30+ menit antar tweet, jangan burst post",
            "Hindari mention 3+ orang dalam 1 tweet",
        ],
    },
    "SPAM_warning": {
        "priority": "medium",
        "title": "Sinyal spam moderat",
        "steps": [
            "Variasi konten — jangan ulang template tweet",
            "Kurangi tweet link-only, tambah konteks/preview",
        ],
    },
    "RANK_banned": {
        "priority": "high",
        "title": "Engagement ditekan algoritma",
        "steps": [
            "Views sangat rendah vs followers — algoritma sedang limit reach",
            "Post konten viral-potential: thread, image, video",
            "Engage dengan akun lebih besar dari kamu (reply bermakna)",
            "Hindari tweet kontroversial yang trigger rate limit",
        ],
    },
    "RANK_warning": {
        "priority": "low",
        "title": "Engagement lemah",
        "steps": [
            "Like ratio rendah — konten kurang engaging",
            "Coba post di jam prime time (19:00-22:00 WIB)",
            "Gunakan image/video untuk boost engagement",
        ],
    },
    "POST_banned": {
        "priority": "critical",
        "title": "Post tidak terindeks (ghost ban)",
        "steps": [
            "Post ada tapi tidak muncul di search — ghost ban aktif",
            "Hentikan semua aktivitas automated 7-14 hari",
            "Hapus tweet yang mungkin trigger spam filter",
            "Post original content dan tunggu reindex",
        ],
    },
    "POST_warning": {
        "priority": "low",
        "title": "Post visibility terbatas",
        "steps": [
            "Beberapa post mungkin tidak terindeks penuh",
            "Pastikan tweet tidak protected/private",
            "Post dengan keyword yang searchable",
        ],
    },
    "INDEX_banned": {
        "priority": "critical",
        "title": "Deindex dari search (index ban)",
        "steps": [
            "Username tidak muncul di search index — deindex total",
            "Hentikan mass activity 14 hari untuk reset",
            "Post original content 1-2x/hari secara natural",
            "Appeal ke X Support jika tidak recover setelah 14 hari",
        ],
    },
    "INDEX_warning": {
        "priority": "low",
        "title": "Index presence tidak konfirmable",
        "steps": [
            "Tunggu 24-48 jam lalu scan ulang",
            "Post tweet dengan hashtag trending untuk test index",
        ],
    },
}


def _build_recovery(layers: list) -> list:
    """Generate recovery checklist from layer statuses."""
    out = []
    seen_keys = set()
    for l in layers:
        name = l.get("name") or ""
        status = l.get("status") or ""
        if status == "safe":
            continue
        key = f"{name}_{status}"
        rule = _RECOVERY_RULES.get(key)
        if not rule or key in seen_keys:
            continue
        seen_keys.add(key)
        out.append({
            "layer": name,
            "status": status,
            "priority": rule["priority"],
            "title": rule["title"],
            "steps": rule["steps"],
        })
    # Sort by priority: critical > high > medium > low
    _prio = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda x: _prio.get(x["priority"], 9))
    return out


@app.get("/api/scan-history/{username}")
async def scan_history(username: str):
    """Timeline of all past scans for a username — for historical tracking."""
    uname = _safe_username(username)
    if not uname:
        return JSONResponse({"error": "invalid username"}, status_code=400)
    rows = await sb_user_history(uname, limit=20)
    if not rows:
        return {"username": uname, "scans": [], "trend": "unknown", "count": 0}
    # Build timeline entries
    scans = []
    for row in rows:
        scans.append({
            "id": row.get("id"),
            "overall": row.get("overall") or "warning",
            "metrics": {
                "search": row.get("search_vis") or 0,
                "reply": row.get("reply_rate") or 0,
                "quote": row.get("quote_rate") or 0,
                "engagement": row.get("engagement") or 0,
            },
            "layers": row.get("layers") or [],
            "timestamp": row.get("created_at") or "",
        })
    # Trend detection: compare last vs first scan
    _score = {"safe": 2, "warning": 1, "banned": 0}
    first = _score.get(scans[0]["overall"], 1)
    last = _score.get(scans[-1]["overall"], 1)
    if last > first:
        trend = "improving"
    elif last < first:
        trend = "degrading"
    else:
        trend = "stable"
    return {
        "username": uname,
        "scans": scans,
        "trend": trend,
        "count": len(scans),
        "first_scan": scans[0]["timestamp"] if scans else "",
        "last_scan": scans[-1]["timestamp"] if scans else "",
    }


# ============================================================
# NON-FOLLOWERS — who doesn't follow back the target
# ============================================================

# In-memory cache: username -> {following, followers_ids, cursors, meta}
# TTL 30 min. Each click fetches 1 batch (200 following + 200 followers),
# computes non-followers incrementally, returns next 5.
NF_CACHE: dict = {}
NF_TTL_SEC = 1800


def _nf_expired(entry: dict) -> bool:
    return time.time() - entry.get("_ts", 0) > NF_TTL_SEC


async def _fetch_following_graphql(user_id: str, cursor: str = "") -> dict:
    """Fetch one page of following via GraphQL (REST friends/list.json is deprecated).
    Returns {users: [{id, screen_name, name, followers, verified, avatar}], next_cursor, error}.
    """
    headers = _cookie_headers()
    if not headers:
        return {"users": [], "next_cursor": "", "error": "no cookies"}
    qid = X_QID.get("Following")
    if not qid:
        return {"users": [], "next_cursor": "", "error": "no Following QID"}
    features = json.dumps(X_FEATURES, separators=(",", ":"))
    variables = json.dumps(
        {"userId": user_id, "count": 100, "cursor": cursor, "includePromotedContent": False},
        separators=(",", ":"),
    )
    import urllib.parse
    qs = urllib.parse.urlencode({"variables": variables, "features": features})
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(
                f"https://x.com/i/api/graphql/{qid}/Following?{qs}",
                headers=headers,
            )
        if r.status_code != 200:
            return {"users": [], "next_cursor": "", "error": f"HTTP {r.status_code}"}
        d = r.json()
        timeline = (
            d.get("data", {}).get("user", {}).get("result", {})
            .get("timeline", {}).get("timeline", {})
        )
        instructions = timeline.get("instructions", [])
        entries = []
        for inst in instructions:
            entries.extend(inst.get("entries", []))
        # Extract users + find bottom cursor
        users = []
        next_cursor = ""
        for e in entries:
            # User entries have entryId starting with "user-"
            if "user-" in (e.get("entryId") or ""):
                result = (
                    e.get("content", {}).get("itemContent", {})
                    .get("user_results", {}).get("result", {})
                )
                core = result.get("core") or {}
                legacy = result.get("legacy") or {}
                uid = str(result.get("rest_id") or "")
                sn = core.get("screen_name") or legacy.get("screen_name") or ""
                if sn and uid:
                    users.append({
                        "id": uid,
                        "screen_name": sn,
                        "name": core.get("name") or legacy.get("name") or "",
                        "followers": legacy.get("followers_count") or 0,
                        "verified": result.get("is_blue_verified") or legacy.get("verified") or False,
                        "avatar": (legacy.get("profile_image_url_https") or "").replace("_normal", "_bigger"),
                    })
            # Cursor entries have entryId starting with "cursor-bottom-"
            if "cursor-bottom-" in (e.get("entryId") or ""):
                content = e.get("content", {})
                # Cursor value is in content.value or content.itemContent.value
                next_cursor = content.get("value") or ""
                if not next_cursor:
                    ic = content.get("itemContent", {})
                    next_cursor = ic.get("value") or ""
        return {"users": users, "next_cursor": next_cursor, "error": ""}
    except Exception as e:
        return {"users": [], "next_cursor": "", "error": str(e)[:80]}


async def _fetch_rest_list(endpoint: str, screen_name: str, cursor: str = "", count: int = 100) -> dict:
    """Fetch one page of friends/list.json or followers/list.json via REST."""
    headers = _cookie_headers()
    if not headers:
        return {"users": [], "next_cursor": "", "error": "no cookies"}
    params = {
        "screen_name": screen_name,
        "count": count,
        "skip_status": True,
        "include_user_entities": False,
    }
    if cursor and cursor != "0":
        params["cursor"] = cursor
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(
                f"https://x.com/i/api/1.1/{endpoint}",
                params=params, headers=headers,
            )
        if r.status_code != 200:
            return {"users": [], "next_cursor": "", "error": f"HTTP {r.status_code}"}
        data = r.json()
        users = data.get("users") or []
        nc = str(data.get("next_cursor_str") or data.get("next_cursor") or "")
        return {"users": users, "next_cursor": nc, "error": ""}
    except Exception as e:
        return {"users": [], "next_cursor": "", "error": str(e)[:80]}


@app.get("/api/non-followers/{username}")
async def non_followers(username: str, batch: int = 0):
    """Fetch non-followers (people target follows but don't follow back).

    Incremental: each call fetches 1 batch of following + followers (200 each),
    accumulates in cache, returns next 5 non-followers + progress estimate.
    batch=0 starts fresh. Subsequent batches continue from cursor.
    """
    uname = _safe_username(username)
    if not uname:
        return JSONResponse({"error": "invalid username"}, status_code=400)

    now = time.time()

    # Get or create cache entry
    if batch == 0 or uname not in NF_CACHE or _nf_expired(NF_CACHE[uname]):
        NF_CACHE[uname] = {
            "user_id": "",
            "following": [],
            "followers_ids": set(),
            "f_cursor": "",
            "fo_cursor": "",
            "f_done": False,
            "fo_done": False,
            "f_count": 0,
            "fo_count": 0,
            "f_total": 0,
            "fo_total": 0,
            "batches_done": 0,
            "_ts": now,
            "served": 0,
        }

    entry = NF_CACHE[uname]

    # First call: get profile for totals + user_id
    if not entry["user_id"]:
        features = json.dumps(X_FEATURES, separators=(",", ":"))
        import urllib.parse
        v = json.dumps({"screen_name": uname, "withSafetyModeUserGreeting": True}, separators=(",", ":"))
        qs = urllib.parse.urlencode({"variables": v, "features": features})
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                r = await client.get(
                    f"https://x.com/i/api/graphql/{X_QID['UserByScreenName']}/UserByScreenName?{qs}",
                    headers=_cookie_headers(),
                )
            if r.status_code == 200:
                user = (r.json().get("data") or {}).get("user", {}).get("result", {})
                legacy = user.get("legacy") or {}
                entry["user_id"] = str(user.get("rest_id") or "")
                entry["f_total"] = int(legacy.get("friends_count") or 0)
                entry["fo_total"] = int(legacy.get("followers_count") or 0)
        except Exception:
            pass

    # Fetch 1 batch of following via GraphQL (if not done)
    if not entry["f_done"] and entry["user_id"]:
        result = await _fetch_following_graphql(entry["user_id"], entry["f_cursor"])
        if result["error"]:
            return JSONResponse({
                "error": result["error"],
                "username": uname,
                "progress": _nf_progress(entry),
            }, status_code=502)
        entry["following"].extend(result["users"])
        entry["f_cursor"] = result["next_cursor"]
        entry["f_count"] = len(entry["following"])
        if not result["next_cursor"]:
            entry["f_done"] = True

    # Fetch 1 batch of followers via REST (only need IDs)
    if not entry["fo_done"]:
        result = await _fetch_rest_list("followers/list.json", uname, entry["fo_cursor"])
        if result["error"]:
            return JSONResponse({
                "error": result["error"],
                "username": uname,
                "progress": _nf_progress(entry),
            }, status_code=502)
        for u in result["users"]:
            entry["followers_ids"].add(str(u.get("id_str") or u.get("id") or ""))
        entry["fo_cursor"] = result["next_cursor"]
        entry["fo_count"] = len(entry["followers_ids"])
        if not result["next_cursor"] or result["next_cursor"] == "0":
            entry["fo_done"] = True

    entry["batches_done"] += 1

    # Compute non-followers from what we have so far
    non_followers = []
    for u in entry["following"]:
        uid = str(u.get("id") or "")
        if uid and uid not in entry["followers_ids"]:
            non_followers.append(u)

    # Return next 5 (offset by served count)
    offset = entry["served"]
    page = non_followers[offset:offset + 5]
    entry["served"] = offset + len(page)

    # If both lists done and we've served all, mark complete
    all_done = entry["f_done"] and entry["fo_done"]
    total_nf = len(non_followers)
    has_more = offset + 5 < total_nf or not all_done

    return {
        "username": uname,
        "non_followers": [
            {
                "screen_name": u.get("screen_name") or "",
                "name": u.get("name") or "",
                "avatar": u.get("avatar") or "",
                "followers": u.get("followers") or 0,
                "verified": u.get("verified") or False,
            }
            for u in page
        ],
        "total_non_followers": total_nf,
        "served": entry["served"],
        "has_more": has_more,
        "all_done": all_done,
        "progress": _nf_progress(entry),
    }


def _nf_progress(entry: dict) -> dict:
    """Estimate progress + time remaining."""
    f_total = entry["f_total"]
    fo_total = entry["fo_total"]
    f_done = entry["f_done"]
    fo_done = entry["fo_done"]
    f_count = entry["f_count"]
    fo_count = entry["fo_count"]
    batches = entry["batches_done"]

    # Progress percentage
    if f_total > 0 or fo_total > 0:
        pct = min(100, int(((f_count + fo_count) / max(f_total + fo_total, 1)) * 100))
    else:
        pct = 0

    # Estimate: each batch takes ~2s (2 REST calls). Remaining batches.
    if f_done and fo_done:
        est_sec = 0
    else:
        remaining_f = max(0, (f_total - f_count)) // 100 if not f_done else 0
        remaining_fo = max(0, (fo_total - fo_count)) // 100 if not fo_done else 0
        remaining_batches = max(remaining_f, remaining_fo)
        est_sec = remaining_batches * 3

    if est_sec < 60:
        est_str = f"~{est_sec}s"
    else:
        est_str = f"~{est_sec // 60}m {est_sec % 60}s"

    return {
        "pct": pct,
        "est_sec": est_sec,
        "est_str": est_str,
        "following_fetched": f_count,
        "following_total": f_total,
        "followers_fetched": fo_count,
        "followers_total": fo_total,
        "batches_done": batches,
        "following_done": f_done,
        "followers_done": fo_done,
    }


# ============================================================
# GHOST FOLLOWERS — inactive followers (0 tweets, no profile)
# ============================================================

@app.get("/api/ghost-followers/{username}")
async def ghost_followers(username: str):
    """Fetch one page of followers, return inactive ones (statuses_count=0)."""
    uname = _safe_username(username)
    if not uname:
        return JSONResponse({"error": "invalid username"}, status_code=400)

    result = await _fetch_rest_list("followers/list.json", uname, "", count=100)
    if result["error"]:
        return JSONResponse({"error": result["error"], "ghosts": [], "total": 0}, status_code=502)

    ghosts = []
    active = 0
    verified = 0
    for u in result["users"]:
        sc = int(u.get("statuses_count") or 0)
        is_verified = u.get("verified") or u.get("is_blue_verified") or False
        if is_verified:
            verified += 1
        if sc == 0:
            ghosts.append({
                "screen_name": u.get("screen_name") or "",
                "name": u.get("name") or "",
                "avatar": (u.get("profile_image_url_https") or "").replace("_normal", "_bigger"),
                "followers": u.get("followers_count") or 0,
                "verified": is_verified,
                "created_at": u.get("created_at") or "",
            })
        else:
            active += 1

    return {
        "username": uname,
        "ghosts": ghosts,
        "ghost_count": len(ghosts),
        "active_count": active,
        "verified_count": verified,
        "total_checked": len(result["users"]),
        "has_more": bool(result["next_cursor"] and result["next_cursor"] != "0"),
    }


@app.get("/api/health")
async def health():
    me = await run_agentx("me") if Path(AGENTX_BIN).exists() else {"ok": False, "error": {"code": "missing_binary", "message": "agentx binary not on this host"}}
    return {
        "ok": True,
        "agentx_bin": Path(AGENTX_BIN).exists(),
        "agentx_home": AGENTX_HOME,
        "account": AGENTX_ACCOUNT,
        "env_auth_token": bool(TWITTER_AUTH_TOKEN),
        "env_ct0": bool(TWITTER_CT0),
        "auth_ok": bool(me.get("ok")),
        "observer": (me.get("data") or {}).get("screenName") if me.get("ok") else None,
        "error": (me.get("error") or None) if not me.get("ok") else None,
        "vercel": ON_VERCEL,
        "audit_layers": 8,
        "cline": {
            "cookie_set": bool(CLINE_COOKIE),
            "bearer_set": bool(CLINE_API_KEY),
            "force": CLINE_FORCE,
            "chat_model": CLINE_CHAT_MODEL,
            "deep_model": CLINE_DEEP_MODEL,
        },
        "note": "On Vercel: TWITTER_AUTH_TOKEN + TWITTER_CT0 power cookie GraphQL fallback (no agentx binary). Local can use AgentX binary or the same env cookies.",
    }


@app.get("/assets/{fname}")
async def serve_asset(fname: str):
    """Serve static UI assets (capybara mascot, logo)."""
    safe = re.sub(r"[^a-zA-Z0-9_.\-]", "", fname or "")
    if not safe or ".." in safe:
        return Response(status_code=404, content=b"not found")
    path = ASSETS_DIR / safe
    if not path.exists() or not path.is_file():
        return Response(status_code=404, content=b"not found")
    suf = path.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".js": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
    }.get(suf, "application/octet-stream")
    # Short cache for code (versioned refs handle busting); long cache for media.
    if suf in (".js", ".css"):
        cache = "public, max-age=60, must-revalidate"
    else:
        cache = "public, max-age=86400"
    return FileResponse(
        path,
        media_type=media,
        headers={"Cache-Control": cache},
    )


class DeepRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    username: str = ""
    message: str
    template: str = ""


CHAT_TEMPLATES = {
    "profile": "Kasih saran perbaikan buat profil X akun ini — bio, foto, nama, pinned. Apa yang bisa bikin lebih menarik & aman dari shadowban.",
    "niche": "Analisis niche/topik akun ini. Saran positioning & konten apa yang cocok biar tumbuh dan engagement naik.",
    "recover": "Akun ini kena sinyal pembatasan. Kasih langkah konkret recovery shadowban, urut prioritas.",
    "growth": "Kasih strategi growth realistis buat akun ini — posting habit, engagement, jam posting, tipe konten.",
    "content": "Kasih 5 ide konten spesifik yang cocok buat akun ini biar reach & interaksi naik tanpa kelihatan spam.",
}


def _chat_prompt(scan: dict, message: str) -> str:
    p = scan.get("profile") or {}
    layers = scan.get("layers") or []
    layer_txt = ", ".join(
        f"{l.get('name')}={l.get('status')}({l.get('confidence')}%)" for l in layers
    ) or "belum ada data layer"
    return (
        "Kamu CapyAi 🦫 — asisten santai, ramah, ngasih saran soal akun X (Twitter). "
        "Jawab dalam Bahasa Indonesia yang hangat tapi to-the-point. Pakai poin kalau perlu. "
        "Jangan pakai format JSON, jawab natural seperti chat.\n\n"
        f"DATA AKUN @{p.get('username') or scan.get('username') or '-'}:\n"
        f"- Nama: {p.get('name') or '-'}\n"
        f"- Bio: {p.get('bio') or '-'}\n"
        f"- Followers: {p.get('followers') or 0} | Following: {p.get('following') or 0} | Posts: {p.get('tweets') or 0}\n"
        f"- Status keseluruhan: {scan.get('overall') or '-'}\n"
        f"- Layer shadowban: {layer_txt}\n\n"
        f"PERTANYAAN USER:\n{message}\n\n"
        "Jawab langsung, spesifik ke akun ini, maksimal ~180 kata."
    )


@app.post("/api/capy-chat")
async def capy_chat(req: ChatRequest):
    msg = (req.message or "").strip()
    tmpl = (req.template or "").strip()
    if tmpl and tmpl in CHAT_TEMPLATES:
        msg = CHAT_TEMPLATES[tmpl] + (f"\n\nCatatan user: {msg}" if msg else "")
    if not msg:
        return JSONResponse({"error": "message required"}, status_code=400)

    username = _safe_username(req.username)
    if not username:
        return JSONResponse(
            {"error": "Isi target username dulu ya 🌿", "code": "no_user"},
            status_code=400,
        )

    # --- follow gate + daily quota (reset 00:00 WIB) ---
    day = wib_today()
    follows = await check_follows_brand(username)
    limit = CHAT_LIMIT_FOLLOWER if follows else CHAT_LIMIT_GUEST
    used = await sb_chat_quota_get(username, day)
    if used >= limit:
        return JSONResponse(
            {
                "error": "limit",
                "code": "quota",
                "follows": follows,
                "limit": limit,
                "used": used,
                "brand": BRAND_HANDLE,
                "reply": (
                    f"Kuota chat harian @{username} udah habis ({used}/{limit}). "
                    + (
                        "Reset lagi jam 00:00 WIB ya 🦫"
                        if follows
                        else f"Follow @{BRAND_HANDLE} biar kuota naik jadi {CHAT_LIMIT_FOLLOWER}/hari! Reset tiap 00:00 WIB 🦫"
                    )
                ),
            },
            status_code=429,
        )

    scan = {"username": username, "profile": {}, "overall": "-", "layers": []}
    try:
        scan = await check_with_agentx(username)
    except Exception:
        pass  # chat still works without live data

    prompt = _chat_prompt(scan, msg)
    # System guard: never reveal the real backend model. If asked, say PUBLIC_MODEL_NAME.
    system_msg = (
        "Kamu CapyAi 🦫, asisten analisis akun X. Kalau user tanya kamu pakai "
        f"model/AI/teknologi/platform apa, jawab HANYA: '{PUBLIC_MODEL_NAME}' dan "
        "berhenti di situ — jangan sebut nama platform, perusahaan, penyedia, "
        "atau layanan apa pun (jangan sebut Cline, Venice, Anthropic, MiniMax, "
        "Virtuals, Qwen, OpenAI, dll). JANGAN pernah menyebut nama model backend. "
        "Selain itu jawab normal."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        if CLINE_FORCE and (CLINE_API_KEY or CLINE_COOKIE):
            # Opt-in Cline path
            try:
                content = await _cline_chat(CLINE_CHAT_MODEL, messages, timeout=60.0)
            except Exception as cline_err:
                err_str = str(cline_err)
                if any(s in err_str.lower() for s in ("auth expired", "not set", "cookie expired")):
                    return JSONResponse(
                        {
                            "error": "auth",
                            "code": "cline_auth",
                            "reply": "Capy lagi butuh auth ulang. Pantau aja ya, fix-nya lagi jalan 🦫",
                        },
                        status_code=503,
                    )
                # fallback ke Virtuals kalau Cline yang dipaksain gagal
                if not VIRTUALS_KEY:
                    return JSONResponse({"error": f"CapyAi error: {cline_err}"}, status_code=502)
                try:
                    content = await _virtuals_chat(VIRTUALS_CHAT_MODEL, messages, timeout=60.0)
                except Exception as virt_err:
                    return JSONResponse(
                        {"error": f"CapyAi: Cline {cline_err}; Virtuals {virt_err}"},
                        status_code=502,
                    )
        else:
            # Default: Virtuals primary, model sesuai env (default minimax-m3)
            if not VIRTUALS_KEY:
                return JSONResponse(
                    {"error": "VIRTUALS_KEY not set on this host"}, status_code=502
                )
            content = await _virtuals_chat(VIRTUALS_CHAT_MODEL, messages, timeout=60.0)
    except Exception as e:
        return JSONResponse({"error": f"CapyAi error: {e}"}, status_code=502)

    reply = (content or "").strip()
    if reply.startswith("```"):
        reply = re.sub(r"^```[a-zA-Z]*\n?", "", reply)
        reply = re.sub(r"\n?```$", "", reply).strip()
    # Belt-and-suspenders: scrub any accidental leak of the real model name.
    reply = re.sub(r"(?i)minimax[\s\-]*m?3?(\s*preview)?", PUBLIC_MODEL_NAME, reply)
    reply = re.sub(r"(?i)\bvirtuals\b", PUBLIC_MODEL_NAME, reply)

    # count this successful chat against today's quota
    await sb_chat_quota_incr(username, day)
    remaining = max(0, limit - (used + 1))
    return {
        "reply": reply or "Capy lagi bingung, coba tanya lagi ya 🦫",
        "username": username,
        "profile": scan.get("profile") or {},
        "follows": follows,
        "limit": limit,
        "used": used + 1,
        "remaining": remaining,
        "brand": BRAND_HANDLE,
        "model": PUBLIC_MODEL_NAME,
        "timestamp": datetime.now().isoformat(),
    }


def _deep_prompt(payload: dict) -> str:
    """Build the CapyAi analysis instruction from a scan result."""
    p = payload.get("profile") or {}
    layers = payload.get("layers") or []
    metrics = payload.get("metrics") or {}
    layer_lines = "\n".join(
        f"- {l.get('name')}: {l.get('status')} ({l.get('confidence')}%) — {l.get('desc')}"
        for l in layers
        if isinstance(l, dict)
    )
    followers = p.get("followers") or 0
    following = p.get("following") or 0
    tweets = p.get("tweets") or 0
    return f"""Kamu adalah CapyAi, asisten analisis akun X (Twitter) yang ramah, tenang, dan cerdas — berkarakter kapibara santai. Analisis akun berikut secara mendalam dan berikan output dalam Bahasa Indonesia yang hangat namun teknis akurat.

DATA AKUN:
- Username: @{p.get('username')}
- Nama: {p.get('name')}
- Followers: {followers}
- Following: {following}
- Total post: {tweets}
- Verified: {p.get('verified')}
- Overall status shadowban: {payload.get('overall')}
- Metrics: search {metrics.get('search')}, reply {metrics.get('reply')}, quote {metrics.get('quote')}, engagement {metrics.get('engagement')}

HASIL 8-LAYER AUDIT:
{layer_lines}

Balas HANYA dengan JSON valid (tanpa markdown fence) dengan struktur berikut:
{{
  "summary": "ringkasan 2-3 kalimat kondisi akun, hangat & jelas",
  "growth_insight": {{
    "follower_following_ratio": <angka rasio followers/following, 2 desimal>,
    "verdict": "sehat|perlu perhatian|bermasalah",
    "note": "1-2 kalimat insight rasio & pertumbuhan"
  }},
  "engagement_breakdown": {{
    "score": <0-100 estimasi kualitas engagement>,
    "note": "penjelasan singkat kualitas engagement"
  }},
  "charts": {{
    "visibility": [
      {{"label":"Search","value":<0-100>}},
      {{"label":"Reply","value":<0-100>}},
      {{"label":"Quote","value":<0-100>}},
      {{"label":"Engagement","value":<0-100>}},
      {{"label":"Index","value":<0-100>}}
    ],
    "layer_confidence": [ {{"label":"<nama layer>","value":<confidence>}} ... untuk 8 layer ]
  }},
  "non_followers_estimate": "kalimat estimasi berapa orang yang di-follow tapi tidak follow balik, berdasarkan rasio (perkiraan kasar, sebut sebagai estimasi)",
  "solutions": [
    "solusi/tips ke-1 konkret & actionable",
    "... total TEPAT 10 solusi untuk mengatasi/mencegah shadowban & meningkatkan visibility, spesifik untuk kondisi akun ini"
  ]
}}

Pastikan solutions berisi tepat 10 item. Jangan tambahkan teks apa pun di luar JSON."""


@app.post("/api/deep-analysis")
async def deep_analysis(req: DeepRequest):
    username = _safe_username(req.username)
    if not username:
        return JSONResponse({"error": "username required"}, status_code=400)

    # 10-minute cache
    now = time.time()
    cached = DEEP_CACHE.get(username)
    if cached and cached[0] > now:
        return JSONResponse({**cached[1], "cached": True})
    # opportunistic prune
    for k in [k for k, v in list(DEEP_CACHE.items()) if v[0] <= now]:
        DEEP_CACHE.pop(k, None)

    # Get a fresh scan to feed the model
    try:
        scan = await check_with_agentx(username)
    except Exception as e:
        return JSONResponse(
            {"error": f"Capy gagal ambil data akun: {e}"}, status_code=502
        )

    prompt = _deep_prompt(scan)
    messages = [{"role": "user", "content": prompt}]
    try:
        if CLINE_FORCE and (CLINE_API_KEY or CLINE_COOKIE):
            # Opt-in Cline path
            try:
                content = await _cline_chat(CLINE_DEEP_MODEL, messages, timeout=90.0)
            except Exception as cline_err:
                if not VIRTUALS_KEY:
                    return JSONResponse(
                        {"error": f"CapyAi error: {cline_err}"}, status_code=502
                    )
                try:
                    content = await _virtuals_chat(VIRTUALS_MODEL, messages, timeout=90.0)
                except Exception as virt_err:
                    return JSONResponse(
                        {"error": f"CapyAi: Cline {cline_err}; Virtuals {virt_err}"},
                        status_code=502,
                    )
        else:
            # Default: Virtuals primary, model Opus untuk deep analysis
            if not VIRTUALS_KEY:
                return JSONResponse(
                    {"error": "VIRTUALS_KEY not set on this host"}, status_code=502
                )
            content = await _virtuals_chat(VIRTUALS_MODEL, messages, timeout=90.0)
    except Exception as e:
        return JSONResponse({"error": f"CapyAi error: {e}"}, status_code=502)

    # Parse model JSON (strip fences if any)
    txt = (content or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\n?", "", txt)
        txt = re.sub(r"\n?```$", "", txt).strip()
    analysis = None
    try:
        analysis = json.loads(txt)
    except json.JSONDecodeError:
        s, e = txt.find("{"), txt.rfind("}")
        if s >= 0 and e > s:
            try:
                analysis = json.loads(txt[s : e + 1])
            except json.JSONDecodeError:
                analysis = None
    if analysis is None:
        return JSONResponse(
            {"error": "CapyAi kasih format aneh", "raw": txt[:400]}, status_code=502
        )

    result = {
        "username": username,
        "profile": scan.get("profile"),
        "overall": scan.get("overall"),
        "analysis": analysis,
        "model": PUBLIC_MODEL_NAME,
        "timestamp": datetime.now().isoformat(),
    }
    DEEP_CACHE[username] = (now + DEEP_TTL_SEC, result)
    return JSONResponse(result)


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9384)
