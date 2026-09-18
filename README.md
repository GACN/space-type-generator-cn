# 太空字体生成器 · 中文版

**SPACE TYPE GENERATOR — CN Edition**

离线可用的中文增强版，基于 [spacetypegenerator.com](https://spacetypegenerator.com) 构建。

23 个 p5.js 动态字体生成玩法，全中文界面 + 中文输入支持。

![preview](https://raw.githubusercontent.com/GACN/space-type-generator-cn/main/preview.png)

## 在线体验

GitHub Pages: **https://gacn.github.io/space-type-generator-cn/cn/index.html**

## 本地运行

```bash
# 克隆仓库
git clone https://github.com/GACN/space-type-generator-cn.git
cd space-type-generator-cn

# 启动本地服务（需要 HTTP，p5.js 字体加载不支持 file://）
cd cn
python3 -m http.server 8123

# 浏览器打开
# http://127.0.0.1:8123/index.html （圆柱体）
# http://127.0.0.1:8123/crash.html （坍塌 — 中文效果最佳）
```

## 中文支持情况

| 状态 | 玩法 |
|------|------|
| ✅ 完美 | 坍塌(CRASH)、爆破(POW)、坍塌时钟、容器(VESSEL)、弹扣(SNAP)、闪击(FLASH)、危险(DANGER)、构造(CONSTRUCT) |
| ⚠️ 仅UI | 圆柱体、字阵、条纹、线圈、旗面、森泽、瀑布、缎带、图层 |
| ⚠️ 部分 | 光耀、立体冲压、线绳、徽章、杂物、BoxSquad |

## 技术原理

核心补丁 `cn_font.js`（~12KB）：

1. **自动挂载中文字体** — 每次 `loadFont()` 后按字重自动挂载思源黑体（Noto Sans SC）
2. **按字符分流** — 改写 p5.Font 的 `_getPath`、`textToPoints`、`_textWidth` 方法，汉字走中文字体，其余走原字体
3. **opentype 补丁** — 同时补丁 `opentype.Font.prototype`，覆盖直接调用 opentype 的页面（shine/boost 等）

不改任何玩法源码，中英文可混排。

## 文件结构

```
cn/                          ← 中文版（可直接部署）
├── *.html                   ← 23 个玩法页面 + 中文说明
├── cn_font.js               ← 中文字形回退补丁（核心）
├── cn_resources/            ← 思源黑体 OTF 字体
├── cn_libs/                 ← 本地化依赖库（p5.js / jQuery / matter.js 等）
└── assets/                  ← 原版资源

build/                       ← 构建工具
├── build_cn.py              ← 构建脚本
├── cn_dict.py               ← 翻译词典
├── cn_font.js               ← 补丁源码
└── libmap.json              ← 依赖映射
```

## 致谢

本项目基于 **[Space Type Generator](https://spacetypegenerator.com)** 构建。

**原作者：[Kiel Mutschelknaus](http://www.kielm.com)**（[@kiel.d.m](https://www.instagram.com/kiel.d.m/)）

- 设计与编码：Kiel Mutschelknaus
- 许可证：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- 支持原作者：[Buy Me a Coffee](https://www.buymeacoffee.com/kieldm)

中文版在原作基础上增加了：
- 全中文界面（23 个玩法的导航、控件、标签）
- 中文字形回退系统（思源黑体 + p5/opentype 双层补丁）
- 离线运行支持（所有 CDN 依赖本地化）
- 中文默认展示文字

## License

[CC BY-NC-SA 4.0](LICENSE) — 与原作一致
