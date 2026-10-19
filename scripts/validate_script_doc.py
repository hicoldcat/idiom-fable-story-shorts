#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_script_doc.py — 校验「成语/寓言 → 30 秒英语讲故事短视频」选题包。

用法::

    python validate_script_doc.py 成语寓言-20261019101530.md \
        --name-prefix 成语寓言 --min 55 --max 70

三级结论:
  PASS  合格
  WARN  参考提示 —— 不影响退出码
  FAIL  必须修复

FAIL 项（全部通过才返回退出码 0）:
  1. 文件名符合 ``<前缀>-<YYYYMMDDHHmmss>.md``（不含平台名），时间戳可解析
  2. 文档含「第一部分」「第二部分」
  3. 选题块恰好 N 个（默认 10）且序号连续
  4. **同一个成语 / 寓言不得重复出现**
  5. 总览表 N 行
  6. 每个选题必备字段齐全
  7. 英文旁白 55–70 词（硬性；``--loose-words`` 可降级为 WARN）
  8. 「单词数量（参考）」标注值与实测一致
  9. 英文旁白不得混入中文
 10. 核心单词 3–5 个（按 `｜` 计数）
 11. 中文旁白 ≥30 汉字；中文贴文 30–80 汉字；英文贴文 20–50 词
 12. 中文话题标签 5–8 个；英文话题标签 3–6 个
 13. 儿童吸引力分析存在且具体
 14. 未出现省略式表述

WARN 项（仅提示，不阻断交付）:
  - 英文旁白里出现疑似超纲难词（内置清单 + 长度 ≥13 字母）
  - 中文标题 > 26 汉字 / 英文标题 > 14 词
  - 标题出现低质标题党用词
  - 文档出现「第三部分」等额外章节

单词统计口径（与 content-spec 一致）:
  去掉 Markdown 标记后按空白切分，含字母或数字的 token 计 1 词；
  数字、缩写、带连字符的词各计 1 词。

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# 文本工具
# --------------------------------------------------------------------------- #

