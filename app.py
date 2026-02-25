import ast
import csv
import json
import os
import math
import time
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from functools import lru_cache
import threading
from collections import defaultdict
import re

# Load environment variables from .env file
load_dotenv()

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'public')
KB_PATH = os.path.join(BASE_DIR, 'kb.json')

# Initialize Flask app
app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

# No ML models; responses are generated from CSV content using templates

# Global variables for knowledge base
kb_docs = []

# Performance optimization caches
response_cache = {}
search_cache = {}
rate_limit_tracker = defaultdict(int)
last_cleanup = datetime.now()

# Advanced features
conversation_memory = {}
LEARN_PATH = os.path.join(BASE_DIR, 'learned.json')
learned_boost = {}

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    
    return dot_product / (magnitude_a * magnitude_b)

def get_cache_key(query, context=""):
    """Generate a cache key for queries."""
    return hashlib.md5(f"{query}:{context}".encode()).hexdigest()

def cleanup_cache():
    """Clean up old cache entries to prevent memory bloat."""
    global last_cleanup
    current_time = datetime.now()
    
    # Clean up cache every 10 minutes
    if (current_time - last_cleanup).seconds < 600:
        return
    
    # Remove cache entries older than 1 hour
    cutoff_time = current_time - timedelta(hours=1)
    
    # Clean response cache
    response_cache_keys_to_remove = []
    for key, (timestamp, _) in response_cache.items():
        if datetime.fromtimestamp(timestamp) < cutoff_time:
            response_cache_keys_to_remove.append(key)
    
    for key in response_cache_keys_to_remove:
        del response_cache[key]
    
    # Clean search cache
    search_cache_keys_to_remove = []
    for key, (timestamp, _) in search_cache.items():
        if datetime.fromtimestamp(timestamp) < cutoff_time:
            search_cache_keys_to_remove.append(key)
    
    for key in search_cache_keys_to_remove:
        del search_cache[key]
    
    last_cleanup = current_time
    print(f"Cache cleanup completed. Removed {len(response_cache_keys_to_remove)} response cache entries and {len(search_cache_keys_to_remove)} search cache entries.")

