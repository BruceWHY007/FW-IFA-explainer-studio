# -*- coding: utf-8 -*-
"""量人物画面：按固定间隔抽帧，测人脸框、头顶、人体左右边界，写 geom.json。
build 按每段时间取这一段里最不利的位置（脸框取并集、头顶取最高），据此摆放头顶标题、两侧标签、身前卡片和小窗取景。

三种实现，--backend auto 时按系统自动选：
  vision     macOS 12+：系统自带 Vision（人脸检测＋人像分割），不用装任何东西。首次运行会用 swiftc 编译 measure.swift。
  mediapipe  Windows／Linux／macOS 通用：pip install mediapipe==0.10.14 opencv-python-headless
             （mediapipe 0.10.14 需要 Python 3.9–3.12；也可以 uv run --python 3.11 --with mediapipe==0.10.14 --with opencv-python-headless python measure.py …）
  opencv     兜底：pip install "opencv-python-headless<5"。只有 OpenCV 自带的人脸检测，头顶按脸框往上 0.4 个框高估算（比实测偏高约 40–60px，标题会让得更多），没有人体边界。精度最低，会在结果里标明。

用法：python measure.py <剪好的人物视频 aroll.mp4> <输出 geom.json> [--step 0.5] [--backend auto|vision|mediapipe|opencv]
"""
import argparse, json, os, platform, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "ifa-tujie")


# ---------------------------------------------------------------- 各实现：输入帧目录，输出 {文件名: {w,h,faces,head_top,extents}}
def run_vision(frames_dir):
    os.makedirs(CACHE, exist_ok=True)
    src = os.path.join(HERE, "measure.swift")
    exe = os.path.join(CACHE, "measure")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        print("编译 measure.swift …", file=sys.stderr)
        subprocess.run(["swiftc", "-O", src, "-o", exe], check=True)
    return json.loads(subprocess.check_output([exe, frames_dir]).decode())


