#!/usr/bin/env python3
# Display name: Dice
# 显示名称：掷骰子
# Description: Roll dice written in dice notation, such as 1d6, 3d6+2, 2d20kh1 or 4d6dl1, and return every face and the total.
# 描述：掷骰子：照 3d6+2、2d20kh1 这样的写法掷，交回每一颗和总数。
# Timeout: 10
# Need load: no
# Clicall: yes
# Parameters:
# {"type": "object", "properties": {
#   "dice": {"type": "string", "description": "Dice notation. Terms joined by + or -: NdM (d% is d100), a plain number, and after NdM optionally khK/klK (keep highest/lowest K) or dhK/dlK (drop highest/lowest K). Default 1d6."},
#   "repeat": {"type": "integer", "description": "Roll the whole expression this many times, 1-20. Default 1."},
#   "label": {"type": "string", "description": "What the roll is for; echoed back."}
# }}
import json
import re
import secrets
import sys

MAX_DICE = 100
MAX_SIDES = 1000
MAX_REPEAT = 20

TERM = re.compile(r"([+-]?)(?:(\d*)d(\d+|%)(?:(kh|kl|dh|dl)(\d+))?|(\d+))", re.I)
rng = secrets.SystemRandom()


def fail(message):
    print(f"错误：{message}")
    sys.exit(1)


def parse(text):
    expr = re.sub(r"\s+", "", text).lower()
    if not expr:
        fail("dice 是空的，例：3d6+2")
    terms = []
    pos = 0
    while pos < len(expr):
        match = TERM.match(expr, pos)
        if not match or match.end() == pos or (pos > 0 and not match.group(1)):
            fail(f"看不懂「{text}」第 {pos + 1} 个字起的部分，例：3d6+2、2d20kh1、4d6dl1")
        sign = -1 if match.group(1) == "-" else 1
        if match.group(6) is not None:
            terms.append({"sign": sign, "const": int(match.group(6))})
        else:
            count = int(match.group(2) or 1)
            sides = 100 if match.group(3) == "%" else int(match.group(3))
            mode, keep = match.group(4), int(match.group(5) or 0)
            if not 1 <= count <= MAX_DICE:
                fail(f"一项至多 {MAX_DICE} 颗骰子：{match.group(0)}")
            if not 2 <= sides <= MAX_SIDES:
                fail(f"骰子的面数要在 2 到 {MAX_SIDES} 之间：{match.group(0)}")
            if mode and not 1 <= keep <= count:
                fail(f"{mode}{keep} 超出了这一项的 {count} 颗：{match.group(0)}")
            terms.append({"sign": sign, "count": count, "sides": sides, "mode": mode, "keep": keep})
        pos = match.end()
    if sum(t.get("count", 0) for t in terms) > MAX_DICE:
        fail(f"一次至多 {MAX_DICE} 颗骰子")
    return terms


def kept(faces, mode, keep):
    """Indices of the faces that count."""
    order = sorted(range(len(faces)), key=lambda i: faces[i])
    if mode == "kh":
        return set(order[-keep:])
    if mode == "kl":
        return set(order[:keep])
    if mode == "dh":
        return set(order[:-keep])
    if mode == "dl":
        return set(order[keep:])
    return set(range(len(faces)))


def roll(terms):
    parts = []
    total = 0
    for term in terms:
        sign = "-" if term["sign"] < 0 else "+"
        if "const" in term:
            total += term["sign"] * term["const"]
            parts.append(f"{sign} {term['const']}")
            continue
        faces = [rng.randint(1, term["sides"]) for _ in range(term["count"])]
        keep = kept(faces, term["mode"], term["keep"])
        subtotal = sum(f for i, f in enumerate(faces) if i in keep)
        total += term["sign"] * subtotal
        shown = ", ".join(str(f) if i in keep else f"~{f}~" for i, f in enumerate(faces))
        name = f"{term['count']}d{term['sides']}{term['mode'] or ''}{term['keep'] or ''}"
        parts.append(f"{sign} {name}[{shown}]={subtotal}")
    line = " ".join(parts)
    return (line[2:] if line.startswith("+ ") else line), total


def main():
    try:
        args = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        fail(f"参数不是 JSON：{exc}")
    dice = str(args.get("dice") or "1d6")
    repeat = args.get("repeat") or 1
    if not isinstance(repeat, int) or not 1 <= repeat <= MAX_REPEAT:
        fail(f"repeat 要是 1 到 {MAX_REPEAT} 的整数")
    terms = parse(dice)
    label = str(args.get("label") or "").strip()
    out = [f"{label}：{dice}" if label else dice]
    for n in range(1, repeat + 1):
        detail, total = roll(terms)
        prefix = f"#{n} " if repeat > 1 else ""
        out.append(f"{prefix}{detail} → **{total}**")
    if any(t.get("mode") for t in terms):
        out.append("（~划掉的~ 不计入）")
    print("\n".join(out))


if __name__ == "__main__":
    main()
