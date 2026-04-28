from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient


DEFAULT_MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DEFAULT_DATABASE_NAME = os.getenv("DATABASE_NAME", "ecommerce_db")


CATEGORY_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Action Figures": {"hi": "एक्शन फिगर्स", "ja": "アクションフィギュア"},
    "Aquarium": {"hi": "एक्वेरियम", "ja": "水槽用品"},
    "Art and Craft": {"hi": "कला और शिल्प", "ja": "アートとクラフト"},
    "Audio Accessories": {"hi": "ऑडियो एक्सेसरीज़", "ja": "オーディオアクセサリー"},
    "Automotive": {"hi": "ऑटोमोटिव", "ja": "自動車用品"},
    "Baby Clothing": {"hi": "बेबी कपड़े", "ja": "ベビー服"},
    "Baby Products": {"hi": "बेबी उत्पाद", "ja": "ベビー用品"},
    "Backpacks": {"hi": "बैकपैक", "ja": "バックパック"},
    "Beauty and Personal Care": {"hi": "ब्यूटी और पर्सनल केयर", "ja": "美容とパーソナルケア"},
    "Beverages": {"hi": "पेय पदार्थ", "ja": "飲料"},
    "Board Games": {"hi": "बोर्ड गेम्स", "ja": "ボードゲーム"},
    "Books": {"hi": "किताबें", "ja": "本"},
    "Bracelets": {"hi": "कंगन", "ja": "ブレスレット"},
    "Cameras": {"hi": "कैमरे", "ja": "カメラ"},
    "Camping Gear": {"hi": "कैंपिंग गियर", "ja": "キャンプ用品"},
    "Car Accessories": {"hi": "कार एक्सेसरीज़", "ja": "カーアクセサリー"},
    "Cat Supplies": {"hi": "बिल्ली सप्लाई", "ja": "猫用品"},
    "Children Books": {"hi": "बच्चों की किताबें", "ja": "児童書"},
    "Consoles": {"hi": "कंसोल", "ja": "ゲーム機"},
    "Cookware": {"hi": "कुकवेयर", "ja": "調理器具"},
    "Craft Supplies": {"hi": "क्राफ्ट सप्लाई", "ja": "クラフト用品"},
    "Cycling": {"hi": "साइक्लिंग", "ja": "サイクリング"},
    "Diapers": {"hi": "डायपर", "ja": "おむつ"},
    "Dog Supplies": {"hi": "कुत्ता सप्लाई", "ja": "犬用品"},
    "Drawing": {"hi": "ड्रॉइंग", "ja": "描画"},
    "Educational Toys": {"hi": "शैक्षिक खिलौने", "ja": "知育玩具"},
    "Electronics": {"hi": "इलेक्ट्रॉनिक्स", "ja": "電子機器"},
    "Fashion": {"hi": "फैशन", "ja": "ファッション"},
    "Feeding": {"hi": "फीडिंग", "ja": "授乳用品"},
    "Fiction": {"hi": "फिक्शन", "ja": "フィクション"},
    "Fitness Equipment": {"hi": "फिटनेस उपकरण", "ja": "フィットネス機器"},
    "Footwear": {"hi": "फुटवेयर", "ja": "履物"},
    "Furniture": {"hi": "फर्नीचर", "ja": "家具"},
    "Gaming": {"hi": "गेमिंग", "ja": "ゲーム"},
    "Gaming Accessories": {"hi": "गेमिंग एक्सेसरीज़", "ja": "ゲームアクセサリー"},
    "Garden": {"hi": "गार्डन", "ja": "ガーデン"},
    "Garden Tools": {"hi": "गार्डन टूल्स", "ja": "園芸工具"},
    "Grocery": {"hi": "किराना", "ja": "食料品"},
    "Haircare": {"hi": "हेयरकेयर", "ja": "ヘアケア"},
    "Health": {"hi": "स्वास्थ्य", "ja": "健康"},
    "Home Decor": {"hi": "होम डेकोर", "ja": "ホームデコレーション"},
    "Home and Kitchen": {"hi": "घर और रसोई", "ja": "ホームとキッチン"},
    "Instruments": {"hi": "वाद्य यंत्र", "ja": "楽器"},
    "Jewelry": {"hi": "ज्वेलरी", "ja": "ジュエリー"},
    "Laptops": {"hi": "लैपटॉप", "ja": "ノートパソコン"},
    "Luggage": {"hi": "लगेज", "ja": "旅行かばん"},
    "Makeup": {"hi": "मेकअप", "ja": "メイクアップ"},
    "Medical Supplies": {"hi": "मेडिकल सप्लाई", "ja": "医療用品"},
    "Men Clothing": {"hi": "पुरुषों के कपड़े", "ja": "メンズ衣料"},
    "Men Watches": {"hi": "पुरुषों की घड़ियाँ", "ja": "メンズ腕時計"},
    "Motorcycle Parts": {"hi": "मोटरसाइकिल पार्ट्स", "ja": "オートバイ部品"},
    "Music": {"hi": "संगीत", "ja": "音楽"},
    "Necklaces": {"hi": "हार", "ja": "ネックレス"},
    "Non Fiction": {"hi": "नॉन फिक्शन", "ja": "ノンフィクション"},
    "Office Furniture": {"hi": "कार्यालय फर्नीचर", "ja": "オフィス家具"},
    "Office Supplies": {"hi": "कार्यालय सप्लाई", "ja": "オフィス用品"},
    "Organic Food": {"hi": "ऑर्गेनिक फूड", "ja": "オーガニック食品"},
    "Outdoor Decor": {"hi": "आउटडोर डेकोर", "ja": "屋外装飾"},
    "PC Gaming": {"hi": "पीसी गेमिंग", "ja": "PCゲーム"},
    "Painting": {"hi": "पेंटिंग", "ja": "絵画"},
    "Pet Supplies": {"hi": "पेट सप्लाई", "ja": "ペット用品"},
    "Phase 2A Smoke Category": {"hi": "चरण 2A स्मोक श्रेणी", "ja": "フェーズ2Aスモークカテゴリ"},
    "Plants": {"hi": "पौधे", "ja": "植物"},
    "Printers": {"hi": "प्रिंटर", "ja": "プリンター"},
    "Rings": {"hi": "अंगूठियाँ", "ja": "指輪"},
    "Skincare": {"hi": "स्किनकेयर", "ja": "スキンケア"},
    "Smart Watches": {"hi": "स्मार्ट वॉच", "ja": "スマートウォッチ"},
    "Smartphones": {"hi": "स्मार्टफोन", "ja": "スマートフォン"},
    "Snacks": {"hi": "स्नैक्स", "ja": "スナック"},
    "Sports and Outdoors": {"hi": "स्पोर्ट्स और आउटडोर", "ja": "スポーツとアウトドア"},
    "Stationery": {"hi": "स्टेशनरी", "ja": "文房具"},
    "Supplements": {"hi": "सप्लीमेंट्स", "ja": "サプリメント"},
    "Tools and Equipment": {"hi": "टूल्स और उपकरण", "ja": "工具と機器"},
    "Toys and Games": {"hi": "खिलौने और गेम्स", "ja": "おもちゃとゲーム"},
    "Travel": {"hi": "यात्रा", "ja": "旅行"},
    "Travel Accessories": {"hi": "ट्रैवल एक्सेसरीज़", "ja": "旅行アクセサリー"},
    "Vinyl Records": {"hi": "विनाइल रिकॉर्ड", "ja": "レコード"},
    "Watches": {"hi": "घड़ियाँ", "ja": "腕時計"},
    "Wellness": {"hi": "वेलनेस", "ja": "ウェルネス"},
    "Women Clothing": {"hi": "महिलाओं के कपड़े", "ja": "レディース衣料"},
    "Women Watches": {"hi": "महिलाओं की घड़ियाँ", "ja": "レディース腕時計"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill Hindi and Japanese model translations for seeded categories and products."
    )
    parser.add_argument("--mongodb-url", default=DEFAULT_MONGODB_URL)
    parser.add_argument("--database", default=DEFAULT_DATABASE_NAME)
    parser.add_argument("--overwrite", action="store_true", help="Replace existing hi/ja translations.")
    return parser.parse_args()