def run_mediapipe(frames_dir):
    import cv2
    import mediapipe as mp
    out = {}
    fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    ss = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
    for name in sorted(os.listdir(frames_dir)):
        if not name.endswith(".jpg"):
            continue
        img = cv2.imread(os.path.join(frames_dir, name))
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        faces = []
        r = fd.process(rgb)
        for det in (r.detections or []):
            b = det.location_data.relative_bounding_box
            faces.append({"x": b.xmin * w, "y": b.ymin * h, "w": b.width * w, "h": b.height * h, "conf": float(det.score[0])})
        rec = {"w": w, "h": h, "faces": faces}
        m = ss.process(rgb).segmentation_mask
        if m is not None:
            mask = m > 0.5
            cov = mask.sum(axis=1)
            rows = [y for y in range(h) if cov[y] > w / 60]
            rec["head_top"] = float(rows[0]) if rows else -1
            ext = []
            step = max(1, h // 160)
            for y in range(0, h, step):
                xs = mask[y].nonzero()[0]
                ext.append([float(y), float(xs[0]) if len(xs) else -1, float(xs[-1]) if len(xs) else -1])
            rec["extents"] = ext
        out[name] = rec
    return out


def run_opencv(frames_dir):
    import cv2
    if not hasattr(cv2, "CascadeClassifier"):
        sys.exit("OpenCV 5 去掉了 Haar 人脸检测，兜底实现要用 4.x：pip install \"opencv-python-headless<5\"（更推荐装 mediapipe）")
    casc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    out = {}
    for name in sorted(os.listdir(frames_dir)):
        if not name.endswith(".jpg"):
            continue
        img = cv2.imread(os.path.join(frames_dir, name))
        h, w = img.shape[:2]
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        fs = casc.detectMultiScale(g, 1.1, 5, minSize=(w // 10, w // 10))
        faces = []
        for (x, y, fw, fh) in fs:
            faces.append({"x": float(x), "y": float(y), "w": float(fw), "h": float(fh), "conf": 0.5})
        rec = {"w": w, "h": h, "faces": faces}
        if faces:
            f = max(faces, key=lambda f: f["w"] * f["h"])
            # 估算头顶：Haar 框顶在眉毛上方，往上再留 0.4 个框高给额头和头发（宁高勿低）
            rec["head_top"] = max(0.0, f["y"] - 0.4 * f["h"])
        out[name] = rec
    return out


def pick_backend(name):
    if name != "auto":
        return name
    if platform.system() == "Darwin" and shutil.which("swiftc"):
        return "vision"
    try:
        import mediapipe  # noqa: F401
        import cv2  # noqa: F401
        return "mediapipe"
    except Exception:
        pass
    try:
        import cv2  # noqa: F401
        print("⚠️ 没装 mediapipe，退回 OpenCV 兜底：头顶是估算值、没有人体边界。建议 pip install mediapipe==0.10.14", file=sys.stderr)
        return "opencv"
    except Exception:
        sys.exit("没有可用的测量实现。macOS 装 Xcode 命令行工具（xcode-select --install）；"
                 "Windows／Linux 运行 pip install mediapipe==0.10.14 opencv-python-headless")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--backend", default="auto", choices=["auto", "vision", "mediapipe", "opencv"])
    a = ap.parse_args()
    backend = pick_backend(a.backend)
    probe = lambda *x: subprocess.check_output(["ffprobe", "-v", "error", *x, a.video]).decode().strip()
    dur = float(probe("-show_entries", "format=duration", "-of", "csv=p=0"))
    w, h = [int(v) for v in probe("-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x").split("x")]
    tmp = tempfile.mkdtemp(prefix="tujie-measure-")
    try:
        # 抽帧统一缩到 540 宽，测完换算回原尺寸
        subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", f"fps=1/{a.step},scale=540:-2", "-q:v", "3",
                        os.path.join(tmp, "f%05d.jpg")], check=True)
        raw = {"vision": run_vision, "mediapipe": run_mediapipe, "opencv": run_opencv}[backend](tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    frames = []
    for name in sorted(raw):
        r = raw[name]
        t = round((int(name[1:6]) - 1) * a.step, 3)
        sx, sy = w / r["w"], h / r["h"]
        faces = sorted(r.get("faces", []), key=lambda f: -f["w"] * f["h"])
        face = None
        if faces:
            f = faces[0]
            face = [round(f["x"] * sx), round(f["y"] * sy), round(f["w"] * sx), round(f["h"] * sy)]
        ht = r.get("head_top", -1)
        ext = [[round(y * sy), round(l * sx) if l >= 0 else -1, round(rr * sx) if rr >= 0 else -1] for y, l, rr in r.get("extents", [])]
        frames.append({"t": t, "face": face, "head_top": round(ht * sy) if ht is not None and ht >= 0 else None, "extents": ext})
    json.dump({"video": os.path.abspath(a.video), "width": w, "height": h, "duration": dur, "step": a.step,
               "backend": backend, "estimated_head_top": backend == "opencv", "frames": frames},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    ok = [f for f in frames if f["face"]]
    if ok:
        import statistics as st
        tops = [f["head_top"] for f in ok if f["head_top"] is not None]
        print(f"[{backend}] {len(frames)} 帧，{len(ok)} 帧有人脸；脸顶中位 {st.median(f['face'][1] for f in ok):.0f}px，"
              f"脸高中位 {st.median(f['face'][3] for f in ok):.0f}px，头顶最高 {min(tops) if tops else '—'}px")
        # 人物段能用哪些版式：和 build 同一套算法，现在就报，写草稿时避开放不下的版式
        from tujie import room
        geom = json.load(open(a.out, encoding="utf-8"))
        r, lines = room.summary(geom)
        geom["room"] = r
        json.dump(geom, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
        for ln in lines:
            print("· " + ln)
    else:
        sys.exit(f"[{backend}] {len(frames)} 帧，没有检测到人脸")


if __name__ == "__main__":
    main()
