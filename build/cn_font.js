/* ==========================================================================
   STG 中文版 · 中文字形回退补丁  cn_font.js
   --------------------------------------------------------------------------
   原版 23 个玩法加载的都是「只有拉丁字形」的字体（Inter / Extenda / IBM Plex…），
   直接输入中文会渲染成方框或空白。这个补丁做两件事：

     1. 每次 loadFont() 之后，按原字体的字重自动再挂一款中文字体（思源黑体 / Noto Sans SC）
        Thin → Thin、Bold/Heavy → Bold、Black → Black、其余 → Regular
     2. 接管 p5.Font 的三个关键方法，按「字符」分流：
        汉字/中文标点 → 中文字体，其余 → 原字体
        · _getPath        取字形轮廓（text() 矢量绘制走这里）
        · textToPoints    取轮廓采样点（POW / CRASH / VESSEL 等物理玩法走这里）
        · _textWidth      量字宽（自动适应字号走这里）
        · textBounds      量包围盒

   所以：不改任何玩法源码，中英文可以混排。中文用思源黑体，英文保持原字体风格。
   p5 2.x（BoxSquad）走的是 Canvas 文本，这里额外追加 "STG CN" 字体族兜底。
   ========================================================================== */
(function () {
  'use strict';

  if (typeof window === 'undefined') return;

  var CN_DIR = 'cn_resources/';
  var WEIGHTS = {
    thin: 'NotoSansSC-Thin.otf',
    regular: 'NotoSansSC-Regular.otf',
    bold: 'NotoSansSC-Bold.otf',
    black: 'NotoSansSC-Black.otf'
  };
  // 一个字体族名，供 p5 2.x / Canvas 文本回退使用
  var CN_CSS_FAMILY = 'STG CN';

  var HAS_CJK = /[\u2e80-\u303f\u3040-\u30ff\u31c0-\u33ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef\u3000-\u303f]/;
  function isCJKChar(ch) { return HAS_CJK.test(ch); }

  /* 按原字体文件名猜字重，给中文选一款粗细相近的，混排时视觉更统一 */
  function pickWeight(path) {
    var s = String(path || '');
    if (/Thin|Hairline|ExtraLight|Extra-Light|Light|Lt\b|45Lt/i.test(s)) return 'thin';
    if (/Black|Blk|Heavy|95/i.test(s)) return 'black';
    if (/Bold|-Bd|SemiBold|Semi-Bd/i.test(s)) return 'bold';
    return 'regular';
  }

  // ---- 中文字体缓存：同一字重只加载一次 ----
  var CN_CACHE = {};

  function loadCN(inst, weight, onReady) {
    var entry = CN_CACHE[weight];
    if (!entry) {
      entry = CN_CACHE[weight] = { font: null, waiting: [] };
      var file = CN_DIR + (WEIGHTS[weight] || WEIGHTS.regular);
      _loadFont.call(inst, file, function (f) {
        entry.font = f;
        entry.waiting.splice(0).forEach(function (cb) { try { cb(); } catch (e) {} });
      }, function () {
        console.warn('[STG中文版] 中文字体加载失败：' + file);
        entry.waiting.splice(0).forEach(function (cb) { try { cb(); } catch (e) {} });
      });
    }
    if (entry.font) onReady();
    else entry.waiting.push(onReady);
  }

  /* 按字符切段：连续的汉字为一段，连续的非汉字为一段 */
  function splitRuns(str) {
    var runs = [], cur = '', curIsCN = null, ch, flag, i;
    for (i = 0; i < str.length; i++) {
      ch = str.charAt(i);
      flag = isCJKChar(ch);
      if (curIsCN === null || flag === curIsCN) { cur += ch; curIsCN = flag; }
      else { runs.push({ text: cur, cn: curIsCN }); cur = ch; curIsCN = flag; }
    }
    if (cur) runs.push({ text: cur, cn: curIsCN });
    return runs;
  }

  // ======================  p5 1.x 分支  ======================
  function patchP5v1() {
    var F = p5.Font && p5.Font.prototype;
    if (!F || typeof F._getPath !== 'function') return false;

    var _getPath = F._getPath;
    var _textWidth = F._textWidth;
    var _textToPoints = F.textToPoints;
    var _textBounds = F.textBounds;
    var LEFT = (p5.LEFT || 'left');
    var ALPHABETIC = (p5.BASELINE || 'alphabetic');

    /* 取字形轮廓：逐段生成路径再合并（合并后的 commands 与 p5 原生结构一致） */
    F._getPath = function (line, x, y, options) {
      if (!this.__cn || typeof line !== 'string' || !HAS_CJK.test(line)) {
        return _getPath.apply(this, arguments);
      }
      var renderer = (options && options.renderer && options.renderer._pInst
        && options.renderer._pInst._renderer) || (options && options.renderer) || this.parent._renderer;
      var savedAlign = renderer._textAlign, savedBase = renderer._textBaseline;
      var runs = splitRuns(line);
      var total = 0, i, r, f;
      for (i = 0; i < runs.length; i++) {
        f = runs[i].cn ? this.__cn : this;
        total += _textWidth.call(f, runs[i].text, renderer._textSize);
      }
      // 先按整体宽度算好对齐起点，再强制左对齐逐段绘制，避免每段各自居中
      var origin = this._handleAlignment(renderer, line, x, y, total);
      renderer._textAlign = LEFT;
      renderer._textBaseline = ALPHABETIC;
      var px = origin.x, merged = [];
      try {
        for (i = 0; i < runs.length; i++) {
          r = runs[i];
          f = r.cn ? this.__cn : this;
          var p = _getPath.call(f, r.text, px, origin.y, options);
          if (p && p.commands) merged = merged.concat(p.commands);
          px += _textWidth.call(f, r.text, renderer._textSize);
        }
      } finally {
        renderer._textAlign = savedAlign;
        renderer._textBaseline = savedBase;
      }
      return { commands: merged };
    };

    /* 量字宽：逐段相加，保证自动适应字号/居中定位在中文下也准确 */
    F._textWidth = function (str, fontSize) {
      if (!this.__cn || typeof str !== 'string' || !HAS_CJK.test(str)) {
        return _textWidth.apply(this, arguments);
      }
      var runs = splitRuns(str), w = 0, i;
      for (i = 0; i < runs.length; i++) {
        w += _textWidth.call(runs[i].cn ? this.__cn : this, runs[i].text, fontSize);
      }
      return w;
    };

    /* 取轮廓采样点：POW / CRASH / CRASH CLOCK / VESSEL 的物理字母走这条路径 */
    F.textToPoints = function (txt, x, y, fontSize, options) {
      if (!this.__cn || typeof txt !== 'string' || !HAS_CJK.test(txt)) {
        return _textToPoints.apply(this, arguments);
      }
      var runs = splitRuns(txt), res = [], xoff = 0, i;
      for (i = 0; i < runs.length; i++) {
        var r = runs[i];
        var f = r.cn ? this.__cn : this;
        var pts = _textToPoints.call(f, r.text, x + xoff, y, fontSize, options);
        if (pts && pts.length) res = res.concat(pts);
        xoff += _textWidth.call(f, r.text, fontSize);
      }
      return res;
    };

    /* 包围盒：合并各段结果 */
    if (typeof _textBounds === 'function') {
      F.textBounds = function (str) {
        if (!this.__cn || typeof str !== 'string' || !HAS_CJK.test(str)) {
          return _textBounds.apply(this, arguments);
        }
        var args = Array.prototype.slice.call(arguments);
        var x = args.length > 1 ? args[1] : 0, y = args.length > 2 ? args[2] : 0,
          fontSize = args.length > 3 ? args[3] : undefined, opts = args.length > 4 ? args[4] : undefined;
        var p = (opts && opts.renderer && opts.renderer._pInst) || this.parent;
        var renderer = p._renderer;
        var fs = fontSize || renderer._textSize;
        var savedAlign = renderer._textAlign, savedBase = renderer._textBaseline;
        renderer._textAlign = LEFT; renderer._textBaseline = ALPHABETIC;
        var runs = splitRuns(str), px = x, minX = Infinity, minY = Infinity,
          maxX = -Infinity, maxY = -Infinity, total = 0, i, r, f, b;
        try {
          for (i = 0; i < runs.length; i++) {
            r = runs[i]; f = r.cn ? this.__cn : this;
            b = _textBounds.call(f, r.text, px, y, fs, opts);
            minX = Math.min(minX, b.x); minY = Math.min(minY, b.y);
            maxX = Math.max(maxX, b.x + b.w); maxY = Math.max(maxY, b.y + b.h);
            px += _textWidth.call(f, r.text, fs);
            total += _textWidth.call(f, r.text, fs);
          }
        } finally {
          renderer._textAlign = savedAlign; renderer._textBaseline = savedBase;
        }
        var pos = this._handleAlignment(renderer, str, minX, minY, total);
        return { x: pos.x, y: pos.y, w: maxX - minX, h: maxY - minY, advance: minX - x };
      };
    }
    return true;
  }

  // ======================  p5 2.x 分支（BoxSquad） ======================
  function patchP5v2() {
    var proto = (p5.Renderer2D && p5.Renderer2D.prototype) || (p5.Renderer && p5.Renderer.prototype);
    if (!proto || typeof proto._currentTextFont !== 'function') return false;
    var _cur = proto._currentTextFont;
    proto._currentTextFont = function () {
      var f = _cur.call(this);
      if (typeof f === 'string' && f.indexOf(CN_CSS_FAMILY) === -1) {
        return f + ', "' + CN_CSS_FAMILY + '", sans-serif';
      }
      return f;
    };
    return true;
  }

  // ======================  opentype.js 直接调用补丁（shine / boost / string / 徽章） ======================
  function patchOpentype() {
    if (typeof opentype === 'undefined' || !opentype.Font || !opentype.Font.prototype) return false;
    var OF = opentype.Font.prototype;
    var _otGetPath = OF.getPath;
    var _otGetWidth = OF.getAdvanceWidth;
    var _otStringToGlyphs = OF.stringToGlyphs;

    function cnFont() {
      // 取第一个已加载的中文字体的 opentype 对象
      for (var w in CN_CACHE) {
        if (CN_CACHE[w] && CN_CACHE[w].font && CN_CACHE[w].font.font) return CN_CACHE[w].font.font;
      }
      return null;
    }

    /* getPath: 逐段生成路径再合并 */
    OF.getPath = function (text, x, y, fontSize, options) {
      if (typeof text !== 'string' || !HAS_CJK.test(text)) return _otGetPath.apply(this, arguments);
      var cn = cnFont();
      if (!cn) return _otGetPath.apply(this, arguments);
      var runs = splitRuns(text), px = x, merged = [];
      for (var i = 0; i < runs.length; i++) {
        var r = runs[i];
        var f = r.cn ? cn : this;
        var p = _otGetPath.call(f, r.text, px, y, fontSize, options);
        if (p && p.commands) merged = merged.concat(p.commands);
        px += _otGetWidth.call(f, r.text, fontSize, options);
      }
      // 返回 opentype Path 对象
      return { commands: merged };
    };

    /* getAdvanceWidth: 逐段相加 */
    OF.getAdvanceWidth = function (text, fontSize, options) {
      if (typeof text !== 'string' || !HAS_CJK.test(text)) return _otGetWidth.apply(this, arguments);
      var cn = cnFont();
      if (!cn) return _otGetWidth.apply(this, arguments);
      var w = 0, runs = splitRuns(text);
      for (var i = 0; i < runs.length; i++) {
        var f = runs[i].cn ? cn : this;
        w += _otGetWidth.call(f, runs[i].text, fontSize, options);
      }
      return w;
    };

    /* stringToGlyphs: 逐段合并 glyph 数组 */
    OF.stringToGlyphs = function (text) {
      if (typeof text !== 'string' || !HAS_CJK.test(text)) return _otStringToGlyphs.apply(this, arguments);
      var cn = cnFont();
      if (!cn) return _otStringToGlyphs.apply(this, arguments);
      var runs = splitRuns(text), all = [];
      for (var i = 0; i < runs.length; i++) {
        var f = runs[i].cn ? cn : this;
        all = all.concat(_otStringToGlyphs.call(f, runs[i].text));
      }
      return all;
    };
    return true;
  }

  function injectCSSFamily() {
    var style = document.createElement('style');
    style.textContent =
      '@font-face{font-family:"' + CN_CSS_FAMILY + '";' +
      'src:url("' + CN_DIR + 'NotoSansSC-Regular.otf") format("opentype");' +
      'font-display:swap;}';
    (document.head || document.documentElement).appendChild(style);
  }

  // ======================  启动：接管 loadFont  ======================
  var _loadFont = null;

  function boot() {
    if (typeof p5 === 'undefined' || !p5.prototype || !p5.Font || typeof p5.prototype.loadFont !== 'function') {
      console.warn('[STG中文版] 未检测到 p5，中文回退补丁未生效');
      return;
    }
    _loadFont = p5.prototype.loadFont;

    p5.prototype.loadFont = function (path, onSuccess, onError) {
      var self = this;
      var isCN = /NotoSansSC|SourceHan|cn_resources/.test(String(path || ''));
      var p5Font = _loadFont.call(this, path, function (f) { if (onSuccess) onSuccess(f); }, onError);

      if (!isCN && window.__STG_CN_DISABLE !== true) {
        var weight = pickWeight(path);
        var blocking = typeof self._incrementPreload === 'function';
        if (blocking) self._incrementPreload();
        loadCN(self, weight, function () {
          if (p5Font) p5Font.__cn = CN_CACHE[weight].font;
          if (blocking && typeof self._decrementPreload === 'function') self._decrementPreload();
        });
      }
      return p5Font;
    };

    var ok1 = patchP5v1();
    var ok2 = patchP5v2();
    var ok3 = patchOpentype();
    injectCSSFamily();
    console.log('[STG中文版] 中文回退补丁已生效  p5.Font=' + ok1 + '  Canvas=' + ok2 + '  opentype=' + ok3);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
