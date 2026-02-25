import os
import json
from flask import Flask, request, jsonify
import csv
import ast

app = Flask(__name__)

# Simple knowledge base loading
def load_simple_knowledge():
    kb = []
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        kb_path = os.path.join(base_path, 'knowledge_base.csv')
        
        if os.path.exists(kb_path):
            with open(kb_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('title') and row.get('content'):
                        kb.append({
                            'title': row['title'].strip(),
                            'content': row['content'].strip()[:500],
                            'category': row.get('category', '').strip()
                        })
                        if len(kb) >= 100:  # Limit for performance
                            break
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
    
    return kb

KNOWLEDGE_BASE = load_simple_knowledge()

def simple_search(query, top_k=3):
    query = query.lower()
    results = []
    
    for item in KNOWLEDGE_BASE:
        score = 0
        if query in item['title'].lower():
            score += 3
        if query in item['content'].lower():
            score += 1
        
        if score > 0:
            results.append({
                'title': item['title'],
                'content': item['content'],
                'similarity': min(score / 4.0, 1.0)
            })
    
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or not data.get('message'):
            return jsonify({'response': 'Please provide a message.', 'sources': []}), 400
        
        query = data['message'].strip()
        lang = data.get('lang', 'en')[:2]
        
        # Simple search
        results = simple_search(query, top_k=3)
        
        if results:
            response = f"Based on your query about '{query}', I found information about:\n\n"
            for i, result in enumerate(results, 1):
                response += f"{i}. **{result['title']}**\n{result['content']}\n\n"
            
            sources = [{'title': r['title'], 'content': r['content'], 'similarity': f"{r['similarity']:.2f}"} for r in results]
        else:
            response = f"I don't have specific information about '{query}' in my knowledge base. Please try asking about lentils, grains, or Ayurvedic properties."
            sources = []
        
        return jsonify({
            'response': response,
            'sources': sources,
            'processing_time': '0.5s'
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'response': 'I encountered an error processing your request. Please try again.',
            'sources': []
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
