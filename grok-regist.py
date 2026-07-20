#!/usr/bin/env python3
"""
grok-signup-local.py — Auto-register akun Grok (x.ai). 
Murni menggunakan turnstilePatch Lokal (Tanpa Capsolver) + Tambahan Fungsi 9Router.
Owner: Paizutempest
"""
import sys
import time
import re
import json
import os
import tempfile
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from colorama import init, Fore, Style

init(autoreset=True)

# ── Config (from .env) ────────────────────────────────────────
_env = {}
_envfile = Path(__file__).parent / '.env'
if _envfile.exists():
    for line in _envfile.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            _env[k.strip()] = v.strip()

def _env_or(key, default): return _env.get(key, default)

PASSWORD = _env_or('PASSWORD', 'change-me!')
TS_DIR   = Path('turnstilePatch').resolve()  # Folder turnstilePatch
OUT      = Path('sso.txt')
SIGNUP   = 'https://accounts.x.ai/sign-up?redirect=grok-com'
PAIZUMAILER = _env_or('PAIZUMAILER_URL', 'https://tempik.paizu.my.id') # change-me
DOMAINS  = _env_or('PAIZUMAILER_DOMAINS', 'paizu.my.id').split(',') # change-me
ROUTER9  = _env_or('ROUTER9_URL', 'http://localhost:portmu') # change-me
ROUTER9_PASS = _env_or('ROUTER9_PASS', 'change-me')

_domain_idx = 0
def next_domain():
    global _domain_idx
    d = DOMAINS[_domain_idx % len(DOMAINS)]
    _domain_idx += 1
    return d

def unlock_turnstile():
    if not (TS_DIR / 'script.js').exists() or not (TS_DIR / 'manifest.json').exists():
        raise RuntimeError(f"Missing turnstilePatch/script.js or manifest.json at {TS_DIR}")
    return str(TS_DIR)

# ── ANSI & Visual Branding ────────────────────────────────────
CYN = Fore.CYAN
GRN = Fore.GREEN
RED = Fore.RED
YEL = Fore.YELLOW
DIM = Style.DIM
RST = Style.RESET_ALL
SP = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
W = 74

def display_banner(current_ip="ROUTER_PROXY_LOCKED"):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.BLUE}{Style.BRIGHT}")
    print("     ██████╗ ██████╗  ██████╗ ██╗  ██╗     █████╗ ██╗")
    print("    ██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝    ██╔══██╗██║")
    print("    ██║  ███╗██████╔╝██║   ██║█████╔╝     ███████║██║")
    print("    ██║   ██║██╔══██╗██║   ██║██╔═██╗     ██╔══██║██║")
    print("    ╚██████╔╝██║  ██║╚██████╔╝██║  ██╗    ██║  ██║██║")
    print("     ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝")
    print(f"    META MODEL API - VISUAL DEBUG ENGINE v12.0")
    print(f"    Owner: Paizutempest | Gateway IP: [{current_ip}]")
    print(RST)

def log_line(tag, msg, tag_color=GRN):
    print(f"  {tag_color}│{RST} {tag_color}{tag:<6}{RST} {msg}")

def row(idx, email, step_n, step_msg, status, metric):
    print(f"  {DIM}{idx:<3}{RST} {email[:34]:<34} {CYN}[{step_n:02d}]{RST} {step_msg[:18]:<18} {status:<12} {DIM}{metric}{RST}")

def clear_line(): sys.stdout.write('\r\033[K'); sys.stdout.flush()

def wait(msg):  print(f"    {YEL}→{RST} {msg}")
def ok(msg):    print(f"    {GRN}✓{RST} {msg}")
def no(msg):    print(f"    {RED}✗{RST} {msg}")

# ── Temp Mail Client ──────────────────────────────────────────
class Mail:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({'Accept':'application/json','Content-Type':'application/json'})
    def create(self):
        sid = self.s.get(f'{PAIZUMAILER}/api/session', timeout=15).json()['sessionId']
        self.s.headers['x-session-id'] = sid
        self.domain = next_domain()
        r = self.s.post(f'{PAIZUMAILER}/api/inboxes', json={'domain':self.domain}, timeout=15)
        self.addr = r.json()['address']
        return self.addr
    def peek_code(self):
        try:
            msgs = self.s.get(f'{PAIZUMAILER}/api/inboxes/{self.addr}/messages', timeout=15).json() or []
            for m in msgs:
                for txt in (m.get('subject',''), m.get('body','')):
                    g = re.search(r'code:\s*([A-Z0-9]{3}-[A-Z0-9]{3})', txt, re.I)
                    if g: return g.group(1).replace('-','')
                    g = re.search(r'code:\s*([A-Z0-9]{6})', txt, re.I)
                    if g: return g.group(1)
        except: pass
        return None

