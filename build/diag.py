#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：打开页面，输出全部控制台信息 + p5 运行状态"""
import sys, os, json
from playwright.sync_api import sync_playwright
CHROME = "/data/data/com.termux/files/usr/bin/chromium-browser"
url = sys.argv[1]
WAIT = float(sys.argv[2]) if len(sys.argv) > 2 else 12
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=[
        "--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars",
        "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    pg.on("console", lambda m: print(f"[{m.type}] {m.text[:400]}"))
    pg.on("pageerror", lambda e: print("[pageerror]", str(e)[:600]))
    pg.on("requestfailed", lambda r: print("[reqfail]", r.url[:150], r.failure))
    pg.on("response", lambda r: print(f"[{r.status}]", r.url[:130]) if r.status >= 400 else None)
    pg.goto(url, wait_until="load", timeout=60000)
    pg.wait_for_timeout(int(WAIT*1000))
    st = pg.evaluate("""() => {
      const c = document.querySelector('canvas');
      let webgl = null;
      try { webgl = !!document.createElement('canvas').getContext('webgl'); } catch(e) { webgl = 'err'; }
      return {frameCount: (window.frameCount!==undefined?window.frameCount:null),
              canvas: c ? [c.width, c.height] : null,
              webgl, p5: typeof p5, setup: typeof setup, preload: typeof preload,
              fontsLoaded: (window.__STG_CN&&Object.keys(window.__STG_CN))||null,
              cnCount: (window.__STG_CN_CACHE?Object.keys(window.__STG_CN_CACHE):null)};
    }""")
    print("STATE:", json.dumps(st, ensure_ascii=False))
    b.close()