def product_number(product: dict[str, Any]) -> int:
    match = re.search(r"Product\s+(\d+)", str(product.get("name", "")))
    if match:
        return int(match.group(1))

    edition = product.get("specifications", {}).get("Edition")
    match = re.search(r"(\d+)", str(edition or ""))
    return int(match.group(1)) if match else 1


def product_translations(product: dict[str, Any], category_translation: dict[str, str]) -> dict[str, dict[str, str]]:
    number = product_number(product)
    hi_category = category_translation["hi"]
    ja_category = category_translation["ja"]

    return {
        "hi": {
            "name": f"{hi_category} उत्पाद {number}",
            "description": (
                f"{hi_category} श्रेणी का उत्पाद संस्करण {number}. "
                "यह रोजमर्रा के उपयोग के लिए गुणवत्ता, आराम और दीर्घकालिक भरोसे को ध्यान में रखकर बनाया गया है."
            ),
        },
        "ja": {
            "name": f"{ja_category} 商品 {number}",
            "description": (
                f"{ja_category}カテゴリの商品エディション{number}です。"
                "日常使いに向けて、品質、快適さ、長期的な信頼性のバランスを重視しています。"
            ),
        },
    }


def missing_translation_filter(overwrite: bool) -> dict[str, Any]:
    if overwrite:
        return {}
    return {
        "$or": [
            {"translations.hi.name": {"$exists": False}},
            {"translations.ja.name": {"$exists": False}},
        ]
    }