# ── 9Router API Client ────────────────────────────────────────
class Router9:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({'Accept':'application/json','Content-Type':'application/json'})
    def login(self):
        try:
            r = self.s.post(f'{ROUTER9}/api/auth/login', json={'password':ROUTER9_PASS}, timeout=15)
            return r.json().get('success', False)
        except:
            return False
    def device_code(self):
        r = self.s.get(f'{ROUTER9}/api/oauth/grok-cli/device-code', timeout=10)
        return r.json()
    def poll(self, device_code, code_verifier):
        r = self.s.post(f'{ROUTER9}/api/oauth/grok-cli/poll',
                        json={'deviceCode': device_code, 'codeVerifier': code_verifier}, timeout=10)
        return r.json()
    def list_providers(self):
        r = self.s.get(f'{ROUTER9}/api/providers', timeout=15)
        conns = r.json().get('connections', [])
        return [c for c in conns if c.get('provider') == 'grok-cli']

# ── Fungsi Baru: Add Accounts to 9Router ──────────────────────
def add_to_router(accounts):
    print(f"\n {CYN}─── [ 9ROUTER ADD ] ──{'─'*(W-21)}{RST}")
    r9 = Router9()
    if not r9.login():
        no("9router login failed"); return
    ok("9router login authorized")
    existing = {c.get('email') for c in r9.list_providers()}
    ok(f"Existing profiles in 9router infrastructure: {len(existing)}")

    profile = str(Path(tempfile.gettempdir()) / f"grok-router-{int(time.time())}")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile, headless=False, channel='chrome',
            args=['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled',
                  '--window-size=1280,1024'],
            viewport={'width':1280,'height':1024},
            ignore_default_args=['--enable-automation'],
        )
        added = 0; skipped = 0; failed = 0
        for i, acc in enumerate(accounts):
            email = acc['email']
            print(f"\n  {DIM}[{i+1}/{len(accounts)}]{RST} {email}")
            if email in existing:
                wait("Account already registered, skipped")
                skipped += 1; continue
            try:
                pw_cookies = []
                for c in acc.get('sso_cookies', []):
                    cc = dict(c)
                    if not cc.get('domain'): continue
                    ss = cc.get('sameSite','Lax')
                    if ss not in ('Strict','Lax','None'): ss = 'Lax'
                    cc['sameSite'] = ss
                    pw_cookies.append(cc)
                ctx.clear_cookies()
                ctx.add_cookies(pw_cookies)
                
                d = r9.device_code()
                user_code = d['user_code']
                verify_url = d['verification_uri_complete']
                wait(f"User Code: {user_code}")
                
                page = ctx.new_page()
                page.goto(verify_url, wait_until='domcontentloaded', timeout=45000)
                time.sleep(3)
                
                has_login_input = page.evaluate("!!document.querySelector('input[type=email], input[type=password]')")
                if has_login_input:
                    no("SSO expired, need login")
                    page.close(); failed += 1; continue
                    
                try:
                    page.get_by_role('button', name='Continue', exact=False).click(timeout=5000)
                    clicked = 'continue'
                    time.sleep(3)
                except:
                    clicked = None
                    
                if clicked:
                    ok("Continue requested")
                    try:
                        page.get_by_role('button', name='Allow', exact=True).click(timeout=8000)
                        ok("Consent accepted")
                        time.sleep(2)
                    except:
                        try:
                            page.get_by_role('button', name='Allow All', exact=True).click(timeout=3000)
                            ok("Consent all accepted")
                            time.sleep(2)
                        except:
                            no("Consent submission button target omitted")
                            page.close(); failed += 1; continue
                time.sleep(3)
                page.close()
                
                for _ in range(60):
                    res = r9.poll(d['device_code'], d['codeVerifier'])
                    if res.get('success'):
                        ok("Profile successfully mapped inside 9router framework")
                        added += 1; break
                    elif not res.get('pending'):
                        no(f"Polling error context downstream: {res.get('error')}")
                        failed += 1; break
                    time.sleep(5)
                else:
                    no("Polling window constraint reached (5min limit)"); failed += 1
            except Exception as e:
                no(f"Execution error context: {e}"); failed += 1
        ctx.close()
    print(f"\n {CYN}─── [ 9ROUTER DONE ] ──{'─'*(W-21)}{RST}")
    print(f"  {GRN}added{RST}: {added}  {YEL}skipped{RST}: {skipped}  {RED}failed{RST}: {failed}")

