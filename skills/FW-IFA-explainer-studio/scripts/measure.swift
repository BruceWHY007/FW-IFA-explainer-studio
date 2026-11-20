// 人物画面测量：每张 jpg 输出人脸框、头顶位置、人体左右边界（按行），坐标是图像像素，原点左上。
// 用法：measure <帧目录>   → stdout 输出 JSON {"文件名": {"w","h","faces":[{x,y,w,h,conf}],"head_top","extents":[[y,左,右],...]}}
// 依赖 macOS 12+ 的 Vision（人脸检测＋人像分割）。scripts/measure.py 会自动编译并调用它。
import Foundation
import Vision
import AppKit
import CoreVideo

let dir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
let files = ((try? FileManager.default.contentsOfDirectory(atPath: dir)) ?? []).filter { $0.hasSuffix(".jpg") }.sorted()
var out: [String: Any] = [:]
for f in files {
    let url = URL(fileURLWithPath: dir).appendingPathComponent(f)
    guard let img = NSImage(contentsOf: url),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let W = Double(cg.width), H = Double(cg.height)
    let fr = VNDetectFaceRectanglesRequest()
    let seg = VNGeneratePersonSegmentationRequest()
    seg.qualityLevel = .accurate
    seg.outputPixelFormat = kCVPixelFormatType_OneComponent8
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([fr, seg])
    var faces: [[String: Double]] = []
    for o in fr.results ?? [] {
        let b = o.boundingBox
        faces.append(["x": b.minX * W, "y": (1 - b.maxY) * H, "w": b.width * W, "h": b.height * H, "conf": Double(o.confidence)])
    }
    var rec: [String: Any] = ["w": W, "h": H, "faces": faces]
    if let pb = seg.results?.first?.pixelBuffer {
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        let mw = CVPixelBufferGetWidth(pb), mh = CVPixelBufferGetHeight(pb), bpr = CVPixelBufferGetBytesPerRow(pb)
        let base = CVPixelBufferGetBaseAddress(pb)!.assumingMemoryBound(to: UInt8.self)
        var top = -1
        var ext: [[Double]] = []
        let step = max(1, mh / 160)
        for y in 0..<mh {
            var c = 0, l = -1, r = -1
            for x in 0..<mw where base[y * bpr + x] > 127 { c += 1; if l < 0 { l = x }; r = x }
            if top < 0 && c > mw / 60 { top = y }
            if y % step == 0 {
                ext.append([Double(y) * H / Double(mh), l < 0 ? -1 : Double(l) * W / Double(mw), r < 0 ? -1 : Double(r) * W / Double(mw)])
            }
        }
        CVPixelBufferUnlockBaseAddress(pb, .readOnly)
        rec["head_top"] = top < 0 ? -1 : Double(top) * H / Double(mh)
        rec["extents"] = ext
    }
    out[f] = rec
}
let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