def rate_limit_check(client_ip, limit=10):
    """Check if client has exceeded rate limit."""
    current_time = int(time.time())
    minute_key = f"{client_ip}:{current_time // 60}"
    
    if rate_limit_tracker[minute_key] >= limit:
        return False
    
    rate_limit_tracker[minute_key] += 1
    
    # Clean old entries
    old_keys = [key for key in rate_limit_tracker.keys() 
                if int(key.split(':')[1]) < current_time // 60 - 5]
    for key in old_keys:
        del rate_limit_tracker[key]
    
    return True



def update_conversation_memory(client_ip, query, response):
    """Update conversation memory for context-aware responses."""
    if client_ip not in conversation_memory:
        conversation_memory[client_ip] = []
    
    # Keep only last 5 interactions to prevent memory bloat
    conversation_memory[client_ip].append({
        'query': query,
        'response': response,
        'timestamp': time.time()
    })
    
    if len(conversation_memory[client_ip]) > 5:
        conversation_memory[client_ip] = conversation_memory[client_ip][-5:]
    try:
        terms = _tokenize(query)
        for t in terms:
            learned_boost[t] = learned_boost.get(t, 0.0) + 0.05
        with open(LEARN_PATH, 'w', encoding='utf-8') as f:
            json.dump({"boost": learned_boost}, f, ensure_ascii=False)
    except Exception:
        pass

def get_conversation_context(client_ip):
    """Get recent conversation context for follow-up queries."""
    if client_ip not in conversation_memory:
        return ""
    
    recent_context = conversation_memory[client_ip][-3:]  # Last 3 interactions
    context_parts = []
    
    for interaction in recent_context:
        context_parts.append(f"Previous question: {interaction['query']}")
        context_parts.append(f"Previous answer: {interaction['response'][:100]}...")
    
    return "\n".join(context_parts)

def load_knowledge_base():
    global kb_docs
    KB_PATH = os.path.join(BASE_DIR, 'knowledge_base.csv')
    EXTRA_PATH = os.path.join(BASE_DIR, '900_food_cereal,vegetable,green.csv')
    if not os.path.exists(KB_PATH):
        print(f"Warning: Knowledge base file not found at {KB_PATH}")
        return
    try:
        with open(KB_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            kb_docs = []
            for row in reader:
                # Normalize fields
                row['title'] = row.get('title', '').strip()
                row['category'] = row.get('category', '').strip()
                row['content'] = row.get('content', '').strip()
                # Parse structured fields if present
                try:
                    row['nutrition'] = ast.literal_eval(row.get('nutrition', '{}'))
                except Exception:
                    row['nutrition'] = {}
                try:
                    row['ayurveda'] = ast.literal_eval(row.get('ayurveda', '{}'))
                except Exception:
                    row['ayurveda'] = {}
                kb_docs.append(row)
        # Load extra dataset if available
        if os.path.exists(EXTRA_PATH):
            with open(EXTRA_PATH, 'r', encoding='utf-8') as f2:
                reader2 = csv.DictReader(f2)
                for row in reader2:
                    title = (row.get('Food Item (खाद्य पदार्थ)') or '').strip()
                    category = (row.get('Cereals,Pulses,Lentils & Legumes') or row.get('Category') or '').strip()
                    calories = (row.get('Calories (per 100g)') or '').strip()
                    protein = (row.get('Protein (g)') or '').strip()
                    carbs = (row.get('Carbs(g)') or '').strip()
                    fats = (row.get('Fats(g)') or '').strip()
                    rasa = (row.get('Rasa (Taste) (रस)') or '').strip()
                    virya = (row.get('Virya (Potency) (वीर्य)') or '').strip()
                    guna = (row.get('Guna (Quality) (गुण)') or '').strip()
                    vipaka = (row.get('Vipaka (Post-digestive) (विपाक)') or '').strip()
                    suitable = (row.get('Suitable for (Vata/Pitta/Kapha)') or '').strip()
                    notes = (row.get('Notes (Digestion / Special Effects)') or '').strip()
                    if not title:
                        continue
                    nutrition = {}
                    if calories: nutrition['calories'] = calories
                    if protein: nutrition['protein'] = protein
                    if carbs: nutrition['carbs'] = carbs
                    if fats: nutrition['fats'] = fats
                    ayurveda = {}
                    if rasa: ayurveda['rasa'] = rasa
                    if virya: ayurveda['virya'] = virya
                    if guna: ayurveda['guna'] = guna
                    if vipaka: ayurveda['vipaka'] = vipaka
                    if suitable: ayurveda['dosha_effects'] = suitable
                    content_parts = []
                    if notes: content_parts.append(notes)
                    # Build a compact description
                    if nutrition:
                        content_parts.append("Nutritional (per 100g): " + ", ".join([f"{k.capitalize()}: {v}" for k, v in nutrition.items()]))
                    if ayurveda:
                        content_parts.append("Ayurvedic: " + ", ".join([f"{k.capitalize()}: {v}" for k, v in ayurveda.items()]))
                    content = "\n".join(content_parts).strip()
                    kb_docs.append({
                        'id': title.lower().replace(' ', '-'),
                        'title': title,
                        'category': category,
                        'content': content,
                        'nutrition': nutrition,
                        'ayurveda': ayurveda,
                        'source': 'extra_csv'
                    })
        print(f"Loaded {len(kb_docs)} items from knowledge base")
        try:
            if os.path.exists(LEARN_PATH):
                with open(LEARN_PATH, 'r', encoding='utf-8') as lf:
                    data = json.load(lf)
                    boost = data.get("boost") or {}
                    for k, v in boost.items():
                        learned_boost[k] = float(v)
        except Exception:
            pass
    except Exception as e:
        print(f"Error loading knowledge base: {str(e)}")
        raise

def _tokenize(text):
    return re.findall(r"[a-zA-Z\u0900-\u097F]+", (text or "").lower())

def _has_devanagari(text):
    return bool(re.search(r"[\u0900-\u097F]", text or ""))
def is_single_item_query(query, kb_results):
    if not kb_results:
        return False
    top = kb_results[0]
    top_sim = float(top.get('similarity') or 0.0)
    second_sim = float(kb_results[1].get('similarity') or 0.0) if len(kb_results) > 1 else 0.0
    tokens = set(_tokenize(query))
    title_tokens = set(_tokenize(top.get('title', '')))
    strong_title_match = len(tokens.intersection(title_tokens)) > 0
    signal_words = {'nutrition','calories','ayurveda','protein','carbs','fats','rasa','virya','guna','vipaka'}
    has_signal = len(tokens.intersection(signal_words)) > 0
    product_words = {'toor','tur','arhar','तूर','अरहर','moong','मूंग','urad','उड़द','chana','चना','masoor','मसूर'}
    if tokens.intersection(product_words):
        return True
    if top_sim >= 0.4 and (len(kb_results) == 1 or (top_sim - second_sim) >= 0.1) and (strong_title_match or has_signal):
        return True
    return False
def search_knowledge_base(query, top_k=3, threshold=0.0):
    """Keyword-based search with simple scoring over the CSV content."""
    if not kb_docs:
        return []
    
    # Check cache first
    cache_key = get_cache_key(query, f"search_{top_k}_{threshold}")
    if cache_key in search_cache:
        timestamp, cached_results = search_cache[cache_key]
        # Use cache if less than 5 minutes old
        if time.time() - timestamp < 300:
            print(f"Using cached search results for: {query}")
            return cached_results
    
    try:
        base_terms = _tokenize(query)
        synonyms = {
            'dal': ['lentil', 'pulse', 'moong', 'mung', 'toor', 'tur', 'arhar', 'chana', 'urad', 'masoor', 'pigeon', 'pea'],
            'lentil': ['dal', 'pulse', 'moong', 'mung', 'masoor', 'urad', 'chana'],
            'pulse': ['dal', 'lentil'],
            'moong': ['mung', 'green', 'gram'],
            'toor': ['tur', 'pigeon', 'pea', 'arhar'],
            'arhar': ['toor', 'tur', 'pigeon', 'pea'],
            'chana': ['chickpea', 'gram'],
            'urad': ['black', 'gram'],
            'masoor': ['red', 'lentil']
        }
        query_terms = list(base_terms)
        for term in base_terms:
            for syn in synonyms.get(term, []):
                if syn not in query_terms:
                    query_terms.append(syn)
        results = []
        for doc in kb_docs:
            title = doc.get('title', '')
            content = doc.get('content', '')
            category = doc.get('category', '')
            text = " ".join([title, content, category]).lower()
            # Simple scoring: title hits count more; category medium; content lower
            score = 0.0
            for term in query_terms:
                if not term:
                    continue
                if term in title.lower():
                    score += 3.0
                if term in category.lower():
                    score += 2.0
                # count occurrences in content
                score += text.count(term) * 0.5
                score += learned_boost.get(term, 0.0)
            if score > threshold:
                results.append({
                    'id': doc.get('id'),
                    'title': title or 'No title',
                    'content': content,
                    'similarity': min(score / 10.0, 1.0),
                    'source': 'knowledge_base',
                    'nutrition': doc.get('nutrition', {}),
                    'ayurveda': doc.get('ayurveda', {})
                })
        results.sort(key=lambda x: x['similarity'], reverse=True)
        final = results[:top_k]
        search_cache[cache_key] = (time.time(), final)
        return final
    except Exception as e:
        print(f"Error searching knowledge base: {str(e)}")
        search_cache[cache_key] = (time.time(), [])
        return []

def _safe_float(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None

def _index_foods():
    groups = {'cereals': [], 'pulses': [], 'vegetables': [], 'others': []}
    for doc in kb_docs:
        cat = (doc.get('category') or '').lower()
        title = (doc.get('title') or '').lower()
        if 'cereal' in cat or 'grain' in cat or 'rice' in title or 'wheat' in title:
            groups['cereals'].append(doc)
        elif 'pulse' in cat or 'lentil' in cat or 'dal' in title:
            groups['pulses'].append(doc)
        elif 'vegetable' in cat or 'veg' in cat:
            groups['vegetables'].append(doc)
        else:
            groups['others'].append(doc)
    return groups

def _pick_items_with_calories(items, n):
    picked = []
    for doc in items:
        cal = _safe_float((doc.get('nutrition', {}) or {}).get('calories'))
        if cal:
            picked.append((doc, cal))
        if len(picked) >= n:
            break
    if len(picked) < n:
        for doc in items:
            if doc not in [p[0] for p in picked]:
                picked.append((doc, _safe_float((doc.get('nutrition', {}) or {}).get('calories')) or 100.0))
            if len(picked) >= n:
                break
    return picked

def _parse_calorie_target(query):
    m = re.search(r'(\d{3,4})\s*(kcal|cal|calories)?', query.lower())
    if m:
        val = int(m.group(1))
        if 1000 <= val <= 3500:
            return val
    return 2000

def _parse_preferences(query):
    q = query.lower()
    prefs = {
        'veg': ('vegetarian' in q or 'vegan' in q),
        'avoid': []
    }
    avoid_match = re.findall(r'avoid\s+([a-zA-Z\u0900-\u097F]+)', q)
    prefs['avoid'] = avoid_match or []
    return prefs

def _labels(lang):
    if lang == 'hi':
        return {
            'diet_plan': 'आहार योजना',
            'breakfast': 'नाश्ता',
            'lunch': 'दोपहर का भोजन',
            'snack': 'स्नैक',
            'dinner': 'रात का खाना',
            'note': 'नोट: भूख और गतिविधि के अनुसार मात्रा समायोजित करें। व्यक्तिगत सलाह के लिए विशेषज्ञ से संपर्क करें।',
            'question': 'प्रश्न',
            'nutri': 'पोषण जानकारी (प्रति 100 ग्राम)',
            'ayur': 'आयुर्वेदिक गुण',
            'general': 'सामान्य जानकारी'
        }
    return {
        'diet_plan': 'Diet Plan',
        'breakfast': 'Breakfast',
        'lunch': 'Lunch',
        'snack': 'Snack',
        'dinner': 'Dinner',
        'note': 'Note: Adjust portions based on appetite and activity. Consult a professional for personalized advice.',
        'question': 'Question',
        'nutri': 'Nutritional Information (per 100g)',
        'ayur': 'Ayurvedic Properties',
        'general': 'General Insights'
    }

def generate_diet_plan(query, lang='en'):
    total_cal = _parse_calorie_target(query)
    prefs = _parse_preferences(query)
    idx = _index_foods()
    meals = [
        ('breakfast', 0.25),
        ('lunch', 0.35),
        ('snack', 0.15),
        ('dinner', 0.25)
    ]
    plan_lines = []
    L = _labels(lang)
    plan_lines.append(f"{L['diet_plan']} (~{total_cal} kcal)")
    for meal_name, share in meals:
        meal_target = int(total_cal * share)
        cereals = _pick_items_with_calories(idx['cereals'], 1)
        pulses = _pick_items_with_calories(idx['pulses'], 1)
        vegetables = _pick_items_with_calories(idx['vegetables'], 1)
        chosen = []
        if meal_name in ['breakfast', 'dinner']:
            chosen = cereals + pulses
        elif meal_name == 'lunch':
            chosen = cereals + pulses + vegetables
        else:
            chosen = vegetables or cereals
        chosen = chosen[:3]
        portions = []
        if chosen:
            per_item = meal_target / max(len(chosen), 1)
            for doc, cal100 in chosen:
                grams = int(per_item / cal100 * 100)
                title = doc.get('title', 'Item')
                if any(a in title.lower() for a in prefs['avoid']):
                    continue
                portions.append((title, grams, doc))
        plan_lines.append(f"\n{L[meal_name]} (~{meal_target} kcal)")
        if not portions:
            plan_lines.append("- दाल और अनाज को सब्जियों के साथ मिलाएँ" if lang == 'hi' else "- Choose mixed dal and cereals with vegetables")
        else:
            for title, grams, doc in portions:
                plan_lines.append(f"- {title}: ~{grams} g")
                nut = doc.get('nutrition', {})
                if nut:
                    p = nut.get('protein'); c = nut.get('carbs'); f = nut.get('fats')
                    extras = []
                    if p: extras.append(("प्रोटीन " if lang == 'hi' else "Protein ") + f"{p} " + ("प्रति 100 ग्राम" if lang == 'hi' else "per 100g"))
                    if c: extras.append(("कार्ब्स " if lang == 'hi' else "Carbs ") + f"{c} " + ("प्रति 100 ग्राम" if lang == 'hi' else "per 100g"))
                    if f: extras.append(("वसा " if lang == 'hi' else "Fats ") + f"{f} " + ("प्रति 100 ग्राम" if lang == 'hi' else "per 100g"))
                    if extras:
                        plan_lines.append(f"  • " + ", ".join(extras))
                ayu = doc.get('ayurveda', {})
                if ayu:
                    rasa = ayu.get('rasa'); virya = ayu.get('virya'); vipaka = ayu.get('vipaka'); dosha = ayu.get('dosha_effects')
                    props = []
                    if rasa: props.append(("रस: " if lang == 'hi' else "Rasa: ") + f"{rasa}")
                    if virya: props.append(("वीर्य: " if lang == 'hi' else "Virya: ") + f"{virya}")
                    if vipaka: props.append(("विपाक: " if lang == 'hi' else "Vipaka: ") + f"{vipaka}")
                    if dosha: props.append(("दोष: " if lang == 'hi' else "Dosha: ") + f"{dosha}")
                    if props:
                        plan_lines.append(f"  • " + ", ".join(props))
    plan_lines.append("\n" + L['note'])
    return "\n".join(plan_lines)

def generate_response(query, context_docs=None, client_ip=None, lang='en'):
    """Compose a response from the top knowledge base documents."""
    try:
        if not context_docs and ("diet plan" in query.lower() or ("diet" in query.lower() and "plan" in query.lower()) or "meal plan" in query.lower()):
            return generate_diet_plan(query, lang=lang)
        if not context_docs:
            return _smalltalk_or_help(query, lang)
        lines = []
        single_mode = len(context_docs) == 1
        L = _labels(lang)
        lines.append(f"{L['question']}: {query}")
        # Deduplicate by title to avoid repeated items from multiple sources
        dedup = []
        seen_titles = set()
        for d in (context_docs if not single_mode else context_docs[:1]):
            t = (d.get('title') or '').strip().lower()
            if t and t in seen_titles:
                continue
            seen_titles.add(t)
            dedup.append(d)
        for i, doc in enumerate(dedup, 1):
            lines.append(f"\n{doc.get('title', 'No title')} ({doc.get('source', 'knowledge_base')})")
            if doc.get('nutrition'):
                lines.append(L['nutri'] + ":")
                for k, v in doc['nutrition'].items():
                    lines.append(f"- {k.capitalize()}: {v}")
            if doc.get('ayurveda'):
                lines.append(L['ayur'] + ":")
                for k, v in doc['ayurveda'].items():
                    lines.append(f"- {k.capitalize()}: {v}")
            if doc.get('content'):
                # Include a concise snippet
                snippet = doc['content']
                if len(snippet) > 600:
                    snippet = snippet[:600] + "..."
                if (lang == 'hi' and _has_devanagari(snippet)) or (lang != 'hi'):
                    lines.append(snippet)
        def _general_sections(q, lang):
            t = set(_tokenize(q))
            general = []
            if any(x in t for x in ['dal','lentil','pulse','moong','toor','arhar','chana','urad','masoor']):
                if lang == 'hi':
                    general.append("दालें पौध प्रोटीन और फाइबर का अच्छा स्रोत हैं। भिगोना एंटी-न्यूट्रिएंट्स कम करता है; अंकुरण से विटामिन और पाचन में सुधार होता है। जीरा, अदरक, हींग और हल्दी के साथ पकाना पाचन में सहायक है। अनाज के साथ मिलाने से अमीनो एसिड संतुलन बेहतर होता है।")
                    general.append("सामान्य मात्रा: प्रति भोजन लगभग 150–200 ग्राम पकी हुई दाल, सब्जियों के साथ लें।")
                else:
                    general.append("Lentils are rich in plant protein and fiber. Soaking reduces antinutrients; sprouting improves vitamins and digestibility. Cooking with cumin, ginger, asafoetida, and turmeric supports digestion. Pair with cereals to improve amino acid balance.")
                    general.append("Typical portions: ~150–200 g cooked dal per meal, combine with vegetables.")
            if any(x in t for x in ['cereal','grain','rice','wheat','millet','oats']):
                if lang == 'hi':
                    general.append("साबुत अनाज जटिल कार्बोहाइड्रेट, फाइबर और बी-विटामिन प्रदान करते हैं। परिष्कृत के बजाय साबुत रूप चुनें। अनाज और दाल साथ लेने से प्रोटीन गुणवत्ता बेहतर होती है।")
                    general.append("सामान्य मात्रा: प्रति भोजन ~150–200 ग्राम पका हुआ अनाज, गतिविधि के अनुसार समायोजित करें।")
                else:
                    general.append("Whole grains provide complex carbs, fiber, and B-vitamins. Prefer whole/minimally processed forms. Mixing grains with pulses yields more complete protein.")
                    general.append("Common portions: ~150–200 g cooked grain per meal, adjust for activity.")
            if any(x in t for x in ['vegetable','veg','greens','leafy']):
                general.append("सब्जियाँ विटामिन, खनिज, एंटीऑक्सिडेंट और फाइबर देती हैं। मौसमी और विविध रंगों को प्राथमिकता दें। हल्की भाप या सौटे पोषक तत्व बनाए रखते हैं।" if lang == 'hi' else "Vegetables supply vitamins, minerals, antioxidants, and fiber. Prefer seasonal diversity. Light steaming or sautéing preserves nutrients.")
            if any(x in t for x in ['ayurveda','dosha','vata','pitta','kapha']):
                general.append("आयुर्वेद में रस, वीर्य और विपाक के आधार पर दोष संतुलन पर जोर है। वात के लिए गर्म और नम; पित्त के लिए शीतल और मधुर/तिक्त; कफ के लिए हल्का, गरम और कषाय/कटु खाद्य। व्यक्तिगत अन्तर होता है।" if lang == 'hi' else "Ayurveda balances doshas using rasa, virya, vipaka. Vata often benefits from warm, moist foods; Pitta from cooling, mildly sweet/bitter; Kapha from light, warming, pungent foods.")
            if any(x in t for x in ['protein','carb','fat','fiber','vitamin','mineral','glycemic']):
                general.append("संतुलित थाली: दाल (प्रोटीन+फाइबर), अनाज (कार्ब), और सब्जियाँ (माइक्रोन्यूट्रिएंट्स)। फाइबर और जल सेवन पर ध्यान दें।" if lang == 'hi' else "Balanced plate: pulse (protein+fiber), grain (carbs), vegetables (micronutrients). Consider fiber and hydration.")
                general.append("सामान्यतः: प्रोटीन 20–30%, कार्ब 40–55%, वसा 25–35% (लक्ष्य/गतिविधि अनुसार)।" if lang == 'hi' else "Typical ranges: protein 20–30%, carbs 40–55%, fats 25–35% (adjust for goals/activity).")
            general.append("सामान्य मार्गदर्शन: साबुत खाद्य, पर्याप्त जल, नियमित भोजन समय और विविधता। विशेष स्थितियों में विशेषज्ञ से सलाह लें।" if lang == 'hi' else "General guidance: whole foods, hydration, regular meal timing, and variety. Consult a professional for specific conditions.")
            return general
        sections = _general_sections(query, lang) if not single_mode else []
        if sections:
            lines.append("\n" + L['general'])
            for s in sections:
                lines.append(f"- {s}")
        return "\n".join(lines)
    except Exception as e:
        print(f"Error generating response: {str(e)}")

def _smalltalk_or_help(query, lang):
    q = (query or "").strip().lower()
    hi_words = {'hi','hello','hey','namaste','नमस्ते','नमस्कार'}
    bye_words = {'bye','goodbye','see you','धन्यवाद','अलविदा'}
    thanks_words = {'thanks','thank you','धन्यवाद'}
    help_words = {'help','what can you do','capabilities','assist','सहायता','मदद'}
    who_words = {'who are you','about you','तुम कौन हो','आप कौन हैं'}
    if any(w in q for w in hi_words):
        return "नमस्ते! मैं आपके पोषण और आयुर्वेद संबंधित प्रश्नों में मदद कर सकता/सकती हूँ। आप किसी दाल/अनाज/सब्जी के पोषण या आयुर्वेदिक गुण पूछ सकते हैं, या कैलोरी लक्ष्य के साथ डाइट प्लान माँग सकते हैं।" if lang == 'hi' else "Hello! I can help with nutrition and Ayurveda questions. Ask about nutrition or Ayurvedic properties of lentils/grains/vegetables, or request a diet plan with a calorie target."
    if any(w in q for w in thanks_words):
        return "आपका स्वागत है!" if lang == 'hi' else "You're welcome!"
    if any(w in q for w in bye_words):
        return "धन्यवाद! फिर मिलेंगे।" if lang == 'hi' else "Thanks! See you again."
    if any(w in q for w in who_words):
        return "मैं पोषण और आयुर्वेद सहायक हूँ—CSV ज्ञान-आधार से जानकारी देता/देती हूँ, और आपकी पसंद के आधार पर सीखता/सीखती रहता/रहती हूँ।" if lang == 'hi' else "I'm a Nutrition & Ayurveda Assistant—answering from a CSV knowledge base and learning from your preferences."
    if any(w in q for w in help_words):
        return ("मैं आपके लिए ये कर सकता/सकती हूँ:\n- किसी खाद्य पदार्थ के पोषण/आयुर्वेदिक गुण बताना\n- पित्त/वात/कफ संतुलन के अनुसार सुझाव\n- 2000 kcal जैसा लक्ष्य देकर डाइट प्लान बनाना\nउदाहरण: \"मूंग दाल nutrition\", \"pitta balancing foods\", \"diet plan 2200 vegetarian\""
                if lang == 'hi'
                else "I can help you with:\n- Nutrition/Ayurvedic properties of foods\n- Vata/Pitta/Kapha balancing suggestions\n- Diet plans with calorie targets (e.g., 2000 kcal)\nExamples: \"moong dal nutrition\", \"pitta balancing foods\", \"diet plan 2200 vegetarian\"")
    # Generic friendly prompt
    return ("मुझे आपके प्रश्न का सटीक संदर्भ नहीं मिला। आप किसी खाद्य का नाम लिखकर पोषण/आयुर्वेद पूछें, या कैलोरी लक्ष्य देकर डाइट प्लान माँगें।"
            if lang == 'hi'
            else "I couldn't find a specific match. Ask for nutrition/Ayurvedic properties of a food, or request a diet plan with a calorie target.")

# API Endpoints
@app.route('/api/chat', methods=['POST'])
def chat():
    start_time = time.time()
    client_ip = request.remote_addr or 'unknown'

    
    try:
        # Rate limiting check
        if not rate_limit_check(client_ip, limit=10):
            return jsonify({
                'response': 'Too many requests. Please wait a moment before trying again.',
                'sources': []
            }), 429
        
        # Periodic cleanup
        cleanup_cache()
        
        # Check if request has JSON data
        if not request.is_json:
            return jsonify({
                'response': 'Invalid request format. Please send JSON data.',
                'sources': []
            }), 400

        data = request.get_json()
        query = data.get('message', '').strip()
        lang = (data.get('lang') or 'en').strip()[:2]
        
        if not query:
            return jsonify({
                'response': 'Please enter a message.',
                'sources': []
            }), 400
        
        try:
            # Search knowledge base for relevant context
            kb_results = search_knowledge_base(query, top_k=5, threshold=0.0)
            if kb_results and is_single_item_query(query, kb_results):
                kb_results = kb_results[:1]
            
            # Generate response using Gemini with knowledge base context
            response_text = generate_response(query, context_docs=kb_results if kb_results else None, client_ip=client_ip, lang=lang)
            
            # Update conversation memory
            update_conversation_memory(client_ip, query, response_text)
            
            # Prepare sources from knowledge base and Gemini Search (only include relevant ones)
            sources = []
            
            # Add knowledge base sources
            if kb_results:
                kb_sources = [{
                    'title': doc['title'],
                    'content': doc['content'][:200] + '...' if len(doc['content']) > 200 else doc['content'],
                    'source': 'knowledge_base',
                    'similarity': f"{doc['similarity']:.2f}"
                } for doc in kb_results]
                sources.extend(kb_sources)
            
            # Sort sources by relevance
            sources.sort(key=lambda x: float(x.get('similarity', 0)), reverse=True)
            
            # Log performance
            processing_time = time.time() - start_time
            print(f"Request processed in {processing_time:.2f}s for query: {query[:50]}...")
            
            return jsonify({
                'response': response_text,
                'sources': sources,
                'processing_time': f"{processing_time:.2f}s"
            })
            
        except Exception as e:
            print(f"Error processing chat request: {str(e)}")
            return jsonify({
                'response': "I'm having trouble generating a response. Please try again.",
                'sources': []
            }), 500
    
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {str(e)}")
        return jsonify({
            'response': 'An unexpected error occurred. Please try again later.',
            'sources': []
        }), 500

@app.route('/')
def serve_index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path == '@vite/client':
        return ("// stubbed vite client\nexport default {};", 200, {'Content-Type': 'application/javascript'})
    return send_from_directory(STATIC_FOLDER, path)

@app.route('/@vite/client')
def vite_client_stub():
    return ("// stubbed vite client\nexport default {};", 200, {'Content-Type': 'application/javascript'})

if __name__ == '__main__':
    # Load knowledge base on startup
    print("Loading knowledge base...")
    load_knowledge_base()
    

    
    # Start the server
    print("Starting server...")
    app.run(host='0.0.0.0', port=3000, debug=True)