# ── Main Runner ───────────────────────────────────────────────
def main():
    display_banner()
    args = sys.argv[1:]
    
    # Mode Tambahan: Ambil data dari sso.txt dan kirim langsung ke 9router jika argumen '--router' dilempar
    if args and args[0] == '--router':
        accounts = []
        if OUT.exists():
            with open(OUT) as f:
                for l in f:
                    if l.strip() and '"email"' in l:
                        try: accounts.append(json.loads(l))
                        except: pass
        if len(args) > 1:
            n = int(args[1])
            accounts = accounts[-n:]
        if not accounts:
            print(f"  {RED}✗{RST} No valid profiles discovered inside data index")
            return
        wait(f"Loaded {len(accounts)} registration profile items from store index")
        add_to_router(accounts)
        return

    count = int(args[0]) if args else 1
    t_start = time.time()
    
    try:
        ext_path = unlock_turnstile()
        log_line('LOAD', f"Hooked Patch Extension: {ext_path}", CYN)
    except Exception as e:
        log_line('FATAL', str(e), RED)
        return

    profile = str(Path(tempfile.gettempdir()) / f"grok-local-{int(time.time())}")
    results = []
    ok_n = 0; fail_n = 0
    log_lines = []

    with sync_playwright() as p:
        # Load ekstensi turnstilePatch lokal secara utuh ke browser context
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile, headless=False, channel='chrome',
            args=['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled',
                  '--window-size=1280,1024',
                  f'--load-extension={ext_path}',
                  f'--disable-extensions-except={ext_path}'],
            viewport={'width':1280,'height':1024},
            ignore_default_args=['--enable-automation'],
        )
        
        for i in range(count):
            t_acc = time.time()
            print(f"\n{CYN}─── [ RUNNING LOCAL BATCH: {i+1}/{count} ] ──{'─'*(W-30)}{RST}")
            try:
                res = run_one(ctx)
                results.append(res)
                ok_n += 1
                elapsed = f"{time.time()-t_acc:.1f}s"
                row(i+1, res['email'], 9, 'Completed', f"{GRN}SUCCESS{RST}", elapsed)
                log_lines.append((f"[{i+1:03d}] {res['email']} -> Operational ({elapsed})", GRN, 'DONE'))
            except Exception as e:
                fail_n += 1
                elapsed = f"{time.time()-t_acc:.1f}s"
                row(i+1, '— Pipeline Failure —', 0, 'Terminated', f"{RED}FAILED{RST}", elapsed)
                log_lines.append((f"[{i+1:03d}] Failure details: {e} ({elapsed})", RED, 'FAIL'))
                results.append({'error': str(e)})
            
            try: ctx.clear_cookies()
            except: pass
            print(f"  {DIM}[{ok_n}✓ {fail_n}×]  Remaining queue: {count-i-1}  | Total runtime: {int(time.time()-t_start)}s{RST}")
            
        ctx.close()

    print(f"\n {CYN}┌── [ SYSTEM LOGS ] ──{'─'*(W-21)}{RST}")
    for msg, color, tag in log_lines:
        print(f" {CYN}│{RST} {color}{tag:<6}{RST} {msg}")
    print(f" {CYN}└{'─'*(W-2)}{RST}")
    
    # Prompt Tambahan: Eksekusi sinkronisasi otomatis ke 9Router di akhir batch loop jika ada akun sukses
    success_accs = [r for r in results if 'email' in r]
    if success_accs:
        print()
        try:
            ans = input(f"  {YEL}?{RST} Forward data streams directly into the 9Router Engine framework clusters? [y/N] ").strip().lower()
        except EOFError:
            ans = ''
        if ans == 'y':
            add_to_router(success_accs)

