# -*- coding: utf-8 -*-
"""人物段能用哪些版式：按 geom.json 算头顶还剩多少、脸两侧还剩多少。

和 build 用同一套算法（直接借 Film 的人脸几何方法），measure.py 量完就报、draft_plan.py 写草稿时避开、
style_preview.py 出对照图时选开场版式，不用等到 build 才报「头顶只有 44px」「脸两侧只剩 178px」。
"""
from .core import Film, W, TITLE_TOP, SAFE_X

TITLE_MIN_FS = 56   # 头顶标题最小字号：头顶可用高度低于它就放不下（layouts_host.head_title）
SIDE_MIN = 220      # 对立标签最小宽度：脸两侧都要留出这么宽（layouts_host.side_tags）


class Geo:
    """只有人脸几何的 Film：方法原样借用，算出来和 build 一致。"""
    _frames = Film._frames
    face_box = Film.face_box
    face_med = Film.face_med
    head_top = Film.head_top
    zoom_origin = Film.zoom_origin

    def __init__(self, geom):
        self.geom = geom
        self.aroll_dur = float(geom.get("duration") or max((f["t"] for f in geom.get("frames", [])), default=0))


def title_avail(g, t0, t1):
    """头顶标题可用高度（px）。头顶标题所在段不推近，按原尺寸算。"""
    return g.head_top(t0, t1) - 22 - TITLE_TOP


def side_room(g, t0, t1, zoom=False):
    """脸两侧较窄那一边还剩多宽（px），和 side_tags 的算法一致。"""
    fx, fy, fw, fh = g.face_box(t0, t1, zoom=zoom)
    left = fx - fw * 0.05 - SAFE_X - 16
    right = W - (fx + fw * 1.05) - SAFE_X - 16
    return min(left, right)


def title_ok(g, t0, t1):
    return title_avail(g, t0, t1) >= TITLE_MIN_FS


def side_ok(g, t0, t1):
    """跳切推近会让脸变宽，按推近后的位置算，宁严勿松。"""
    return side_room(g, t0, t1, zoom=True) >= SIDE_MIN


def summary(geom, win=4.0):
    """全片按 win 秒一段滑过去，统计头顶标题、对立标签各有多少时间放得下。返回 (dict, 中文报告行)。"""
    g = Geo(geom)
    dur = g.aroll_dur
    ts = [i * win for i in range(max(1, int(dur // win)))]
    t_ok = [title_ok(g, t, t + win) for t in ts]
    s_ok = [side_ok(g, t, t + win) for t in ts]
    ta = [title_avail(g, t, t + win) for t in ts]
    sr = [side_room(g, t, t + win, zoom=True) for t in ts]
    r = {"title_ok_ratio": round(sum(t_ok) / len(ts), 2), "title_avail_min": round(min(ta)), "title_avail_max": round(max(ta)),
         "side_ok_ratio": round(sum(s_ok) / len(ts), 2), "side_room_min": round(min(sr)), "side_room_max": round(max(sr)),
         "open_title_ok": title_ok(g, 0, min(4.0, dur))}
    lines = []
    if r["title_ok_ratio"] == 0:
        lines.append(f"头顶标题：全片放不下（头顶可用 {r['title_avail_min']}–{r['title_avail_max']}px，至少 {TITLE_MIN_FS}px）。"
                     f"开场和问句改用身前卡片 chest_cards；下次拍摄头顶留出画面高度的 1/4")
    elif r["title_ok_ratio"] < 1:
        lines.append(f"头顶标题：{r['title_ok_ratio']:.0%} 的时间放得下（头顶可用 {r['title_avail_min']}–{r['title_avail_max']}px）"
                     + ("；开场放不下，开场用身前卡片" if not r["open_title_ok"] else ""))
    else:
        lines.append(f"头顶标题：全片放得下（头顶可用至少 {r['title_avail_min']}px）")
    if r["side_ok_ratio"] == 0:
        lines.append(f"对立标签：全片放不下（脸两侧推近后 {r['side_room_min']}–{r['side_room_max']}px，至少 {SIDE_MIN}px）。"
                     f"两个对立概念改用身前卡片（两张）或贴纸")
    elif r["side_ok_ratio"] < 1:
        lines.append(f"对立标签：{r['side_ok_ratio']:.0%} 的时间放得下（脸两侧推近后 {r['side_room_min']}–{r['side_room_max']}px）")
    else:
        lines.append(f"对立标签：全片放得下（脸两侧推近后至少 {r['side_room_min']}px）")
    return r, lines
