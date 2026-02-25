import os
import json
from flask import Flask, request, jsonify
import importlib
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
import sys
if ROOT not in sys.path:
    sys.path.append(ROOT)

app = Flask(__name__)

# Load knowledge base once at startup
try:
    app_module = importlib.import_module("app")
    app_module.load_knowledge_base()
except Exception as e:
    print(f"Error loading knowledge base: {e}")
    app_module = None

@app.route("/api/chat", methods=["POST"])
def chat():
    if not app_module:
        return jsonify({"response":"Chatbot is currently initializing. Please try again in a moment.","sources":[]}), 503
    
    start_time = time.time()
    client_ip = request.remote_addr or "unknown"
    
    try:
        # Rate limiting
        if hasattr(app_module, 'rate_limit_check') and not app_module.rate_limit_check(client_ip, limit=10):
            return jsonify({"response":"Too many requests. Please wait a moment before trying again.","sources":[]}), 429
        
        # Cleanup if available
        if hasattr(app_module, 'cleanup_cache'):
            app_module.cleanup_cache()
        
        if not request.is_json:
            return jsonify({"response":"Invalid request format. Please send JSON data.","sources":[]}), 400
            
        data = request.get_json()
        query = (data.get("message") or "").strip()
        lang = (data.get("lang") or "en")[:2]
        
        if not query:
            return jsonify({"response":"Please enter a message.","sources":[]}), 400
        
        # Search knowledge base
        kb_results = None
        if hasattr(app_module, 'search_knowledge_base'):
            kb_results = app_module.search_knowledge_base(query, top_k=5, threshold=0.0)
        
        # Generate response
        response_text = "I'm here to help with nutritional and Ayurvedic information about Indian foods."
        if hasattr(app_module, 'generate_response'):
            response_text = app_module.generate_response(query, context_docs=kb_results if kb_results else None, client_ip=client_ip, lang=lang)
        
        # Update conversation memory if available
        if hasattr(app_module, 'update_conversation_memory'):
            app_module.update_conversation_memory(client_ip, query, response_text)
        
        # Prepare sources
        sources = []
        if kb_results:
            kb_sources = [{
                "title": doc.get("title", "Unknown"),
                "content": doc.get("content", "")[:200] + "..." if len(doc.get("content", "")) > 200 else doc.get("content", ""),
                "source": "knowledge_base",
                "similarity": f"{doc.get('similarity', 0):.2f}"
            } for doc in kb_results]
            sources.extend(kb_sources)
        
        sources.sort(key=lambda x: float(x.get("similarity", 0)), reverse=True)
        processing_time = time.time() - start_time
        
        return jsonify({
            "response": response_text,
            "sources": sources,
            "processing_time": f"{processing_time:.2f}s"
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({
            "response":"I'm having trouble generating a response. Please try again.",
            "sources": []
        }), 500

if __name__ == "__main__":
    app.run()