_PUNCT = re.compile(r"[\s\u3000()（）〔〕\[\]【】{}<>:：;；,，。.!！?？*_`~\-—–|/\\#「」『』]+")
_MD_STRIP = re.compile(r"[*_`>#\[\]()]+")
_WORDISH = re.compile(r"[A-Za-z0-9]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_TAG = re.compile(r"#[^\s#]+")
_QUOTED = re.compile(r"[「『]([^」』]+)[」』]")


def norm_key(s: str) -> str:
    """归一化一行文本，用于字段标记识别（去空白/标点/Markdown 装饰，转小写）。"""
    return _PUNCT.sub("", s).lower()


def count_words(s: str) -> int:
    """按统一口径统计英文词数。"""
    s = _MD_STRIP.sub(" ", s)
    return sum(1 for t in re.split(r"\s+", s) if _WORDISH.search(t))


def count_cjk(s: str) -> int:
    return len(_CJK.findall(s))


def count_tags(s: str) -> int:
    return len(_TAG.findall(s))


def strip_tags(s: str) -> str:
    return _TAG.sub(" ", s)


def count_vocab_items(s: str) -> int:
    """核心单词按 `｜` 分隔计数（兼容半角竖线）。"""
    return len([p for p in re.split(r"[｜|]", s) if p.strip()])


# --------------------------------------------------------------------------- #
# 字段标记（顺序 = 识别优先级）
# --------------------------------------------------------------------------- #

FIELD_DEFS = [
    ("zh_title", ["中文标题"]),
    ("en_title", ["englishtitle"]),
    ("source", ["故事出处"]),
    ("moral", ["故事与寓意"]),
    ("words", ["核心单词"]),
    ("en_vo", ["englishvoiceover"]),
    ("word_count", ["单词数量", "wordcount"]),
    ("zh_vo", ["中文旁白"]),
    ("zh_post", ["中文贴文"]),
    ("en_post", ["englishpost"]),
    ("zh_tags", ["中文话题标签"]),
    ("en_tags", ["英文话题标签"]),
    ("appeal", ["儿童吸引力分析"]),
]

FIELD_LABELS = {
    "zh_title": "中文标题",
    "en_title": "English Title",
    "source": "故事出处",
    "moral": "故事与寓意",
    "words": "核心单词",
    "en_vo": "英文旁白",
    "word_count": "单词数量（参考）",
    "zh_vo": "中文旁白",
    "zh_post": "中文贴文",
    "en_post": "English Post",
    "zh_tags": "中文话题标签",
    "en_tags": "英文话题标签",
    "appeal": "儿童吸引力分析",
}

TOPIC_RE = re.compile(r"^##\s*(?:选题|第)\s*(\d+)\s*集?\s*[:：]")
FILENAME_RE = re.compile(r"^(?P<prefix>.+?)-(?P<ts>\d{14})\.md$")
LEGACY_FILENAME_RE = re.compile(r"^(?P<prefix>.+?)-(?P<platform>[A-Za-z0-9_]+)-(?P<ts>\d{14})\.md$")
TABLE_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|")

# 疑似超纲词：出现即给 WARN（不阻断）。全部小写。
RARE_WORDS = {
    "approximately", "sufficient", "utilize", "demonstrate", "acquire", "perceive",
    "enormous", "transparent", "organism", "phenomenon", "photosynthesis", "buoyancy",
    "evaporation", "consequently", "nevertheless", "subsequently", "furthermore",
    "additionally", "magnificent", "extraordinary", "fundamental", "specifically",
    "essentially", "predominantly", "simultaneously", "instantaneously", "manipulate",
    "comprehend", "investigate", "accumulate", "transformation", "classification",
    "constellation", "thermodynamics", "electromagnetic", "biodiversity",
}

# 低质标题党用词（出现即 WARN）
CLICKBAIT = ["震惊", "吓傻", "吓哭", "万万没想到", "99%的人", "99％的人",
             "不转不是", "科学家都疯", "史上最", "绝对颠覆"]

ELISION_MARKERS = ["此处省略", "其余选题类似", "以下略", "略去", "同上，不再赘述"]


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #


def trailing_text(line: str) -> str:
    """取字段标记行中、最后一个 '**' 之后的正文（行内首段文字）。"""
    return line.rsplit("**", 1)[-1] if "**" in line else ""


def classify(line: str):
    """把一行判定为某个字段标记；返回 (field_key, 行内正文) 或 (None, None)。"""
    nk = norm_key(line)
    if not nk:
        return None, None
    for key, kws in FIELD_DEFS:
        if any(kw in nk for kw in kws):
            return key, trailing_text(line)
    return None, None


def split_topics(lines):
    """切出所有选题块。返回 [(num, heading, block_lines), ...]"""
    starts = []
    for i, line in enumerate(lines):
        m = TOPIC_RE.match(line.strip())
        if m:
            starts.append((i, int(m.group(1)), line.strip()))
    if not starts:
        return []

    cutoff = len(lines)
    for i in range(starts[0][0] + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("## ") and not TOPIC_RE.match(s):
            cutoff = i
            break

    blocks = []
    for i, (idx, num, heading) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else cutoff
        blocks.append((num, heading, lines[idx:min(end, cutoff)]))
    return blocks


def extract_fields(block_lines):
    """把选题块按字段切分，返回 {field_key: 正文文本}"""
    fields = {}
    current = None
    for line in block_lines[1:]:  # 跳过 "## 选题 N：..." 标题行本身
        key, rest = classify(line)
        if key:
            current = key
            fields.setdefault(key, [])
            if rest.strip():
                fields[key].append(rest)
        elif current:
            fields[current].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items()}


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #


PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


class Report:
    def __init__(self):
        self.items = []  # (level, scope, message)

    def add(self, ok: bool, scope: str, msg: str):
        self.add_level(PASS if ok else FAIL, scope, msg)

    def warn(self, scope: str, msg: str):
        self.add_level(WARN, scope, msg)

    def add_level(self, level: str, scope: str, msg: str):
        self.items.append((level, scope, msg))

    @property
    def failures(self):
        return [i for i in self.items if i[0] == FAIL]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == WARN]

    def render(self) -> str:
        out = []
        last_scope = None
        for level, scope, msg in self.items:
            if scope != last_scope:
                out.append(f"\n[{scope}]")
                last_scope = scope
            out.append(f"  {level:<4}  {msg}")
        return "\n".join(out)


