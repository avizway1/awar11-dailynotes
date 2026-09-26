"""
Aviz Academy - RDS + ElastiCache Serverless (Valkey) Demo
Product Catalog API + Live UI Dashboard
"Learn by Doing, Not Just Watching"
"""

import os, time, json, logging
import pymysql, redis
from flask import Flask, jsonify, request, Response
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# RDS MySQL config - all values from environment variables
DB_CONFIG = {
    "host":        os.environ.get("DB_HOST", "localhost"),
    "port":        int(os.environ.get("DB_PORT", 3306)),
    "user":        os.environ.get("DB_USER", "admin"),
    "password":    os.environ.get("DB_PASSWORD", "avizacademy"),
    "database":    os.environ.get("DB_NAME", "productdb"),
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 5,
}

# ElastiCache Serverless Valkey config
# Serverless ALWAYS enforces TLS - cannot be disabled
# ssl=True      -> enables TLS connection
# ssl_cert_reqs -> None skips cert verification (safe inside private VPC)
# No password needed - No Access Control mode
REDIS_CONFIG = {
    "host":                   os.environ.get("REDIS_HOST", "localhost"),
    "port":                   int(os.environ.get("REDIS_PORT", 6379)),
    "decode_responses":       True,
    "socket_connect_timeout": 5,
    "socket_keepalive":       True,
    "ssl":                    True,
    "ssl_cert_reqs":          None,
}

CACHE_TTL = int(os.environ.get("CACHE_TTL", 60))

def get_db(): return pymysql.connect(**DB_CONFIG)

# Single shared Redis client - created ONCE at startup
# This avoids "Too many connections" error.
# TLS handshake happens once at boot, then reused for every request.
_redis_client = redis.Redis(**REDIS_CONFIG)

def get_redis(): return _redis_client
def ckey(kind, id=None): return f"aviz:{kind}:{id}" if id else f"aviz:{kind}"

# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def dashboard():
    return Response(DASHBOARD_HTML, mimetype="text/html")

@app.route("/health")
def health():
    s = {"api":"ok","rds":"unknown","redis":"unknown","ts":datetime.utcnow().isoformat()}
    try: c=get_db(); c.close(); s["rds"]="ok"
    except Exception as e: s["rds"]=f"error: {e}"
    try: get_redis().ping(); s["redis"]="ok"
    except Exception as e: s["redis"]=f"error: {e}"
    return jsonify(s), 200 if s["rds"]=="ok" and s["redis"]=="ok" else 503

# All products via cache
@app.route("/products")
def get_products():
    key=ckey("all"); r=get_redis(); start=time.time()
    cached=r.get(key)
    if cached:
        ms=round((time.time()-start)*1000,2)
        return jsonify({"source":"cache","cache_hit":True,"response_time_ms":ms,
                        "ttl_remaining_s":r.ttl(key),"products":json.loads(cached)})
    conn=get_db()
    try:
        with conn.cursor() as cur: cur.execute("SELECT * FROM products ORDER BY id"); products=cur.fetchall()
    finally: conn.close()
    r.setex(key,CACHE_TTL,json.dumps(products,default=str))
    ms=round((time.time()-start)*1000,2)
    return jsonify({"source":"database","cache_hit":False,"response_time_ms":ms,
                    "ttl_remaining_s":CACHE_TTL,"products":products})

# All products direct DB
@app.route("/products/direct")
def get_products_direct():
    start=time.time(); conn=get_db()
    try:
        with conn.cursor() as cur: cur.execute("SELECT * FROM products ORDER BY id"); products=cur.fetchall()
    finally: conn.close()
    ms=round((time.time()-start)*1000,2)
    return jsonify({"source":"database","cache_hit":False,"response_time_ms":ms,"bypass_cache":True,"products":products})

# Single product via cache
@app.route("/products/<int:pid>")
def get_product(pid):
    key=ckey("id",pid); r=get_redis(); start=time.time()
    cached=r.get(key)
    if cached:
        ms=round((time.time()-start)*1000,2)
        return jsonify({"source":"cache","cache_hit":True,"response_time_ms":ms,
                        "ttl_remaining_s":r.ttl(key),"product":json.loads(cached)})
    conn=get_db()
    try:
        with conn.cursor() as cur: cur.execute("SELECT * FROM products WHERE id=%s",(pid,)); product=cur.fetchone()
    finally: conn.close()
    if not product: return jsonify({"error":"Not found"}),404
    r.setex(key,CACHE_TTL,json.dumps(product,default=str))
    ms=round((time.time()-start)*1000,2)
    return jsonify({"source":"database","cache_hit":False,"response_time_ms":ms,
                    "ttl_remaining_s":CACHE_TTL,"product":product})

