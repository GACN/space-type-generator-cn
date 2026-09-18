# -*- coding: utf-8 -*-
"""STG 中文版构建脚本
把 https://spacetypegenerator.com 的镜像（site/）构建成离线、全中文、支持中文输入的版本（cn/）。

做四件事：
  1. 依赖本地化：CDN 的 p5 / jQuery / matter.js / opentype / roundslider / Google 字体 → cn_libs/
  2. 界面汉化：HTML 文本、属性、选项、JS 字符串字面量 → 中文（词典见 cn_dict.py）
  3. 中文字形：注入 cn_font.js（给每个玩法挂思源黑体，汉字走中文字体，英文保持原字体）
  4. 导航汉化 + 中文说明书入口
"""
import os, re, json, html as H, shutil, sys

ARCH = "/storage/emulated/0/Music/每日归档/2026-09/SPACE_TYPE_GENERATOR"
SRC = ARCH + "/site"
CN = ARCH + "/cn"
BUILD = ARCH + "/build"
sys.path.insert(0, BUILD)
from cn_dict import UI, ART, NAV, PAGE_TITLES, DEFAULT_TITLE

LIBMAP = json.load(open(BUILD + "/libmap.json"))
DROP_HOSTS = ("googletagmanager.com", "cloudflareinsights.com")


# ----------------------------------------------------------------------------- 工具
def strip_analytics(t):
    t = re.sub(r'<script[^>]*(googletagmanager|cloudflareinsights)[^>]*>\s*</script>', '', t)
    t = re.sub(r'<!--\s*Global site tag.*?-->', '', t, flags=re.S)
    # 去掉内联 GA 初始化块
    t = re.sub(r'<script>\s*window\.dataLayer.*?gtag\(\'config\'[^;]*;\s*</script>', '', t, flags=re.S)
    return t


def localize_deps(t):
    for url, fn in LIBMAP.items():
        if url.rstrip('/') in ('https://fonts.gstatic.com',):
            continue
        t = t.replace(url, 'cn_libs/' + fn)
    t = re.sub(r'href=["\']https://fonts\.gstatic\.com["\'][^>]*>', '', t)
    return t


def balance_div(t, start):
    """从 <div ...> 起点找到配对的 </div> 结束位置（返回结束下标，含）"""
    i, depth = start, 0
    for m in re.finditer(r'<div\b|</div>', t[start:]):
        if m.group(0) == '</div>':
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    return -1


def cn_nav(current):
    items = []
    for key, en, cn in NAV:
        href = ('index.html' if key == 'index' else key + '.html')
        label = f'{cn} · {en}'
        style = ' style="font-weight:700"' if key == current else ''
        items.append(f'        <a href="{href}"{style}>{label}</a>')
    items.append('        <a href="guide.html">📖 中文使用说明</a>')
    return ('<div class="dropdown">\n'
            '      <button class="dropbtn">选择玩法…</button>\n'
            '      <div class="dropdown-content">\n' + '\n'.join(items) + '\n'
            '      </div>\n    </div>')


HELP_BADGE = ('<a href="guide.html" style="position:fixed;left:8px;bottom:6px;z-index:99999;'
              'font:11px/1.2 \'IBM Plex Mono\',monospace;color:#000;background:#fff;'
              'border:1px solid #000;padding:4px 7px;text-decoration:none;opacity:.7">中文说明</a>')


def translate_literal(s):
    """整串匹配（用于属性值 / JS 字面量）"""
    if s in ART:
        return ART[s]
    if s in UI:
        return UI[s]
    s2 = s.strip()
    if s2 in ART:
        return ART[s2]
    if s2 in UI:
        return UI[s2]
    return s


def translate_text_node(s):
    """文本节点：保留首尾空白，只翻译内容"""
    if not s.strip():
        return s
    core = s.strip()
    if core in ART:
        return s.replace(core, ART[core])
    if core in UI:
        return s.replace(core, UI[core])
    return s


