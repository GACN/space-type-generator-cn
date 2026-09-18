#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文版验收工具：无头浏览器打开某个玩法页面，抓控制台报错 + 截图。
用法： python3 shot.py <页面名> [输出名] [宽] [高] [等待秒]
"""
import sys, os, json, time
from playwright.sync_api import sync_playwright

CN = "/storage/emulated/0/Music/每日归档/2026-09/SPACE_TYPE_GENERATOR/cn"
OUT = os.path.expanduser("~/stg_shots")
CHROME = "/data/data/com.termux/files/usr/bin/chromium-browser"
PORT = 8123

page = sys.argv[1] if len(sys.argv) > 1 else "index"
outname = sys.argv[2] if len(sys.argv) > 2 else f"shot_{page}.png"
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
H = int(sys.argv[4]) if len(sys.argv) > 4 else 900
WAIT = float(sys.argv[5]) if len(sys.argv) > 5 else 14

url = f"http://127.0.0.1:{PORT}/{(page + '.html') if page != 'index' else 'index.html'}"
logs, errs = [], []

with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path=CHROME,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars",
              "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
              "--disable-features=Vulkan"],
    )
    pg = b.new_page(viewport={"width": W, "height": H})
    pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:300]}"))
    pg.on("pageerror", lambda e: errs.append(str(e)[:400]))
    pg.goto(url, wait_until="load", timeout=60000)
    try:
        pg.wait_for_timeout(int(WAIT * 1000))
    except Exception:
        pass
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, outname)
    pg.screenshot(path=path)
    # 画布是否真的画了东西（非纯色）
    info = pg.evaluate("""() => {
      const c = document.querySelector('canvas');
      if (!c) return {canvas:false};
      let nonBlank = null, ctx = null;
      try {
        const tmp = document.createElement('canvas');
        tmp.width = Math.min(c.width, 300); tmp.height = Math.min(c.height, 300);
        tmp.getContext('2d').drawImage(c, 0, 0, tmp.width, tmp.height);
        const d = tmp.getContext('2d').getImageData(0,0,tmp.width,tmp.height).data;
        const seen = new Set();
        for (let i=0;i<d.length;i+=4) seen.add(d[i]+','+d[i+1]+','+d[i+2]);
        nonBlank = seen.size;
      } catch(e) { nonBlank = 'err:'+e.message; }
      return {canvas:true, w:c.width, h:c.height, colors:nonBlank,
              cnFonts: (window.__STG_CN_FONT_DEBUG||null)};
    }""")
    b.close()

print("URL:", url)
print("canvas:", json.dumps(info, ensure_ascii=False))
print("--- console (last 12) ---")
for l in logs:
    print("   ", l)
print("--- pageerror ---")
for e in errs:
    print("   ", e)
print("saved:", os.path.join(OUT, outname))