# Single product direct DB
@app.route("/products/<int:pid>/direct")
def get_product_direct(pid):
    start=time.time(); conn=get_db()
    try:
        with conn.cursor() as cur: cur.execute("SELECT * FROM products WHERE id=%s",(pid,)); product=cur.fetchone()
    finally: conn.close()
    if not product: return jsonify({"error":"Not found"}),404
    ms=round((time.time()-start)*1000,2)
    return jsonify({"source":"database","cache_hit":False,"response_time_ms":ms,"bypass_cache":True,"product":product})

@app.route("/cache/stats")
def cache_stats():
    r=get_redis(); keys=r.keys("aviz:*"); info=r.info("stats"); mem=r.info("memory")
    hits=info.get("keyspace_hits",0); misses=info.get("keyspace_misses",0); total=hits+misses
    return jsonify({"cached_keys":len(keys),"entries":[{"key":k,"ttl":r.ttl(k)} for k in keys],
                    "total_hits":hits,"total_misses":misses,
                    "hit_rate_pct":round(hits/total*100,1) if total>0 else 0,
                    "used_memory":mem.get("used_memory_human")})

@app.route("/cache/flush", methods=["DELETE"])
def flush_cache():
    r=get_redis(); keys=r.keys("aviz:*")
    if keys: r.delete(*keys)
    return jsonify({"message":"Cache flushed","keys_removed":len(keys)})

@app.route("/benchmark")
def benchmark():
    pid=request.args.get("product_id",1,type=int); r=get_redis(); r.delete(ckey("id",pid))
    results=[]
    for i in range(1,6):
        start=time.time(); key=ckey("id",pid); hit=r.get(key) is not None
        if not hit:
            conn=get_db()
            try:
                with conn.cursor() as cur: cur.execute("SELECT * FROM products WHERE id=%s",(pid,)); p=cur.fetchone()
            finally: conn.close()
            if p: r.setex(key,CACHE_TTL,json.dumps(p,default=str))
        ms=round((time.time()-start)*1000,2)
        results.append({"request":i,"source":"cache" if hit else "database","cache_hit":hit,"response_time_ms":ms})
    db_t=[x["response_time_ms"] for x in results if not x["cache_hit"]]
    ca_t=[x["response_time_ms"] for x in results if x["cache_hit"]]
    avg_db=round(sum(db_t)/len(db_t),2) if db_t else 0
    avg_ca=round(sum(ca_t)/len(ca_t),2) if ca_t else 0
    speedup=round(avg_db/avg_ca,1) if avg_ca>0 and avg_db>0 else "N/A"
    return jsonify({"results":results,"summary":{"avg_db_ms":avg_db,"avg_cache_ms":avg_ca,"speedup":speedup}})


# ═══════════════════════════════════════════════════════════
#  DASHBOARD HTML
# ═══════════════════════════════════════════════════════════
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aviz Academy — RDS + ElastiCache Demo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Sora:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--navy:#0d1117;--card:#161b22;--border:#30363d;--orange:#ff6600;--orange2:#ff8c00;
--green:#39d353;--red:#f85149;--blue:#58a6ff;--yellow:#e3b341;--text:#e6edf3;--muted:#8b949e;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--navy);color:var(--text);font-family:'Sora',sans-serif;min-height:100vh;overflow-x:hidden;}
header{background:linear-gradient(135deg,#0d1117,#161b22);border-bottom:1px solid var(--border);
  padding:0 2rem;display:flex;align-items:center;justify-content:space-between;
  height:64px;position:sticky;top:0;z-index:100;}
.logo{display:flex;align-items:center;gap:.75rem;}
.logo-dot{width:10px;height:10px;border-radius:50%;background:var(--orange);
  box-shadow:0 0 12px var(--orange);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(1.3)}}