def check_filename(path: Path, prefix, rep: Report):
    name = path.name

    legacy = LEGACY_FILENAME_RE.match(name)
    if legacy:
        rep.add(False, "文件名",
                f"文件名含平台名「{legacy.group('platform')}」：{name}；"
                f"规范要求 `<前缀>-<YYYYMMDDHHmmss>.md`，不含生成平台名称")
        return

    m = FILENAME_RE.match(name)
    if not m:
        hint = "（前缀里不要带 `-`）" if "-" in name else ""
        rep.add(False, "文件名", f"不符合 `<前缀>-<YYYYMMDDHHmmss>.md`：{name}{hint}")
        return

    ts = m.group("ts")
    try:
        dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
    except ValueError:
        rep.add(False, "文件名", f"时间戳无法解析为 YYYYMMDDHHmmss：{ts}")
        return
    if not (2000 <= dt.year <= 2100):
        rep.add(False, "文件名", f"时间戳年份异常：{dt.year}")
        return
    got = m.group("prefix")
    if prefix and got != prefix:
        rep.add(False, "文件名", f"文件名前缀「{got}」与期望「{prefix}」不符")
        return
    rep.add(True, "文件名", f"{name}（前缀={got} 时间={dt:%Y-%m-%d %H:%M:%S}）")


def check_overview(lines, want, rep: Report):
    rows = []
    for line in lines:
        m = TABLE_ROW_RE.match(line.strip())
        if m:
            rows.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    rep.add(len(rows) == want, "总览表", f"表格数据行 {len(rows)} 行（要求 {want}）")
    empty = [n for n, zh, en in rows if not zh or not en]
    rep.add(not empty, "总览表", "每行中英文标题都不为空" if not empty else f"第 {empty} 行标题为空")
    for num, zh, en in rows:
        if count_cjk(zh) > 26:
            rep.warn("总览表", f"第 {num} 条中文标题 {count_cjk(zh)} 汉字，超过建议上限 26")
        if count_words(en) > 14:
            rep.warn("总览表", f"第 {num} 条英文标题 {count_words(en)} 词，超过建议上限 14")


def check_vocab(text: str, num: int, rep: Report):
    """英文旁白难词启发式检查 —— 只给 WARN。"""
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']*", text)
    hits = []
    for t in tokens:
        low = t.lower().strip("-'")
        if low in RARE_WORDS or len(low) >= 13:
            hits.append(t)
    uniq = sorted({h for h in hits})
    if uniq:
        rep.warn(f"选题 {num}",
                 f"疑似超纲词 {len(uniq)} 个：{', '.join(uniq[:6])}"
                 f"（建议换成更常见的说法；若上下文能猜出可忽略）")