def run_one(ctx):
    page = ctx.new_page()
    page.set_extra_http_headers({'accept-language': 'en-US,en;q=0.9'})
    
    # [1] Open page
    log_line('STEP 01', 'Loading x.ai primary endpoint...')
    page.goto(SIGNUP, wait_until='domcontentloaded', timeout=45000)
    time.sleep(2)
    try: page.get_by_role('button', name='Accept All Cookies').click(timeout=2000)
    except: pass

    # [2] Click Sign up with email
    log_line('STEP 02', 'Initializing email signup entry hook')
    page.get_by_text('Sign up with email').click(timeout=8000)
    page.wait_for_selector('input[type=email]', timeout=8000)

    # [3] Create Mail
    log_line('STEP 03', 'Provisioning fresh temp target address structural space')
    mail = Mail()
    addr = mail.create()
    log_line('MAIL', f"{addr}", YEL)
    page.locator('input[type=email]').fill(addr)
    page.locator('input[type=email]').press('Enter')
    
    try:
        page.wait_for_selector('input[name=code]', timeout=20000)
    except:
        page.get_by_role('button', name='Sign up').click(timeout=3000)
        page.wait_for_selector('input[name=code]', timeout=15000)

    # [4] Wait OTP
    log_line('STEP 04', 'Intercepting inbound security payload channel matrices...')
    t = time.time()
    sp_idx = 0
    code = None
    while time.time() - t < 120:
        code = mail.peek_code()
        if code: break
        sys.stdout.write(f"\r    {CYN}{SP[sp_idx % len(SP)]}{RST} listening verification data buffers: {int(time.time()-t)}s")
        sys.stdout.flush()
        sp_idx += 1
        time.sleep(0.4)
    clear_line()
    if not code: raise RuntimeError("Verification buffer processing failure (OTP Timeout)")
    log_line('OTP', f"Payload match acquired: {code}", GRN)

    # [5] Submit OTP
    log_line('STEP 05', 'Injecting code sequence token into target context frame')
    page.locator('input[name=code]').first.fill(code, timeout=15000)
    time.sleep(2)
    page.keyboard.press('Enter')
    page.wait_for_selector('input[name=givenName]', timeout=20000)

    # [6] Await Local Turnstile Auto-Remediation (Murni mengandalkan ekstensi turnstilePatch)
    log_line('STEP 07', 'Awaiting local turnstilePatch extension remediation...')
    tok = ''
    for i in range(45):
        tok = page.evaluate("document.querySelector('input[name=cf-turnstile-response]')?.value || ''")
        if tok: 
            break
        if i % 10 == 9:
            log_line('WAIT', f"Extension working on cloudflare parameters ({i+1}s)...", YEL)
        time.sleep(1)
        
    if not tok:
        raise RuntimeError("Local patch extension bypassed standard verification timeout windows")
    log_line('PATCH', 'Turnstile token structural bypass matched locally', GRN)

    # [7] Fill Form (Diisi setelah token local ready agar aman)
    log_line('STEP 06', 'Structuring placeholder metadata identity profile blocks')
    local_part = addr.split('@')[0]
    parts = re.split(r'[._\-]', local_part)
    given = parts[0].capitalize()
    family = parts[1].capitalize() if len(parts) > 1 else 'Xyz'
    
    page.locator('input[name=givenName]').fill(given)
    page.locator('input[name=familyName]').fill(family)
    page.locator('input[name=password]').fill(PASSWORD)
    
    page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[name="givenName"], input[name="familyName"], input[name="password"]');
        inputs.forEach(input => {
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.dispatchEvent(new Event('blur', { bubbles: true }));
        });
    }""")
    time.sleep(1)

    # [SUBMIT] Dispatch Complete Sign Up Event
    log_line('SUBMIT', 'Executing final registration dispatch event...')
    try:
        page.get_by_role('button', name='Complete sign up').click(force=True, timeout=5000)
    except:
        page.evaluate("""() => {
            const submitBtn = document.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.click();
        }""")

    # [8] Redirect Verification Matrix (Optimized with Duplication Interrupter)
    log_line('STEP 08', 'Validating final redirection pipeline endpoints')
    success_redirect = False
    last_body = ""
    for _ in range(30):
        time.sleep(2)
        try: url = page.url
        except: continue
        
        if 'grok.com' in url:
            log_line('REDIRECT', f"→ {url}", GRN)
            success_redirect = True
            break
            
        try:
            txt = page.evaluate("document.body.innerText")
            
            # PROTEKSI UTAMA: Deteksi jika email sudah terdaftar (Existing Account Found)
            if "already exists" in txt.lower() or "associated with this email" in txt.lower():
                log_line('ALERT', 'Email already associated with an existing x.ai account!', RED)
                raise RuntimeError("Existing account detected - Bouncing to next queue item")
                
            for err in ['too weak','already','invalid','try again','failed']:
                if err.lower() in txt.lower() and err not in last_body:
                    log_line('ALERT', f"Platform processing notification triggered: ...{err}...", RED)
            last_body = txt
        except Exception as dom_err:
            if "Bouncing to next queue item" in str(dom_err):
                raise dom_err
            pass

    if not success_redirect:
        sso = [c for c in page.context.cookies() if 'sso' in c.get('name','').lower()]
        if sso: log_line('WARN', 'Active session state cookie validated anyway.', YEL)
        else: raise RuntimeError(f"State alignment aborted. Stuck at: {page.url}")

    # [9] Save Credentials
    log_line('STEP 09', 'Writing credentials payload record to local disk structure')
    data = {
        'email': addr, 'password': PASSWORD, 'code': code,
        'sso_cookies': page.context.cookies(), 'final_url': page.url,
        'timestamp': int(time.time()),
    }
    with open(OUT, 'a') as f:
        f.write(json.dumps(data) + '\n')
    log_line('SAVED', f"Stored structural output record -> {OUT.name}", GRN)
    return data

if __name__ == '__main__':
    main()