def translate_html_body(t):
    # 保护 script/style/注释，只翻译其余部分的文本节点与属性
    guards = []

    def stash(m):
        guards.append(m.group(0))
        return f'\x00{len(guards)-1}\x00'

    t = re.sub(r'<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->', stash, t, flags=re.S)

    # 属性
    def attr_sub(m):
        name, val = m.group(1), m.group(2)
        return f'{name}="{translate_literal(val)}"'

    t = re.sub(r'\b(value|placeholder|title|alt|aria-label)="([^"]*)"', attr_sub, t)
    # 文本节点
    parts = re.split(r'(<[^>]+>)', t)
    for i, p in enumerate(parts):
        if p.startswith('<'):
            continue
        parts[i] = translate_text_node(p)
    t = ''.join(parts)

    def unstash(m):
        return guards[int(m.group(1))]

    t = re.sub(r'\x00(\d+)\x00', unstash, t)
    # 内联脚本里的可见文案（ReadMe 弹窗等）
    def script_sub(m):
        body = m.group(0)
        for k, v in list(UI.items()) + list(ART.items()):
            if len(k) >= 8 and k in body:
                body = body.replace(k, v)
        return body
    t = re.sub(r'<script\b(?![^>]*src).*?</script>', script_sub, t, flags=re.S)
    return t


def insert_cn_font_script(t):
    tags = list(re.finditer(r'<script[^>]*>\s*</script>|<script[^>]*/>', t))
    # 找最后一个已本地化的 p5 脚本标签
    target = None
    for m in re.finditer(r'<script[^>]*src=["\']([^"\']*p5[^"\']*)["\'][^>]*>\s*</script>', t):
        target = m
    if target is None:
        for m in re.finditer(r'<script[^>]*src=[^>]*>\s*</script>', t):
            target = m
    if target is None:
        return t
    ins = '\n    <script src="cn_font.js" type="text/javascript"></script>'
    return t[:target.end()] + ins + t[target.end():]


def ensure_viewport(t):
    if 'name="viewport"' in t:
        return t
    return t.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1">', 1)


# ----------------------------------------------------------------------------- 单页构建
def build_page(page_dir, key, en, cn):
    src = os.path.join(SRC, 'index' if page_dir == '.' else page_dir, "index.html")
    t = open(src, encoding='utf-8', errors='replace').read()

    t = strip_analytics(t)
    t = localize_deps(t)

    # 标题
    title = PAGE_TITLES.get(key, DEFAULT_TITLE.format(cn=cn, en=en))
    t = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', t, flags=re.S)

    # 导航
    m = re.search(r'<div class="dropdown">', t)
    if m:
        end = balance_div(t, m.start())
        if end > 0:
            t = t[:m.start()] + cn_nav(key) + t[end:]

    t = translate_html_body(t)
    t = insert_cn_font_script(t)
    t = ensure_viewport(t)
    t = t.replace('</body>', f'  {HELP_BADGE}\n</body>')

    out = os.path.join(CN, ('index.html' if key == 'index' else key + '.html'))
    open(out, 'w', encoding='utf-8').write(t)
    return out


# ----------------------------------------------------------------------------- JS 汉化
def translate_js(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    orig = t

    def lit_sub(m):
        q, val = m.group(1), m.group(2)
        if val in ART:
            return f'{q}{ART[val]}{q}'
        if val in UI and (len(val) >= 6 or val.isupper()):
            return f'{q}{UI[val]}{q}'
        return m.group(0)

    t = re.sub(r'(["\'])((?:(?!\1).){4,400}?)\1', lit_sub, t, flags=re.S)
    if t != orig:
        open(path, 'w', encoding='utf-8').write(t)
        return True
    return False


def main():
    # 1) 拷贝资源（保留相对目录结构）
    if os.path.exists(CN):
        for name in os.listdir(CN):
            if name in ('cn_libs', 'cn_resources'):
                continue
            p = os.path.join(CN, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    else:
        os.makedirs(CN)
    shutil.copytree(SRC + "/assets", CN, dirs_exist_ok=True)
    shutil.copy2(BUILD + "/cn_font.js", os.path.join(CN, "cn_font.js"))

    # 2) 页面
    built = []
    for key, en, cn in NAV:
        page_dir = 'index_root' if key == 'index' else key
        src_dir = SRC if key == 'index' else os.path.join(SRC, key)
        # 原站首页是 /index.html，其它是 /<name>/index.html
        if key == 'index':
            page_dir = '.'
        built.append(build_page(page_dir, key, en, cn))

    # 3) JS 汉化（跳过第三方库）
    skip = ('cn_libs', 'cn_font.js', 'CCapture.all.min.js', 'gif.worker.js')
    n_js = 0
    for dp, _, fs in os.walk(CN):
        if 'cn_libs' in dp:
            continue
        for f in fs:
            if not f.endswith('.js') or f in skip:
                continue
            if translate_js(os.path.join(dp, f)):
                n_js += 1
    print(f'构建完成：{len(built)} 个页面，{n_js} 个 JS 已汉化')
    for b in built:
        print('   ', b)


if __name__ == '__main__':
    main()