def check_topic(num, fields, lo, hi, rep: Report):
    scope = f"选题 {num}"

    missing = [k for k in FIELD_LABELS if k not in fields]
    rep.add(not missing, scope,
            "必备字段齐全" + (f"（缺失：{', '.join(FIELD_LABELS[k] for k in missing)}）" if missing else ""))
    if missing:
        return

    # 标题
    zh_title = fields["zh_title"].replace("\n", " ").strip()
    en_title = fields["en_title"].replace("\n", " ").strip()
    rep.add(bool(zh_title) and bool(en_title), scope, "中英文标题都不为空")

    # 标题长度与标题党
    zh_len = count_cjk(zh_title)
    if zh_len > 26:
        rep.warn(scope, f"中文标题 {zh_len} 汉字，超过建议上限 26")
    en_len = count_words(en_title)
    if en_len > 14:
        rep.warn(scope, f"英文标题 {en_len} 词，超过建议上限 14")
    bad = [w for w in CLICKBAIT if w in zh_title]
    if bad:
        rep.warn(scope, f"标题含低质标题党用词：{'、'.join(bad)}（夸张可以，别用这种）")

    # 核心单词 3–5 个
    n_items = count_vocab_items(fields["words"])
    rep.add(3 <= n_items <= 5, scope, f"核心单词 {n_items} 个（要求 3–5）")

    # 英文旁白词数：硬性区间
    n = count_words(fields["en_vo"])
    if lo <= n <= hi:
        rep.add(True, scope, f"英文旁白 {n} 词（要求 {lo}–{hi}）")
    else:
        rep.add_level(FAIL, scope, f"【词数】英文旁白 {n} 词，超出 {lo}–{hi} 区间")

    # 英文旁白混入中文
    rep.add(count_cjk(fields["en_vo"]) == 0, scope, "英文旁白未混入中文")

    # 词数标注
    m = re.search(r"(\d+)", fields["word_count"])
    if not m:
        rep.add(False, scope, "「单词数量（参考）」行缺少数字")
    else:
        declared = int(m.group(1))
        rep.add(declared == n, scope,
                f"词数标注 {declared} 与实测 {n} {'一致' if declared == n else '不一致'}")

    check_vocab(fields["en_vo"], num, rep)

    # 中文旁白
    zh_vo_cjk = count_cjk(fields["zh_vo"])
    rep.add(zh_vo_cjk >= 30, scope, f"中文旁白 {zh_vo_cjk} 汉字（要求 ≥30）")

    # 贴文
    zh_post_cjk = count_cjk(strip_tags(fields["zh_post"]))
    rep.add(30 <= zh_post_cjk <= 80, scope, f"中文贴文 {zh_post_cjk} 汉字（要求 30–80）")
    en_post_w = count_words(fields["en_post"])
    rep.add(20 <= en_post_w <= 50, scope, f"英文贴文 {en_post_w} 词（要求 20–50）")

    # 话题标签
    zh_t = count_tags(fields["zh_tags"])
    en_t = count_tags(fields["en_tags"])
    rep.add(5 <= zh_t <= 8, scope, f"中文话题标签 {zh_t} 个（要求 5–8）")
    rep.add(3 <= en_t <= 6, scope, f"英文话题标签 {en_t} 个（要求 3–6）")

    # 吸引力分析
    appeal = fields["appeal"].strip()
    rep.add(len(appeal) >= 10 and count_cjk(appeal) >= 8, scope, "儿童吸引力分析为一句具体说明")


def check_duplicates(blocks, rep: Report):
    """同一个成语 / 寓言不得出现两次。"""
    names = []
    for num, _h, block_lines in blocks:
        src = extract_fields(block_lines).get("source", "")
        found = _QUOTED.findall(src)
        names.append((num, found[0].strip() if found else None))

    missing = [n for n, nm in names if not nm]
    if missing:
        rep.add(False, "查重", f"第 {missing} 条的「故事出处」里没有用「」标出故事名")
        return

    seen = {}
    for num, nm in names:
        seen.setdefault(nm, []).append(num)
    repeated = {k: v for k, v in seen.items() if len(v) > 1}

    if repeated:
        detail = "；".join(f"「{k}」出现在选题 {v}" for k, v in repeated.items())
        rep.add(False, "查重", f"同一个成语 / 寓言重复使用：{detail}")
    else:
        rep.add(True, "查重", f"{len(names)} 个故事互不重复")