def update_categories(db, *, overwrite: bool) -> int:
    modified = 0
    now = datetime.now(timezone.utc)

    for category in db.categories.find({}):
        translation = CATEGORY_TRANSLATIONS.get(category.get("name"))
        if not translation:
            continue

        update: dict[str, Any] = {"updated_at": now}
        if overwrite or "hi" not in category.get("translations", {}):
            update["translations.hi"] = {"name": translation["hi"]}
        if overwrite or "ja" not in category.get("translations", {}):
            update["translations.ja"] = {"name": translation["ja"]}

        if len(update) == 1:
            continue

        result = db.categories.update_one({"_id": category["_id"]}, {"$set": update})
        modified += result.modified_count

    return modified


def update_products(db, *, overwrite: bool) -> int:
    modified = 0
    now = datetime.now(timezone.utc)
    categories = {category["_id"]: category for category in db.categories.find({})}
    query = missing_translation_filter(overwrite)

    for product in db.products.find(query):
        category = categories.get(product.get("category_id"))
        if not category:
            continue

        category_translation = CATEGORY_TRANSLATIONS.get(category.get("name"))
        if not category_translation:
            continue

        translations = product_translations(product, category_translation)
        update: dict[str, Any] = {"updated_at": now}
        existing = product.get("translations", {})

        if overwrite or "hi" not in existing:
            update["translations.hi"] = translations["hi"]
        if overwrite or "ja" not in existing:
            update["translations.ja"] = translations["ja"]

        if len(update) == 1:
            continue

        result = db.products.update_one({"_id": product["_id"]}, {"$set": update})
        modified += result.modified_count

    return modified


def main() -> int:
    args = parse_args()

    client = MongoClient(args.mongodb_url, tz_aware=True)
    db = client[args.database]

    category_count = update_categories(db, overwrite=args.overwrite)
    product_count = update_products(db, overwrite=args.overwrite)

    hi_products = db.products.count_documents({"translations.hi.name": {"$exists": True}})
    ja_products = db.products.count_documents({"translations.ja.name": {"$exists": True}})
    hi_categories = db.categories.count_documents({"translations.hi.name": {"$exists": True}})
    ja_categories = db.categories.count_documents({"translations.ja.name": {"$exists": True}})

    client.close()

    print(f"Updated categories: {category_count}")
    print(f"Updated products: {product_count}")
    print(f"Category translations: hi={hi_categories}, ja={ja_categories}")
    print(f"Product translations: hi={hi_products}, ja={ja_products}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
