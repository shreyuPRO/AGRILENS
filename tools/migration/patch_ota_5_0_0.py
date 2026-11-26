#!/usr/bin/env python3
"""Apply the 5.0.0 OTA safety changes to deployment/ota/ota_update.sh (same changes as the in-app updater in application/main.py):
compile the downloaded main.py before replacing the model; keep a rollback copy of every replaced file in rollback/v<local version>/; add rollback.sh.
The GitHub source URL and the file layout seen by deployed kiosks are unchanged."""
import os
P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deployment", "ota", "ota_update.sh")
s = open(P, encoding="utf-8").read(); o = s


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]; s = s.replace(a, b)


rep('''    "setup_remote_ota.sh",
]''', '''    "setup_remote_ota.sh",
    "rollback.sh",
]''')
rep('''local_tuple = parse_ver(local_ver)
''', '''local_tuple = parse_ver(local_ver)
rollback_dir = os.path.join(app_dir, "rollback", f"v{local_ver}")

def backup_for_rollback(path):
    """Keeps a copy of the running version's file before it is replaced (first copy wins)."""
    try:
        if os.path.exists(path):
            import shutil
            dst = os.path.join(rollback_dir, os.path.relpath(path, app_dir))
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(path, dst)
    except Exception:
        pass
''')
rep('''    if rel == "main.py":
        text_src = data.decode("utf-8", errors="replace")''', '''    if rel == "main.py":
        # compile the downloaded main.py BEFORE the model (or anything else) is replaced
        chk = os.path.join(app_dir, "main.py.ota_check")
        with open(chk, "wb") as f_chk:
            f_chk.write(data)
        try:
            py_compile.compile(chk, doraise=True)
        finally:
            try:
                os.remove(chk)
            except Exception:
                pass
        text_src = data.decode("utf-8", errors="replace")''')
rep('''                    with open(m_tmp, "wb") as f_mout:
                        f_mout.write(m_data)
                    os.replace(m_tmp, model_dest)''', '''                    with open(m_tmp, "wb") as f_mout:
                        f_mout.write(m_data)
                    backup_for_rollback(model_dest)
                    os.replace(m_tmp, model_dest)''')
rep('''        if rel == "main.py":
            py_compile.compile(tmp, doraise=True)
        os.replace(tmp, dest)''', '''        if rel == "main.py":
            py_compile.compile(tmp, doraise=True)
        backup_for_rollback(dest)
        os.replace(tmp, dest)''')
rep('''force = (len(sys.argv) > 2 and sys.argv[2] == "--force")''', '''force = (len(sys.argv) > 2 and sys.argv[2] == "--force")
if os.path.exists(os.path.expanduser("~/.agrilens_ota_hold")) and not force:
    print("[AGRILENS OTA] On hold (~/.agrilens_ota_hold present, set by rollback.sh). Use --force or remove the file.")
    sys.exit(0)''')
open(P, "w", encoding="utf-8", newline="\n").write(s); print("patched", P)
