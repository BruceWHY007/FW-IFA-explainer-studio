# -*- coding: utf-8 -*-
"""按关键词搜母题图标（Lucide，ISC 许可）。中文关键词先查下面的对照表，再按英文名和标签搜。
用法：python icons.py 保险 盾牌 公文包     → 列出候选图标名，挑 2–3 个写进 plan.json 的 motif
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZH = {
    "钱": "dollar banknote coins wallet", "金融": "landmark banknote trending", "银行": "landmark", "保险": "shield umbrella",
    "盾牌": "shield", "公文包": "briefcase", "股票": "candlestick trending chart", "上市": "bell landmark", "估值": "scale gauge",
    "芯片": "cpu chip", "AI": "bot brain sparkles cpu", "人工智能": "bot brain sparkles", "数据": "database chart", "电力": "zap plug",
    "服务器": "server", "手机": "smartphone", "酒店": "hotel bed concierge", "枕头": "bed", "房子": "house building", "房产": "house building key",
    "汽车": "car", "游戏": "gamepad joystick", "电影": "clapperboard film", "矿": "pickaxe mountain gem", "稀土": "gem atom mountain",
    "石油": "fuel droplet", "黄金": "gem coins", "地球": "globe earth", "贸易": "ship container globe", "关税": "ship receipt",
    "政策": "scroll gavel landmark", "法律": "gavel scale", "医疗": "stethoscope heart-pulse pill", "教育": "graduation book",
    "家庭": "house heart users", "孩子": "baby", "退休": "armchair hourglass", "时间": "clock hourglass", "风险": "triangle-alert shield",
    "增长": "trending-up rocket", "下跌": "trending-down", "香港": "building-2 ship", "移民": "plane passport globe", "旅行": "plane luggage",
    "咖啡": "coffee", "餐厅": "utensils chef-hat", "工厂": "factory", "卡车": "truck", "能源": "zap sun battery", "新能源": "battery-charging sun",
}


def main():
    names = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "assets", "icons", "lucide")) if f.endswith(".svg"))
    tags = json.load(open(os.path.join(ROOT, "assets", "icons", "lucide-tags.json"), encoding="utf-8"))
    for q in sys.argv[1:]:
        terms = ZH.get(q, q).lower().split()
        hits = []
        for n in names:
            score = sum(3 for t in terms if t in n) + sum(1 for t in terms for g in tags.get(n, []) if t in g.lower())
            if score:
                hits.append((score, n))
        hits.sort(key=lambda x: (-x[0], x[1]))
        print(f"{q}：{'  '.join(n for _, n in hits[:14]) or '（没找到，换个英文词）'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main()
