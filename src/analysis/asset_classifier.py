"""
Asset classifier for investment trend analysis.
Maps news titles to investment asset classes using keyword matching.
"""

from typing import Dict, List

ASSET_KEYWORDS: Dict[str, List[str]] = {
    "gold": [
        # Vietnamese
        "vàng", "giá vàng", "sjc", "pnj", "doji", "vàng miếng", "vàng nhẫn",
        "kim loại quý", "trang sức vàng",
        # English
        "gold", "xau", "precious metal", "bullion", "gold price", "gold futures",
        "gold etf", "comex gold", "spot gold",
        # Chinese
        "黄金", "金价", "贵金属", "黄金期货",
    ],
    "forex": [
        # Vietnamese
        "tỷ giá", "ngoại tệ", "đô la", "euro", "yên nhật", "bảng anh", "nhân dân tệ",
        "tỷ giá usd", "tỷ giá eur", "ngân hàng nhà nước", "dự trữ ngoại hối",
        # English
        "usd", "eur", "jpy", "gbp", "cny", "forex", "foreign exchange", "dollar",
        "dollar index", "dxy", "fed rate", "interest rate", "federal reserve",
        "currency", "exchange rate", "eur/usd", "usd/jpy", "gbp/usd",
        "fed", "fomc", "powell", "ecb", "boj",
        # Chinese
        "汇率", "美元", "欧元", "日元", "外汇", "人民币汇率",
    ],
    "stocks_us": [
        # English
        "nasdaq", "s&p 500", "s&p500", "dow jones", "nyse", "wall street",
        "us stock", "american stock", "sp500", "dow", "russell 2000",
        "us market", "stock market", "aapl", "msft", "nvda", "tesla", "apple",
        "microsoft", "nvidia", "meta", "alphabet", "google", "amazon",
        "earnings", "ipo", "sec", "nyse", "bear market", "bull market",
        # Vietnamese
        "chứng khoán mỹ", "thị trường mỹ", "cổ phiếu mỹ",
        # Chinese
        "美股", "纳斯达克", "道琼斯", "标普",
    ],
    "stocks_vn": [
        # Vietnamese
        "vnindex", "vn-index", "vn index", "hose", "hnx", "upcom",
        "chứng khoán việt nam", "cổ phiếu", "cophieu", "thị trường chứng khoán",
        "nhà đầu tư", "khối ngoại", "tự doanh", "margin", "room ngoại",
        "vnd", "vcb", "bvh", "hpg", "mwg", "fpt", "vin", "vingroup",
        "ctg", "bid", "acb", "mbbank", "techcombank", "vietcombank",
        "sssi", "vpbs", "hnx30", "vn30", "midcap", "smallcap",
        # English
        "vietnam stock", "ho chi minh stock", "hcm stock exchange",
    ],
    "stocks_cn": [
        # Chinese
        "沪深", "上证", "深证", "港股", "恒生", "a股", "沪指",
        "创业板", "科创板", "北交所",
        # English
        "shanghai composite", "hang seng", "shenzhen", "hong kong stock",
        "a-share", "h-share", "csi 300", "china stock", "hkex",
        # Vietnamese
        "chứng khoán trung quốc", "thị trường trung quốc",
    ],
    "crypto": [
        # Universal
        "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
        "blockchain", "defi", "nft", "altcoin", "binance", "coinbase",
        "usdt", "usdc", "ripple", "xrp", "solana", "sol", "bnb",
        "web3", "satoshi", "halving", "mining", "wallet", "exchange hack",
        # Vietnamese
        "tiền điện tử", "tiền ảo", "tài sản số", "mã hóa",
        # Chinese
        "比特币", "以太坊", "加密货币", "区块链", "数字货币",
    ],
    "commodities": [
        # Vietnamese
        "dầu thô", "giá dầu", "khí đốt", "đồng", "sắt thép", "thép", "nhôm",
        "lúa mì", "gạo", "cà phê", "cao su", "ngô", "đậu tương",
        "hàng hóa", "nguyên liệu", "xăng dầu",
        # English
        "oil", "crude oil", "brent", "wti", "opec", "natural gas", "lng",
        "copper", "iron ore", "steel", "aluminum", "wheat", "corn",
        "soybean", "coffee", "rubber", "sugar", "commodity", "commodities",
        # Chinese
        "原油", "大宗商品", "铜价", "铁矿石", "小麦", "玉米",
    ],
}

ASSET_DISPLAY_NAMES: Dict[str, str] = {
    "gold": "Vàng (XAU)",
    "forex": "Ngoại hối (Forex)",
    "stocks_us": "Chứng khoán Mỹ",
    "stocks_vn": "Chứng khoán Việt Nam",
    "stocks_cn": "Chứng khoán Trung Quốc",
    "crypto": "Tiền điện tử (Crypto)",
    "commodities": "Hàng hóa (Commodities)",
}


def classify_news(titles: List[str]) -> Dict[str, List[str]]:
    """
    Classify news titles into asset classes based on keyword matching.
    A title can match multiple asset classes.

    Returns:
        Dict mapping asset_id -> list of matching titles
    """
    result: Dict[str, List[str]] = {asset: [] for asset in ASSET_KEYWORDS}

    for title in titles:
        title_lower = title.lower()
        for asset, keywords in ASSET_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in title_lower:
                    result[asset].append(title)
                    break  # avoid duplicates per asset

    return result
