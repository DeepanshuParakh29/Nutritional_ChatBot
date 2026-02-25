import os
import csv
import json
import re
import math
from ast import literal_eval

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB1 = os.path.join(BASE_DIR, "knowledge_base.csv")
KB2 = os.path.join(BASE_DIR, "900_food_cereal,vegetable,green.csv")
OUT = os.path.join(BASE_DIR, "trained_model.json")

def tokenize(text):
    return re.findall(r"[a-zA-Z\u0900-\u097F]+", (text or "").lower())

def load_docs():
    docs = []
    if os.path.exists(KB1):
        with open(KB1, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = (row.get("title") or "").strip()
                category = (row.get("category") or "").strip()
                content = (row.get("content") or "").strip()
                try:
                    nutrition = literal_eval(row.get("nutrition", "{}"))
                except Exception:
                    nutrition = {}
                try:
                    ayurveda = literal_eval(row.get("ayurveda", "{}"))
                except Exception:
                    ayurveda = {}
                doc_id = row.get("id") or title.lower().replace(" ", "-")
                text = " ".join([title, category, content])
                docs.append({
                    "id": doc_id,
                    "title": title,
                    "category": category,
                    "content": content,
                    "nutrition": nutrition,
                    "ayurveda": ayurveda,
                    "tokens": tokenize(text)
                })
    if os.path.exists(KB2):
        with open(KB2, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = (row.get("Food Item (खाद्य पदार्थ)") or "").strip()
                if not title:
                    continue
                category = (row.get("Cereals,Pulses,Lentils & Legumes") or row.get("Category") or "").strip()
                calories = (row.get("Calories (per 100g)") or "").strip()
                protein = (row.get("Protein (g)") or "").strip()
                carbs = (row.get("Carbs(g)") or "").strip()
                fats = (row.get("Fats(g)") or "").strip()
                rasa = (row.get("Rasa (Taste) (रस)") or "").strip()
                virya = (row.get("Virya (Potency) (वीर्य)") or "").strip()
                guna = (row.get("Guna (Quality) (गुण)") or "").strip()
                vipaka = (row.get("Vipaka (Post-digestive) (विपाक)") or "").strip()
                suitable = (row.get("Suitable for (Vata/Pitta/Kapha)") or "").strip()
                notes = (row.get("Notes (Digestion / Special Effects)") or "").strip()
                nutrition = {}
                if calories: nutrition["calories"] = calories
                if protein: nutrition["protein"] = protein
                if carbs: nutrition["carbs"] = carbs
                if fats: nutrition["fats"] = fats
                ayurveda = {}
                if rasa: ayurveda["rasa"] = rasa
                if virya: ayurveda["virya"] = virya
                if guna: ayurveda["guna"] = guna
                if vipaka: ayurveda["vipaka"] = vipaka
                if suitable: ayurveda["dosha_effects"] = suitable
                content_parts = []
                if notes: content_parts.append(notes)
                if nutrition:
                    content_parts.append("Nutritional (per 100g): " + ", ".join([f"{k.capitalize()}: {v}" for k, v in nutrition.items()]))
                if ayurveda:
                    content_parts.append("Ayurvedic: " + ", ".join([f"{k.capitalize()}: {v}" for k, v in ayurveda.items()]))
                content = "\n".join(content_parts).strip()
                text = " ".join([title, category, content])
                doc_id = title.lower().replace(" ", "-")
                docs.append({
                    "id": doc_id,
                    "title": title,
                    "category": category,
                    "content": content,
                    "nutrition": nutrition,
                    "ayurveda": ayurveda,
                    "tokens": tokenize(text)
                })
    return docs

def build_bm25(docs, k1=1.5, b=0.75):
    N = len(docs)
    df = {}
    tfs = []
    lengths = []
    for doc in docs:
        tf = {}
        for t in doc["tokens"]:
            tf[t] = tf.get(t, 0) + 1
        tfs.append(tf)
        lengths.append(sum(tf.values()))
        for t in tf.keys():
            df[t] = df.get(t, 0) + 1
    avgdl = sum(lengths) / max(N, 1)
    idf = {}
    for t, d in df.items():
        idf[t] = math.log((N - d + 0.5) / (d + 0.5) + 1.0)
    model = {
        "meta": {"N": N, "avgdl": avgdl, "k1": k1, "b": b},
        "idf": idf,
        "docs": [],
    }
    for i, doc in enumerate(docs):
        model["docs"].append({
            "id": doc["id"],
            "len": lengths[i],
            "tf": tfs[i],
            "title": doc["title"],
            "category": doc["category"],
            "content": doc["content"],
            "nutrition": doc["nutrition"],
            "ayurveda": doc["ayurveda"]
        })
    return model

def main():
    docs = load_docs()
    model = build_bm25(docs)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False)
    print(f"Saved BM25 model with {len(model['docs'])} docs to {OUT}")

if __name__ == "__main__":
    main()
