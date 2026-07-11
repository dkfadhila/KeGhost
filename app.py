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
AGENTX_BIN = os.environ.get("AGENTX_BIN", str(Path(r"G:\Mirai Noa\agentx-src\agentx.exe")))
AGENTX_HOME = os.environ.get("AGENTX_HOME", str(BASE_DIR / ".agentx-home"))
AGENTX_ACCOUNT = os.environ.get("AGENTX_ACCOUNT", "keghost")

AVATAR_DIR.mkdir(parents=True, exist_ok=True)


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
        return {"avg_views": 0, "avg_likes": 0, "avg_replies": 0, "avg_rts": 0, "reply_ratio": 0, "quote_ratio": 0}
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
        "reply_ratio": (replies / max(views, 1)),
        "quote_ratio": (quotes / max(views, 1)),
        "total_views": views,
    }


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
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


async def check_with_agentx(username: str) -> dict:
    """
    Real-ish visibility check via AgentX.
    Uses profile + posts + search probes. Not a perfect oracle for every ban type,
    but grounded in live X data from the observer account.
    """
    username = username.lower().replace("@", "").strip()
    sources = {"engine": "agentx", "account": AGENTX_ACCOUNT}

    # 1) Profile
    user_env = await run_agentx("user", username)
    if not user_env.get("ok"):
        err = (user_env.get("error") or {})
        code = err.get("code") or "api_error"
        msg = err.get("message") or "failed to fetch user"
        if code in ("not_found",) or "not found" in msg.lower():
            return {
                "username": username,
                "overall": "banned",
                "metrics": {"search": 0, "reply": 0, "quote": 0, "engagement": 0},
                "tests": [
                    {"name": "Search Ban", "status": "banned", "confidence": 95, "desc": "Akun tidak ketemu di X"},
                    {"name": "Ghost Ban", "status": "banned", "confidence": 90, "desc": "Profil tidak bisa dibaca observer"},
                    {"name": "Reply Ban", "status": "banned", "confidence": 80, "desc": "Tidak ada data reply"},
                    {"name": "Quote Ban", "status": "banned", "confidence": 80, "desc": "Tidak ada data quote"},
                    {"name": "Typeahead Ban", "status": "banned", "confidence": 90, "desc": "Username tidak resolve"},
                    {"name": "Hashtag Ban", "status": "warning", "confidence": 50, "desc": "Tidak bisa diuji (profil hilang)"},
                ],
                "profile": None,
                "source": sources,
                "error": msg,
                "timestamp": datetime.now().isoformat(),
            }
        # auth / network issues bubble up
        raise RuntimeError(f"agentx user failed: {code}: {msg}")

    user = user_env.get("data") or {}
    profile = build_profile(user)
    sources["rateLimit"] = user_env.get("rateLimit")

    # 2) Posts + search probes + avatar cache (temp 1 menit) in parallel
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

    # --- Score tests ---
    tests = []
    mstats = _metrics_of(posts)

    # Search Ban: from:user should surface their posts if public + recent activity
    if profile.get("protected"):
        tests.append({
            "name": "Search Ban",
            "status": "warning",
            "confidence": 40,
            "desc": "Akun protected — search terbatas secara normal",
        })
        search_status = "warning"
        search_score = 55
    elif len(posts) == 0:
        tests.append({
            "name": "Search Ban",
            "status": "warning",
            "confidence": 45,
            "desc": "Tidak ada post publik terbaru untuk diuji di search",
        })
        search_status = "warning"
        search_score = 50
    elif len(from_own) >= 1:
        tests.append({
            "name": "Search Ban",
            "status": "safe",
            "confidence": _clamp(10 + len(from_own) * 8, 8, 25),
            "desc": f"Post muncul di search from:{username} ({len(from_own)} hit)",
        })
        search_status = "safe"
        search_score = _clamp(70 + len(from_own) * 5, 70, 98)
    else:
        tests.append({
            "name": "Search Ban",
            "status": "banned",
            "confidence": 82,
            "desc": f"Post ada ({len(posts)}) tapi from:{username} kosong di search",
        })
        search_status = "banned"
        search_score = 18

    # Ghost Ban proxy: posts exist + very low views relative to followers, AND weak search
    followers = max(profile.get("followers") or 0, 1)
    avg_views = mstats["avg_views"]
    # Expected rough floor: tiny fraction of followers
    expected_floor = max(20, followers * 0.002)
    if len(posts) == 0:
        tests.append({
            "name": "Ghost Ban",
            "status": "warning",
            "confidence": 40,
            "desc": "Tidak ada post untuk ukur jangkauan",
        })
        ghost_status = "warning"
        ghost_score = 50
    elif avg_views < expected_floor and search_status == "banned":
        tests.append({
            "name": "Ghost Ban",
            "status": "banned",
            "confidence": 78,
            "desc": f"Views rata-rata sangat rendah ({int(avg_views)}) vs followers {followers}",
        })
        ghost_status = "banned"
        ghost_score = 22
    elif avg_views < expected_floor:
        tests.append({
            "name": "Ghost Ban",
            "status": "warning",
            "confidence": 60,
            "desc": f"Views rata-rata rendah ({int(avg_views)}) — mungkin partial limit",
        })
        ghost_status = "warning"
        ghost_score = 48
    else:
        tests.append({
            "name": "Ghost Ban",
            "status": "safe",
            "confidence": _clamp(12 if avg_views > expected_floor * 5 else 22, 8, 30),
            "desc": f"Post punya jangkauan wajar (avg views {int(avg_views)})",
        })
        ghost_status = "safe"
        ghost_score = _clamp(75 + min(avg_views / 1000, 20), 70, 97)

    # Reply Ban proxy: share of reply-looking posts + reply metrics
    reply_posts = [p for p in posts if (p.get("text") or "").startswith("@")]
    if len(posts) == 0:
        tests.append({
            "name": "Reply Ban",
            "status": "warning",
            "confidence": 35,
            "desc": "Tidak ada sampel reply",
        })
        reply_status = "warning"
        reply_score = 50
    elif len(reply_posts) >= 2 and mstats["avg_replies"] < 1 and avg_views < expected_floor:
        tests.append({
            "name": "Reply Ban",
            "status": "banned",
            "confidence": 70,
            "desc": "Banyak reply tapi hampir tidak ada engagement balik",
        })
        reply_status = "banned"
        reply_score = 25
    elif len(reply_posts) >= 1 and mstats["avg_views"] < expected_floor * 0.5:
        tests.append({
            "name": "Reply Ban",
            "status": "warning",
            "confidence": 55,
            "desc": "Reply terlihat lemah jangkauannya",
        })
        reply_status = "warning"
        reply_score = 52
    else:
        tests.append({
            "name": "Reply Ban",
            "status": "safe",
            "confidence": 15,
            "desc": "Tidak ada sinyal reply ban yang kuat",
        })
        reply_status = "safe"
        reply_score = 86

    # Quote Ban proxy: quote metrics on recent posts
    avg_quotes = 0
    if posts:
        avg_quotes = sum(int((p.get("metrics") or {}).get("quotes") or 0) for p in posts) / len(posts)
    if len(posts) == 0:
        tests.append({
            "name": "Quote Ban",
            "status": "warning",
            "confidence": 35,
            "desc": "Tidak ada sampel quote",
        })
        quote_status = "warning"
        quote_score = 50
    elif avg_quotes == 0 and avg_views > 500 and search_status == "banned":
        tests.append({
            "name": "Quote Ban",
            "status": "banned",
            "confidence": 68,
            "desc": "Views ada tapi quote stuck di 0 + search lemah",
        })
        quote_status = "banned"
        quote_score = 28
    elif avg_quotes == 0 and avg_views > 2000:
        tests.append({
            "name": "Quote Ban",
            "status": "warning",
            "confidence": 50,
            "desc": "Quote metrics kosong meski views lumayan",
        })
        quote_status = "warning"
        quote_score = 55
    else:
        tests.append({
            "name": "Quote Ban",
            "status": "safe",
            "confidence": 14,
            "desc": "Quote visibility terlihat normal",
        })
        quote_status = "safe"
        quote_score = 88

    # Typeahead Ban proxy: does @user / bare username surface the account in search?
    surface_hits = len(people_own) + len(bare_own) + len([m for m in mentioned if _author_screen(m) == username])
    # Also count if profile is resolvable (we already have profile) — typeahead often fails separately
    if surface_hits >= 1 or len(from_own) >= 1:
        tests.append({
            "name": "Typeahead Ban",
            "status": "safe",
            "confidence": 12,
            "desc": "Username/post ketemu lewat search observer",
        })
        type_status = "safe"
        type_score = 90
    elif profile and len(posts) > 0 and search_status == "banned":
        tests.append({
            "name": "Typeahead Ban",
            "status": "banned",
            "confidence": 75,
            "desc": "Profil ada tapi hampir tidak muncul di search surface",
        })
        type_status = "banned"
        type_score = 20
    else:
        tests.append({
            "name": "Typeahead Ban",
            "status": "warning",
            "confidence": 48,
            "desc": "Sinyal typeahead lemah / sampel tipis",
        })
        type_status = "warning"
        type_score = 55

    # Hashtag Ban
    if not hashtag:
        tests.append({
            "name": "Hashtag Ban",
            "status": "safe",
            "confidence": 20,
            "desc": "Tidak ada hashtag di post terbaru — skip ketat, default aman",
        })
        hash_status = "safe"
        hash_score = 75
    elif len(hashtag_own) >= 1:
        tests.append({
            "name": "Hashtag Ban",
            "status": "safe",
            "confidence": 10,
            "desc": f"Post muncul di search {hashtag}",
        })
        hash_status = "safe"
        hash_score = 92
    else:
        tests.append({
            "name": "Hashtag Ban",
            "status": "banned",
            "confidence": 72,
            "desc": f"Punya hashtag {hashtag} tapi tidak muncul di hasil search tag itu",
        })
        hash_status = "banned"
        hash_score = 24

    banned_count = sum(1 for t in tests if t["status"] == "banned")
    warn_count = sum(1 for t in tests if t["status"] == "warning")
    if banned_count >= 3:
        overall = "banned"
    elif banned_count >= 1 or warn_count >= 2:
        overall = "warning"
    else:
        overall = "safe"

    # Engagement metric from real views/likes
    if avg_views <= 0:
        eng = 20
    else:
        eng = _clamp(30 + min(avg_views / 50, 50) + min(mstats["avg_likes"] / 5, 20), 10, 98)

    # Recent posts summary for UI
    recent = []
    for p in posts[:5]:
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
        "metrics": {
            "search": search_score if search_status != "banned" else _clamp(search_score, 5, 35),
            "reply": reply_score,
            "quote": quote_score,
            "engagement": eng,
        },
        "tests": tests,
        "profile": profile,
        "recent_posts": recent,
        "probes": {
            "posts_count": len(posts),
            "from_search_hits": len(from_own),
            "mention_search_hits": len(people_own) + len(bare_own),
            "hashtag": hashtag,
            "hashtag_hits": len(hashtag_own),
            "avg_views": int(avg_views),
        },
        "source": sources,
        "timestamp": datetime.now().isoformat(),
    }


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
                "tests": [],
                "profile": None,
                "error": f"Yah capybara-nya bingung nih: {e}",
                "timestamp": datetime.now().isoformat(),
            },
            status_code=502,
        )

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """INSERT INTO checks (username, overall, search_vis, reply_rate, quote_rate, engagement, tests)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                result["overall"],
                result["metrics"]["search"],
                result["metrics"]["reply"],
                result["metrics"]["quote"],
                result["metrics"]["engagement"],
                json.dumps(result["tests"]),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return JSONResponse(result)


@app.get("/api/history")
async def get_history(limit: int = 20):
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


@app.get("/api/health")
async def health():
    me = await run_agentx("me")
    return {
        "ok": True,
        "agentx_bin": Path(AGENTX_BIN).exists(),
        "agentx_home": AGENTX_HOME,
        "account": AGENTX_ACCOUNT,
        "auth_ok": bool(me.get("ok")),
        "observer": (me.get("data") or {}).get("screenName") if me.get("ok") else None,
        "error": (me.get("error") or None) if not me.get("ok") else None,
    }


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9384)