.logo-text{font-size:1.05rem;font-weight:700;letter-spacing:-.02em;}
.logo-sub{font-size:.68rem;color:var(--orange);font-family:'Space Mono',monospace;}
.health-bar{display:flex;gap:.6rem;align-items:center;}
.hpill{font-size:.68rem;font-family:'Space Mono',monospace;padding:.28rem .75rem;
  border-radius:20px;border:1px solid;display:flex;align-items:center;gap:.35rem;}
.pill-ok{border-color:#39d35366;color:var(--green);background:#39d35311;}
.pill-err{border-color:#f8514966;color:var(--red);background:#f8514911;}
.pill-wait{border-color:#8b949e66;color:var(--muted);background:#8b949e11;}
main{max-width:1360px;margin:0 auto;padding:1.75rem 2rem;display:grid;
  grid-template-columns:1fr 1fr;gap:1.25rem;}
.full{grid-column:1/-1;}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.4rem;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
.card.gt::before{background:linear-gradient(90deg,transparent,var(--green),transparent);}
.card.bt::before{background:linear-gradient(90deg,transparent,var(--blue),transparent);}
.card.ot::before{background:linear-gradient(90deg,transparent,var(--orange),transparent);}
.card.yt::before{background:linear-gradient(90deg,transparent,var(--yellow),transparent);}
.stitle{font-size:.62rem;font-family:'Space Mono',monospace;letter-spacing:.15em;
  text-transform:uppercase;color:var(--muted);margin-bottom:1rem;
  display:flex;align-items:center;gap:.5rem;}
.stitle::after{content:'';flex:1;height:1px;background:var(--border);}
.btn-row{display:flex;gap:.65rem;flex-wrap:wrap;margin-bottom:.9rem;}
.btn{font-family:'Space Mono',monospace;font-size:.75rem;font-weight:700;
  padding:.55rem 1.1rem;border-radius:8px;cursor:pointer;border:none;
  display:flex;align-items:center;gap:.45rem;transition:all .15s ease;letter-spacing:.02em;}
.btn:active{transform:scale(.97);}
.btn-cache{background:linear-gradient(135deg,#1a3a1a,#1f4a1f);color:var(--green);border:1px solid #39d35355;}
.btn-cache:hover{box-shadow:0 0 20px rgba(57,211,83,.35);border-color:var(--green);}
.btn-db{background:linear-gradient(135deg,#1a2a3a,#1a3050);color:var(--blue);border:1px solid #58a6ff55;}
.btn-db:hover{box-shadow:0 0 20px rgba(88,166,255,.35);border-color:var(--blue);}
.btn-danger{background:linear-gradient(135deg,#3a1a1a,#4a1f1f);color:var(--red);border:1px solid #f8514955;}
.btn-danger:hover{box-shadow:0 0 20px rgba(248,81,73,.35);border-color:var(--red);}
.btn-yellow{background:linear-gradient(135deg,#2a2200,#3a3000);color:var(--yellow);border:1px solid #e3b34155;}
.btn-yellow:hover{box-shadow:0 0 20px rgba(227,179,65,.35);border-color:var(--yellow);}
.btn:disabled{opacity:.4;cursor:not-allowed;}
.irow{display:flex;gap:.5rem;margin-bottom:.85rem;align-items:center;flex-wrap:wrap;}
.irow label{font-size:.72rem;color:var(--muted);white-space:nowrap;font-family:'Space Mono',monospace;}
.irow input[type=number]{background:#0d1117;border:1px solid var(--border);color:var(--text);
  padding:.4rem .7rem;border-radius:6px;font-family:'Space Mono',monospace;font-size:.78rem;
  width:90px;outline:none;}
.irow input[type=number]:focus{border-color:var(--orange);}
.irow input[type=checkbox]{width:16px;height:16px;accent-color:var(--orange);cursor:pointer;}
.rpanel{background:#0a0e13;border:1px solid var(--border);border-radius:8px;
  padding:.9rem;min-height:110px;max-height:300px;overflow-y:auto;
  font-family:'Space Mono',monospace;font-size:.73rem;line-height:1.75;}
.rpanel::-webkit-scrollbar{width:4px;}
.rpanel::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.badge{display:inline-flex;align-items:center;gap:.35rem;padding:.22rem .65rem;
  border-radius:20px;font-size:.68rem;font-family:'Space Mono',monospace;font-weight:700;margin-bottom:.6rem;}
.bc{background:#39d35322;color:var(--green);border:1px solid #39d35355;}
.bd{background:#58a6ff22;color:var(--blue);border:1px solid #58a6ff55;}
.be{background:#f8514922;color:var(--red);border:1px solid #f8514955;}
.by{background:#e3b34122;color:var(--yellow);border:1px solid #e3b34155;}
.tchip{font-family:'Space Mono',monospace;font-size:.68rem;padding:.18rem .55rem;
  border-radius:6px;background:#ffffff0d;margin-left:.4rem;}
.tf{color:var(--green);}.ts{color:var(--orange);}
.sgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:.65rem;margin-bottom:.9rem;}
.sbox{background:#0a0e13;border:1px solid var(--border);border-radius:8px;padding:.75rem;text-align:center;}
.sval{font-size:1.5rem;font-weight:800;font-family:'Space Mono',monospace;line-height:1;}
.slbl{font-size:.62rem;color:var(--muted);margin-top:.25rem;text-transform:uppercase;letter-spacing:.07em;}
.sg{color:var(--green);}.sb{color:var(--blue);}.so{color:var(--orange);}.sr{color:var(--red);}
.brow{display:flex;align-items:center;gap:.65rem;margin-bottom:.45rem;padding:.55rem .75rem;
  border-radius:6px;background:#0a0e13;border:1px solid var(--border);transition:border-color .3s;}
.brow.hit{border-color:#39d35333;}.brow.miss{border-color:#58a6ff33;}
.bnum{font-family:'Space Mono',monospace;font-size:.68rem;color:var(--muted);width:18px;}
.bwrap{flex:1;height:7px;background:#ffffff0d;border-radius:4px;overflow:hidden;}
.bbar{height:100%;border-radius:4px;transition:width .65s cubic-bezier(.16,1,.3,1);}
.bar-c{background:linear-gradient(90deg,var(--green),#39d35399);}
.bar-d{background:linear-gradient(90deg,var(--blue),#58a6ff99);}
.btime{font-family:'Space Mono',monospace;font-size:.72rem;width:62px;text-align:right;}
.ptable{width:100%;border-collapse:collapse;font-size:.76rem;}
.ptable th{background:#0a0e13;padding:.55rem .75rem;text-align:left;
  font-family:'Space Mono',monospace;font-size:.62rem;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--border);}
.ptable td{padding:.5rem .75rem;border-bottom:1px solid #ffffff08;}
.ptable tr:hover td{background:#ffffff04;}
.cpill{display:inline-block;padding:.12rem .55rem;border-radius:20px;font-size:.63rem;
  background:#ffffff0d;border:1px solid var(--border);font-family:'Space Mono',monospace;}
.price{color:var(--green);font-family:'Space Mono',monospace;font-weight:700;}
.logarea{background:#0a0e13;border:1px solid var(--border);border-radius:8px;
  padding:.9rem;height:150px;overflow-y:auto;
  font-family:'Space Mono',monospace;font-size:.7rem;line-height:1.85;}
.logarea::-webkit-scrollbar{width:4px;}
.logarea::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px;}
.lhit{color:var(--green);}.lmiss{color:var(--blue);}.ldb{color:var(--yellow);}
.lerr{color:var(--red);}.lflush{color:var(--orange);}.lts{color:var(--muted);font-size:.62rem;}
.ttlwrap{background:#ffffff0d;border-radius:4px;height:5px;margin-top:.6rem;overflow:hidden;}
.ttlbar{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--orange),var(--orange2));transition:width .5s;}
.spinner{display:inline-block;width:13px;height:13px;border:2px solid #ffffff22;
  border-top-color:var(--orange);border-radius:50%;animation:spin .6s linear infinite;}
@keyframes spin{to{transform:rotate(360deg)}}
.abox{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #ff660033;
  border-radius:10px;padding:.9rem 1.1rem;display:flex;gap:.9rem;align-items:flex-start;}
.aico{font-size:1.6rem;line-height:1;flex-shrink:0;}
.atitle{font-size:.67rem;font-family:'Space Mono',monospace;color:var(--orange);
  text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem;}
.atext{font-size:.79rem;color:var(--muted);line-height:1.55;}
.empty{color:var(--muted);font-family:'Space Mono',monospace;font-size:.72rem;
  padding:1.25rem;text-align:center;opacity:.5;}
.warn-box{margin-top:.75rem;padding:.65rem .85rem;background:#58a6ff0d;
  border:1px solid #58a6ff22;border-radius:8px;font-size:.73rem;color:var(--muted);}
@media(max-width:860px){main{grid-template-columns:1fr;}.full{grid-column:1;}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-dot"></div>
    <div>
      <div class="logo-text">Aviz Academy</div>
      <div class="logo-sub">RDS + ElastiCache Live Demo</div>
    </div>
  </div>
  <div class="health-bar">
    <div class="hpill pill-wait" id="rds-pill">● RDS</div>
    <div class="hpill pill-wait" id="redis-pill">● Redis</div>
    <button class="btn btn-yellow" style="padding:.3rem .8rem;font-size:.67rem" onclick="checkHealth()">↻ Refresh</button>
  </div>
</header>

<main>

  <!-- ANALOGY ROW -->
  <div class="card ot full" style="padding:1.1rem 1.4rem">
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.9rem">
      <div class="abox">
        <div class="aico">🏭</div>
        <div><div class="atitle">RDS MySQL</div>
        <div class="atext">The warehouse — complete & accurate, but takes time to fetch</div></div>
      </div>
      <div class="abox" style="border-color:#39d35333">
        <div class="aico">🛒</div>
        <div><div class="atitle" style="color:var(--green)">ElastiCache Redis</div>
        <div class="atext">The store shelf — right next to you, blazing fast, restocked by TTL</div></div>
      </div>
      <div class="abox" style="border-color:#58a6ff33">
        <div class="aico">🛍️</div>
        <div><div class="atitle" style="color:var(--blue)">Cache-Aside Pattern</div>
        <div class="atext">Check shelf first → HIT: fast ⚡ MISS: go warehouse, restock shelf</div></div>
      </div>
    </div>
  </div>

  <!-- LEFT: CACHE PANEL -->
  <div class="card gt">
    <div class="stitle">⚡ Request via Cache (ElastiCache → RDS)</div>
    <div class="irow">
      <label>Product ID:</label>
      <input type="number" id="cache-pid" value="1" min="1" max="20">
      <label style="margin-left:.4rem">All products</label>
      <input type="checkbox" id="cache-all">
    </div>
    <div class="btn-row">
      <button class="btn btn-cache" onclick="fetchViaCache()">⚡ Fetch via Cache</button>
      <button class="btn btn-danger" onclick="flushCache()" style="margin-left:auto">🗑️ Flush Cache</button>
    </div>
    <div id="cache-badge" style="margin-bottom:.5rem"></div>
    <div class="rpanel" id="cache-resp"><span class="empty">Click "Fetch via Cache" to see Cache-Aside in action</span></div>
    <div id="ttl-wrap" style="display:none;margin-top:.65rem">
      <div style="display:flex;justify-content:space-between;font-size:.67rem;color:var(--muted);font-family:'Space Mono',monospace">
        <span>Cache TTL remaining</span><span id="ttl-val"></span>
      </div>
      <div class="ttlwrap"><div class="ttlbar" id="ttl-bar" style="width:100%"></div></div>
    </div>
  </div>

  <!-- RIGHT: DIRECT DB PANEL -->
  <div class="card bt">
    <div class="stitle">🗄️ Hit RDS Directly (Bypass Cache)</div>
    <div class="irow">
      <label>Product ID:</label>
      <input type="number" id="db-pid" value="1" min="1" max="20">
      <label style="margin-left:.4rem">All products</label>
      <input type="checkbox" id="db-all">
    </div>
    <div class="btn-row">
      <button class="btn btn-db" onclick="fetchDirectDB()">🗄️ Hit DB Directly</button>
    </div>
    <div id="db-badge" style="margin-bottom:.5rem"></div>
    <div class="rpanel" id="db-resp"><span class="empty">Click "Hit DB Directly" to bypass cache and query RDS</span></div>
    <div class="warn-box">⚠️ This always hits RDS — no cache read or write. Compare latency with the cache panel!</div>
  </div>

  <!-- BENCHMARK -->
  <div class="card yt full">
    <div class="stitle">🚀 Benchmark — 5 Requests, Watch the Speedup</div>
    <div style="display:grid;grid-template-columns:220px 1fr;gap:1.5rem;align-items:start">
      <div>
        <div class="irow" style="margin-bottom:.75rem">
          <label>Product ID:</label>
          <input type="number" id="bench-pid" value="1" min="1" max="20" style="width:80px">
        </div>
        <button class="btn btn-yellow" onclick="runBenchmark()" style="width:100%;justify-content:center">▶ Run Benchmark</button>
        <div id="bench-summary" style="margin-top:.85rem"></div>
      </div>
      <div id="bench-results">
        <div class="empty">Run benchmark to see cache vs database latency comparison</div>
      </div>
    </div>
  </div>

  <!-- PRODUCT TABLE -->
  <div class="card ot full">
    <div class="stitle">📦 Product Catalog</div>
    <div class="btn-row">
      <button class="btn btn-cache" onclick="loadProducts('cache')">⚡ Load via Cache</button>
      <button class="btn btn-db"    onclick="loadProducts('direct')">🗄️ Load Direct from RDS</button>
      <div id="table-badge" style="margin-left:auto;align-self:center"></div>
    </div>
    <div style="overflow-x:auto;max-height:300px;overflow-y:auto">
      <div id="prod-wrap"><div class="empty">Click a button above to load products</div></div>
    </div>
  </div>

  <!-- CACHE STATS -->
  <div class="card gt">
    <div class="stitle">📊 Cache Stats</div>
    <div class="sgrid">
      <div class="sbox"><div class="sval sg" id="s-hits">—</div><div class="slbl">Cache Hits</div></div>
      <div class="sbox"><div class="sval sb" id="s-misses">—</div><div class="slbl">Cache Misses</div></div>
      <div class="sbox"><div class="sval so" id="s-rate">—</div><div class="slbl">Hit Rate</div></div>
      <div class="sbox"><div class="sval sg" id="s-keys">—</div><div class="slbl">Cached Keys</div></div>
      <div class="sbox"><div class="sval so" id="s-mem">—</div><div class="slbl">Memory Used</div></div>
      <div class="sbox"><div class="sval sb" id="s-ttl">60s</div><div class="slbl">TTL Config</div></div>
    </div>
    <button class="btn btn-cache" onclick="loadStats()" style="width:100%;justify-content:center">↻ Refresh Stats</button>
  </div>

  <!-- ACTIVITY LOG -->
  <div class="card bt">
    <div class="stitle">📋 Activity Log</div>
    <div class="logarea" id="log-area"><span class="empty">Requests will appear here...</span></div>
    <button class="btn btn-danger" onclick="clearLog()" style="width:100%;justify-content:center;margin-top:.75rem">Clear Log</button>
  </div>

</main>

<script>
const $=id=>document.getElementById(id);
let logs=[];

function ts(){return new Date().toLocaleTimeString('en-US',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});}

function addLog(type,msg){
  logs.unshift(`<span class="lts">[${ts()}]</span> <span class="l${type}">${msg}</span>`);
  if(logs.length>100)logs.pop();
  $('log-area').innerHTML=logs.join('<br>');
}

function fmtTime(ms){
  const c=ms<20?'tf':'ts';
  return `<span class="tchip ${c}">${ms} ms</span>`;
}

function makeBadge(d){
  if(d.bypass_cache) return `<span class="badge by">🗄️ DIRECT DB</span>${fmtTime(d.response_time_ms)}`;
  if(d.cache_hit)    return `<span class="badge bc">⚡ CACHE HIT</span>${fmtTime(d.response_time_ms)}`;
  return `<span class="badge bd">🗄️ CACHE MISS → DB</span>${fmtTime(d.response_time_ms)}`;
}

function colorJson(s){
  return s.replace(/"([^"]+)":/g,'<span style="color:#79c0ff">"$1"</span>:')
          .replace(/: "([^"]+)"/g,': <span style="color:#a5d6ff">"$1"</span>')
          .replace(/: (\d+\.?\d*)/g,': <span style="color:#f0883e">$1</span>')
          .replace(/: (true|false)/g,': <span style="color:#ff7b72">$1</span>');
}

async function checkHealth(){
  try{
    const d=await(await fetch('/health')).json();
    const rEl=$('rds-pill'), rcEl=$('redis-pill');
    rEl.className='hpill '+(d.rds==='ok'?'pill-ok':'pill-err');
    rEl.textContent='● RDS '+(d.rds==='ok'?'✓':'✗');
    rcEl.className='hpill '+(d.redis==='ok'?'pill-ok':'pill-err');
    rcEl.textContent='● Redis '+(d.redis==='ok'?'✓':'✗');
    addLog(d.rds==='ok'?'hit':'err',`Health: RDS=${d.rds}  Redis=${d.redis}`);
  }catch(e){addLog('err','Health check failed: '+e.message);}
}

async function fetchViaCache(){
  const all=$('cache-all').checked, pid=$('cache-pid').value;
  const url=all?'/products':`/products/${pid}`;
  $('cache-resp').innerHTML='<div class="spinner"></div> Checking Redis shelf...';
  $('cache-badge').innerHTML='';
  try{
    const d=await(await fetch(url)).json();
    $('cache-badge').innerHTML=makeBadge(d);
    const show=d.products||d.product||{};
    $('cache-resp').innerHTML=`<div style="margin-bottom:.45rem;font-size:.68rem;color:var(--muted)">source: <b style="color:${d.cache_hit?'var(--green)':'var(--blue)'}">${d.source}</b></div>${colorJson(JSON.stringify(show,null,2))}`;
    if(d.ttl_remaining_s!==undefined){
      $('ttl-wrap').style.display='block';
      $('ttl-val').textContent=d.ttl_remaining_s+'s';
      $('ttl-bar').style.width=Math.max(0,(d.ttl_remaining_s/60)*100)+'%';
    }
    const label=all?'all products':`product #${pid}`;
    addLog(d.cache_hit?'hit':'miss',d.cache_hit
      ?`⚡ CACHE HIT — ${label} in ${d.response_time_ms}ms`
      :`🗄️ CACHE MISS — ${label} from RDS in ${d.response_time_ms}ms → cached`);
  }catch(e){
    $('cache-resp').innerHTML=`<span style="color:var(--red)">Error: ${e.message}</span>`;
    addLog('err','Fetch via cache failed: '+e.message);
  }
}

async function fetchDirectDB(){
  const all=$('db-all').checked, pid=$('db-pid').value;
  const url=all?'/products/direct':`/products/${pid}/direct`;
  $('db-resp').innerHTML='<div class="spinner"></div> Querying RDS directly...';
  $('db-badge').innerHTML='';
  try{
    const d=await(await fetch(url)).json();
    $('db-badge').innerHTML=makeBadge(d);
    const show=d.products||d.product||{};
    $('db-resp').innerHTML=`<div style="margin-bottom:.45rem;font-size:.68rem;color:var(--muted)">source: <b style="color:var(--yellow)">direct RDS (cache bypassed)</b></div>${colorJson(JSON.stringify(show,null,2))}`;
    const label=all?'all products':`product #${pid}`;
    addLog('db',`🗄️ DIRECT DB — ${label} from RDS in ${d.response_time_ms}ms (cache bypassed)`);
  }catch(e){
    $('db-resp').innerHTML=`<span style="color:var(--red)">Error: ${e.message}</span>`;
    addLog('err','Direct DB fetch failed: '+e.message);
  }
}

async function flushCache(){
  try{
    const d=await(await fetch('/cache/flush',{method:'DELETE'})).json();
    addLog('flush',`🗑️ Cache flushed — ${d.keys_removed} keys removed. Next request hits RDS!`);
    $('cache-badge').innerHTML=`<span class="badge be">🗑️ FLUSHED — ${d.keys_removed} keys removed</span>`;
    $('ttl-wrap').style.display='none';
    loadStats();
  }catch(e){addLog('err','Flush failed: '+e.message);}
}

async function runBenchmark(){
  const pid=$('bench-pid').value;
  $('bench-results').innerHTML='<div class="spinner"></div> Running 5 requests...';
  $('bench-summary').innerHTML='';
  addLog('db','▶ Benchmark starting for product #'+pid);
  try{
    const d=await(await fetch(`/benchmark?product_id=${pid}`)).json();
    const maxT=Math.max(...d.results.map(x=>x.response_time_ms));
    let html='';
    d.results.forEach(row=>{
      const pct=maxT>0?(row.response_time_ms/maxT*100):0;
      const cls=row.cache_hit?'hit':'miss';
      const barCls=row.cache_hit?'bar-c':'bar-d';
      const srcLbl=row.cache_hit
        ?`<span style="color:var(--green);font-family:'Space Mono',monospace;font-size:.63rem;width:64px">⚡ cache</span>`
        :`<span style="color:var(--blue);font-family:'Space Mono',monospace;font-size:.63rem;width:64px">🗄️ db</span>`;
      html+=`<div class="brow ${cls}">
        <span class="bnum">#${row.request}</span>
        ${srcLbl}
        <div class="bwrap"><div class="bbar ${barCls}" style="width:${pct}%"></div></div>
        <span class="btime ${row.cache_hit?'tf':'ts'}">${row.response_time_ms}ms</span>
      </div>`;
    });
    $('bench-results').innerHTML=html;
    const s=d.summary;
    if(s.speedup!=='N/A'){
      $('bench-summary').innerHTML=`<div style="padding:.7rem;background:#39d35311;border:1px solid #39d35333;border-radius:8px;text-align:center">
        <div style="font-size:1.5rem;font-weight:800;color:var(--green);font-family:'Space Mono',monospace">${s.speedup}x faster</div>
        <div style="font-size:.67rem;color:var(--muted);margin-top:.2rem">with cache vs direct DB</div>
        <div style="font-size:.63rem;color:var(--muted);margin-top:.4rem">DB: ${s.avg_db_ms}ms → Cache: ${s.avg_cache_ms}ms</div>
      </div>`;
      addLog('hit',`🚀 Benchmark: Cache is ${s.speedup}x faster (${s.avg_db_ms}ms → ${s.avg_cache_ms}ms)`);
    }
  }catch(e){
    $('bench-results').innerHTML=`<span style="color:var(--red)">Error: ${e.message}</span>`;
    addLog('err','Benchmark failed: '+e.message);
  }
}

async function loadProducts(mode){
  const url=mode==='cache'?'/products':'/products/direct';
  $('prod-wrap').innerHTML='<div class="empty"><span class="spinner"></span> Loading...</div>';
  try{
    const d=await(await fetch(url)).json();
    const products=d.products||[];
    const badge=mode==='cache'
      ?(d.cache_hit?`<span class="badge bc">⚡ CACHE HIT</span>`:`<span class="badge bd">🗄️ CACHE MISS</span>`)
      :`<span class="badge by">🗄️ DIRECT DB</span>`;
    $('table-badge').innerHTML=badge+fmtTime(d.response_time_ms);
    if(!products.length){$('prod-wrap').innerHTML='<div class="empty">No products found</div>';return;}
    let html=`<table class="ptable"><thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th></tr></thead><tbody>`;
    products.forEach(p=>{
      html+=`<tr>
        <td style="color:var(--muted);font-family:'Space Mono',monospace">#${p.id}</td>
        <td>${p.name}</td>
        <td><span class="cpill">${p.category}</span></td>
        <td class="price">$${parseFloat(p.price).toFixed(2)}</td>
        <td style="color:${p.stock>50?'var(--green)':'var(--yellow)'}">${p.stock}</td>
      </tr>`;
    });
    html+='</tbody></table>';
    $('prod-wrap').innerHTML=html;
    addLog(mode==='cache'?(d.cache_hit?'hit':'miss'):'db',
      `📦 Products loaded via ${mode==='cache'?(d.cache_hit?'cache ⚡':'RDS+cached'):'direct RDS'} in ${d.response_time_ms}ms`);
  }catch(e){
    $('prod-wrap').innerHTML=`<div class="empty" style="color:var(--red)">Error: ${e.message}</div>`;
    addLog('err','Load products failed: '+e.message);
  }
}

async function loadStats(){
  try{
    const d=await(await fetch('/cache/stats')).json();
    $('s-hits').textContent=d.total_hits;
    $('s-misses').textContent=d.total_misses;
    $('s-rate').textContent=d.hit_rate_pct+'%';
    $('s-keys').textContent=d.cached_keys;
    $('s-mem').textContent=d.used_memory||'—';
  }catch(e){addLog('err','Stats load failed');}
}

function clearLog(){logs=[];$('log-area').innerHTML='<span class="empty">Log cleared</span>';}

window.addEventListener('DOMContentLoaded',()=>{
  checkHealth(); loadStats();
  setInterval(loadStats,10000);
  addLog('hit','🚀 Aviz Academy Demo Dashboard ready — Learn by Doing!');
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)