def validate(path: Path, want: int, lo: int, hi: int, prefix=None) -> Report:
    rep = Report()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    check_filename(path, prefix, rep)

    rep.add(len(text.strip()) > 0, "文件", f"文件大小 {path.stat().st_size} 字节")
    rep.add("第一部分" in text, "结构", "含「第一部分：10 个选题总览」")
    rep.add("第二部分" in text, "结构", "含「第二部分：10 个选题的完整内容」")

    blocks = split_topics(lines)
    rep.add(len(blocks) == want, "选题数", f"共 {len(blocks)} 个选题块（要求 {want}）")
    nums = [b[0] for b in blocks]
    rep.add(nums == list(range(1, want + 1)), "选题数", f"序号：{nums}")

    check_overview(lines, want, rep)
    check_duplicates(blocks, rep)

    for num, _heading, block_lines in blocks:
        check_topic(num, extract_fields(block_lines), lo, hi, rep)

    if "第三部分" in text:
        rep.warn("结构", "文档含「第三部分」——交付文档只保留第一部分与第二部分"
                         "（质量检查清单属执行者自检，不写入输出）")
    else:
        rep.add(True, "结构", "文档只含第一部分与第二部分")

    for marker in ELISION_MARKERS:
        rep.add(marker not in text, "结构", f"未出现省略式表述「{marker}」")

    return rep


def summary_table(path: Path) -> str:
    """生成每条选题的速览（便于人工核对）。"""
    blocks = split_topics(path.read_text(encoding="utf-8").splitlines())
    if not blocks:
        return ""
    out = ["\n=== 速览（选题 / 故事 / 词数 / 中文贴文字数）==="]
    for num, _h, block_lines in blocks:
        f = extract_fields(block_lines)
        name = (_QUOTED.findall(f.get("source", "")) or ["?"])[0]
        wc = count_words(f.get("en_vo", ""))
        post = count_cjk(strip_tags(f.get("zh_post", "")))
        flag = "OK " if 55 <= wc <= 70 else "!! "
        out.append(f"  {flag}{num:>2}. {name}｜{wc} words｜贴文 {post} 字")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="校验成语/寓言 → 30 秒英语故事短视频脚本 Markdown 文档")
    ap.add_argument("md_path", help="待校验的 .md 文件路径")
    ap.add_argument("--name-prefix", default="成语寓言",
                    help="文件名前缀（默认「成语寓言」；指定了主题时换成主题名）")
    ap.add_argument("--topics", type=int, default=10, help="要求的选题数量（默认 10）")
    ap.add_argument("--min", dest="lo", type=int, default=55,
                    help="英文旁白词数下限（默认 55，硬性）")
    ap.add_argument("--max", dest="hi", type=int, default=70,
                    help="英文旁白词数上限（默认 70，硬性）")
    ap.add_argument("--loose-words", action="store_true",
                    help="把词数越界从 FAIL 降级为 WARN（用于长版/短版需求）")
    ap.add_argument("--no-summary", action="store_true", help="不打印速览表")
    args = ap.parse_args(argv)

    path = Path(args.md_path)
    if not path.is_file():
        print(f"FAIL  文件不存在：{path}")
        return 1

    prefix = args.name_prefix

    rep = validate(path, args.topics, args.lo, args.hi, prefix)

    if args.loose_words:
        rep.items = [
            (WARN, s, m.replace("【词数】", "").replace("超出", "（--loose-words）超出"))
            if (lv == FAIL and "【词数】" in m) else (lv, s, m)
            for lv, s, m in rep.items
        ]

    print(f"=== 校验：{path.name} ===")
    print(rep.render())

    if not args.no_summary:
        print(summary_table(path))

    total = len(rep.items)
    fails = rep.failures
    warns = rep.warnings
    print(f"\n=== 结果：{total - len(fails) - len(warns)} PASS / {len(warns)} WARN / {len(fails)} FAIL"
          f"（共 {total} 项）===")
    if warns:
        print("参考提示（不阻断交付）：")
        for _lv, scope, msg in warns:
            print(f"  ~ [{scope}] {msg}")
    if fails:
        print("需要修复：")
        for _lv, scope, msg in fails:
            print(f"  - [{scope}] {msg}")
        print("\nVERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
