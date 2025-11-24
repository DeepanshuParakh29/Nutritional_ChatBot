import json
import os
import math
import time
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google.generativeai import GenerativeModel, configure, embed_content
from dotenv import load_dotenv
import requests
from functools import lru_cache
import threading
from collections import defaultdict

# Load environment variables from .env file
load_dotenv()

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'public')
KB_PATH = os.path.join(BASE_DIR, 'kb.json')

# API Key for Gemini
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')

# Google Search API credentials
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')

# Initialize Flask app
app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

# Initialize Gemini model
configure(api_key=GEMINI_API_KEY)
gemini_model = GenerativeModel('gemini-2.0-flash')

# Global variables for knowledge base
kb_docs = []
kb_vectors = []

# Performance optimization caches
response_cache = {}
search_cache = {}
embedding_cache = {}
request_queue = []
queue_lock = threading.Lock()
rate_limit_tracker = defaultdict(int)
last_cleanup = datetime.now()

# Advanced features
conversation_memory = {}
research_cache = {}
formatting_rules = {
    'max_paragraph_length': 200,
    'min_paragraph_length': 50,
    'paragraph_separator': '\n\n',
    'bullet_points': ['•', '-', '*', '→']
}

# Learning system
learning_database = {}
feedback_scores = {}
successful_responses = {}
knowledge_expansion = {}
LEARNING_DB_PATH = os.path.join(BASE_DIR, 'learning_database.json')

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

def load_learning_database():
    """Load the learning database from file."""
    global learning_database, feedback_scores, successful_responses, knowledge_expansion
    
    try:
        if os.path.exists(LEARNING_DB_PATH):
            with open(LEARNING_DB_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                learning_database = data.get('learning_database', {})
                feedback_scores = data.get('feedback_scores', {})
                successful_responses = data.get('successful_responses', {})
                knowledge_expansion = data.get('knowledge_expansion', {})
            print(f"Loaded learning database with {len(learning_database)} entries")
    except Exception as e:
        print(f"Error loading learning database: {str(e)}")
        # Initialize empty databases
        learning_database = {}
        feedback_scores = {}
        successful_responses = {}
        knowledge_expansion = {}

def save_learning_database():
    """Save the learning database to file."""
    try:
        data = {
            'learning_database': learning_database,
            'feedback_scores': feedback_scores,
            'successful_responses': successful_responses,
            'knowledge_expansion': knowledge_expansion,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(LEARNING_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Learning database saved successfully")
    except Exception as e:
        print(f"Error saving learning database: {str(e)}")

def learn_from_interaction(query, response, sources, client_ip):
    """Learn from successful interactions."""
    # Generate query signature for learning
    query_signature = hashlib.md5(query.lower().encode()).hexdigest()
    
    # Extract key concepts from the query
    key_concepts = extract_key_concepts(query)
    
    # Store the successful interaction
    if query_signature not in learning_database:
        learning_database[query_signature] = {
            'query': query,
            'key_concepts': key_concepts,
            'responses': [],
            'total_interactions': 0,
            'success_score': 0.0
        }
    
    # Add this response to the learning database
    response_entry = {
        'response': response,
        'sources': sources,
        'timestamp': datetime.now().isoformat(),
        'client_ip': client_ip,
        'feedback_score': 0.0  # Will be updated based on user feedback
    }
    
    learning_database[query_signature]['responses'].append(response_entry)
    learning_database[query_signature]['total_interactions'] += 1
    
    # Limit stored responses per query to prevent database bloat
    if len(learning_database[query_signature]['responses']) > 10:
        learning_database[query_signature]['responses'] = learning_database[query_signature]['responses'][-10:]
    
    # Expand knowledge base with new information
    expand_knowledge(query, response, key_concepts)
    
    # Save learning database periodically
    if learning_database[query_signature]['total_interactions'] % 5 == 0:
        save_learning_database()

def extract_key_concepts(query):
    """Extract key concepts from query for learning."""
    # Simple concept extraction - can be enhanced with NLP
    import re
    
    # Remove common words and extract meaningful terms
    common_words = {'what', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'about', 'how', 'why', 'when', 'where'}
    
    words = re.findall(r'\b\w+\b', query.lower())
    key_concepts = [word for word in words if word not in common_words and len(word) > 2]
    
    # Also extract nutritional/ayurvedic terms
    nutritional_terms = ['protein', 'carbohydrate', 'fat', 'fiber', 'vitamin', 'mineral', 'calorie', 'nutrition']
    ayurvedic_terms = ['dosha', 'vata', 'pitta', 'kapha', 'ayurveda', 'herbal', 'medicine', 'treatment']
    
    for term in nutritional_terms + ayurvedic_terms:
        if term in query.lower():
            key_concepts.append(term)
    
    return list(set(key_concepts))  # Remove duplicates

def expand_knowledge(query, response, key_concepts):
    """Expand knowledge base with new information."""
    for concept in key_concepts:
        if concept not in knowledge_expansion:
            knowledge_expansion[concept] = {
                'definitions': [],
                'examples': [],
                'related_queries': [],
                'confidence_score': 0.0
            }
        
        # Extract potential definitions from response
        sentences = response.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if concept.lower() in sentence.lower() and len(sentence) > 20:
                # This might be a definition or explanation
                if concept.lower() in sentence[:50].lower():  # Concept appears early in sentence
                    knowledge_expansion[concept]['definitions'].append(sentence)
                    knowledge_expansion[concept]['confidence_score'] += 0.1
        
        # Add related query
        if query not in knowledge_expansion[concept]['related_queries']:
            knowledge_expansion[concept]['related_queries'].append(query)
        
        # Limit stored information
        if len(knowledge_expansion[concept]['definitions']) > 5:
            knowledge_expansion[concept]['definitions'] = knowledge_expansion[concept]['definitions'][-5:]
        if len(knowledge_expansion[concept]['related_queries']) > 10:
            knowledge_expansion[concept]['related_queries'] = knowledge_expansion[concept]['related_queries'][-10:]

def get_learned_context(query):
    """Get context from learned interactions."""
    query_signature = hashlib.md5(query.lower().encode()).hexdigest()
    key_concepts = extract_key_concepts(query)
    
    learned_context = []
    
    # Check for exact or similar queries
    if query_signature in learning_database:
        entry = learning_database[query_signature]
        if entry['responses']:
            # Get the best previous response
            best_response = max(entry['responses'], key=lambda x: x.get('feedback_score', 0))
            learned_context.append(f"Previous successful answer to similar question: {best_response['response'][:200]}...")
    
    # Check for concept-based learning
    for concept in key_concepts:
        if concept in knowledge_expansion:
            concept_info = knowledge_expansion[concept]
            if concept_info['definitions']:
                learned_context.append(f"Learned information about {concept}: {concept_info['definitions'][0][:150]}...")
    
    return '\n'.join(learned_context)

def update_feedback(query_signature, response_index, feedback_score):
    """Update feedback score for a response."""
    if query_signature in learning_database:
        responses = learning_database[query_signature]['responses']
        if 0 <= response_index < len(responses):
            responses[response_index]['feedback_score'] = feedback_score
            
            # Update overall success score
            total_score = sum(r.get('feedback_score', 0) for r in responses)
            learning_database[query_signature]['success_score'] = total_score / len(responses)
            
            save_learning_database()

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

def is_follow_up_query(query, client_ip):
    """Detect if this is a follow-up query that needs more research."""
    follow_up_indicators = [
        'tell me more', 'more about', 'explain further', 'details',
        'elaborate', 'expand', 'go deeper', 'research', 'investigate',
        'what else', 'additional', 'further information', 'comprehensive'
    ]
    
    query_lower = query.lower()
    is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators)
    
    # Also check if it references previous topics
    if client_ip in conversation_memory:
        recent_queries = [interaction['query'].lower() for interaction in conversation_memory[client_ip][-3:]]
        for recent_query in recent_queries:
            # Check for common nouns/keywords that might indicate follow-up
            words = recent_query.split()
            for word in words:
                if len(word) > 4 and word in query_lower:  # Significant word overlap
                    is_follow_up = True
                    break
    
    return is_follow_up

def deep_research(query, num_results=8):
    """Perform deeper research using Gemini's knowledge."""
    research_queries = [
        f"{query} comprehensive overview",
        f"{query} scientific research and studies",
        f"{query} detailed analysis and benefits",
        f"{query} practical applications and uses"
    ]
    
    all_results = []
    
    for research_query in research_queries[:3]:  # Limit to prevent API abuse
        cache_key = get_cache_key(research_query, f"gemini_deep_research_{num_results}")
        
        if cache_key in research_cache:
            timestamp, cached_results = research_cache[cache_key]
            if time.time() - timestamp < 3600:  # 1 hour cache for research
                all_results.extend(cached_results)
                continue
        
        try:
            results = gemini_search(research_query, num_results=3)
            research_cache[cache_key] = (time.time(), results)
            all_results.extend(results)
            time.sleep(1)  # Rate limiting between searches
        except Exception as e:
            print(f"Deep research query failed: {research_query} - {str(e)}")
            # Try fallback search for this query
            try:
                fallback_results = fallback_search(research_query, num_results=2)
                all_results.extend(fallback_results)
            except Exception as fallback_error:
                print(f"Fallback search also failed: {str(fallback_error)}")
    
    # Remove duplicates based on title similarity
    unique_results = []
    seen_titles = set()
    
    for result in all_results:
        title_lower = result['title'].lower()
        # Simple deduplication - skip if title is too similar
        is_duplicate = False
        for seen_title in seen_titles:
            if title_lower in seen_title or seen_title in title_lower:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_results.append(result)
            seen_titles.add(title_lower)
    
    return unique_results[:num_results]

def format_response_text(text):
    """Format response text with proper paragraph alignment and structure."""
    if not text:
        return text
    
    # Split into paragraphs
    paragraphs = text.split('\n')
    formatted_paragraphs = []
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        # Handle bullet points
        is_bullet = False
        for bullet in formatting_rules['bullet_points']:
            if paragraph.startswith(bullet):
                is_bullet = True
                break
        
        if is_bullet:
            # Keep bullet points as-is
            formatted_paragraphs.append(paragraph)
        else:
            # Split long paragraphs
            if len(paragraph) > formatting_rules['max_paragraph_length']:
                # Try to split at sentence boundaries
                sentences = paragraph.split('. ')
                current_para = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    if len(current_para + sentence + '. ') <= formatting_rules['max_paragraph_length']:
                        current_para += sentence + '. '
                    else:
                        if current_para:
                            formatted_paragraphs.append(current_para.strip())
                        current_para = sentence + '. '
                
                if current_para:
                    formatted_paragraphs.append(current_para.strip())
            else:
                formatted_paragraphs.append(paragraph)
    
    # Join with proper spacing
    formatted_text = formatting_rules['paragraph_separator'].join(formatted_paragraphs)
    
    # Clean up extra spaces
    formatted_text = formatted_text.replace('  ', ' ').replace(' \n', '\n')
    
    return formatted_text.strip()

def load_knowledge_base():
    """Load the knowledge base from JSON file and load/generate embeddings."""
    global kb_docs, kb_vectors
    
    # Path to store embeddings cache
    EMBEDDINGS_CACHE_PATH = os.path.join(BASE_DIR, 'embeddings_cache.json')
    
    if not os.path.exists(KB_PATH):
        print(f"Warning: Knowledge base file not found at {KB_PATH}")
        return
    
    try:
        # Load knowledge base
        with open(KB_PATH, 'r', encoding='utf-8') as f:
            kb_docs = json.load(f)
        
        print(f"Loaded {len(kb_docs)} items from knowledge base")
        
        # Try to load cached embeddings if they exist
        cached_embeddings = {}
        if os.path.exists(EMBEDDINGS_CACHE_PATH):
            try:
                with open(EMBEDDINGS_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cached_embeddings = json.load(f)
                print(f"Loaded {len(cached_embeddings)} cached embeddings")
            except Exception as e:
                print(f"Warning: Could not load embeddings cache: {str(e)}")
        
        # Process each document
        processed_docs = []
        embeddings_failed = False
        for doc in kb_docs:
            doc_id = doc.get('id')
            content = f"{doc.get('title', '')} {doc.get('content', '')}"
            
            # Try to get cached embedding first
            if doc_id in cached_embeddings:
                doc['embedding'] = cached_embeddings[doc_id]
                processed_docs.append(doc)
                continue
                
            # If no cached embedding and we haven't failed yet, try to generate one
            if not embeddings_failed:
                try:
                    response = embed_content(
                        model='models/embedding-001',
                        content=content
                    )
                    doc['embedding'] = response['embedding']
                    # Add to cache
                    cached_embeddings[doc_id] = response['embedding']
                    processed_docs.append(doc)
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error generating embedding: {str(e)}")
                    print("Skipping embedding generation for remaining documents due to quota limits")
                    embeddings_failed = True
                    # Add document without embedding
                    processed_docs.append(doc)
            else:
                # Add document without embedding since we already hit quota limits
                processed_docs.append(doc)
        
        # Update the cache file only if we have new embeddings
        if cached_embeddings and not embeddings_failed:
            try:
                with open(EMBEDDINGS_CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(cached_embeddings, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Warning: Could not save embeddings cache: {str(e)}")
        
        # Update kb_docs with processed docs
        kb_docs = processed_docs
        docs_with_embeddings = len([doc for doc in kb_docs if doc.get('embedding')])
        print(f"Successfully processed {len(kb_docs)} documents ({docs_with_embeddings} with embeddings)")
        
    except Exception as e:
        print(f"Error loading knowledge base: {str(e)}")
        raise

def search_knowledge_base(query, top_k=3, threshold=0.5):
    """Search the knowledge base for relevant documents with caching and optimization."""
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
        # Get query embedding with retry logic
        max_retries = 3
        query_embedding = None
        for attempt in range(max_retries):
            try:
                response = embed_content(model='models/embedding-001', content=query)
                query_embedding = response['embedding']
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to get query embedding after {max_retries} attempts: {str(e)}")
                    print("Falling back to keyword search...")
                    results = fallback_keyword_search(query, top_k)
                    # Cache the results
                    search_cache[cache_key] = (time.time(), results)
                    return results
                time.sleep(1)  # Wait before retrying
        
        # Calculate similarity scores with optimized ranking
        results = []
        for doc in kb_docs:
            if not doc.get('embedding'):
                continue
                
            similarity = cosine_similarity(query_embedding, doc['embedding'])
            
            # Apply boosted ranking for better results
            boosted_score = similarity
            
            # Boost score if query terms appear in title
            query_terms = query.lower().split()
            title_lower = doc.get('title', '').lower()
            for term in query_terms:
                if term in title_lower:
                    boosted_score += 0.2  # Boost for title matches
            
            # Boost score for recent/popular documents (if we had that data)
            # For now, just use the boosted similarity
            
            if boosted_score >= threshold:
                results.append({
                    'id': doc.get('id'),
                    'title': doc.get('title', 'No title'),
                    'content': doc.get('content', ''),
                    'similarity': boosted_score,
                    'source': 'knowledge_base',
                    'nutrition': doc.get('nutrition', {}),
                    'ayurveda': doc.get('ayurveda', {})
                })
        
        # Sort by boosted similarity score (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        final_results = results[:top_k]
        
        # Cache the results
        search_cache[cache_key] = (time.time(), final_results)
        
        return final_results
    
    except Exception as e:
        print(f"Error searching knowledge base: {str(e)}")
        results = fallback_keyword_search(query, top_k)
        # Cache the fallback results
        search_cache[cache_key] = (time.time(), results)
        return results

def fallback_keyword_search(query, top_k=3):
    """Fallback keyword-based search when embeddings are not available."""
    query_lower = query.lower()
    query_terms = query_lower.split()
    
    results = []
    for doc in kb_docs:
        title_lower = doc.get('title', '').lower()
        content_lower = doc.get('content', '').lower()
        category_lower = doc.get('category', '').lower()
        
        # Calculate keyword match score
        score = 0
        for term in query_terms:
            if term in title_lower:
                score += 3  # Title matches are worth more
            if term in content_lower:
                score += 1
            if term in category_lower:
                score += 2
        
        if score > 0:
            results.append({
                'id': doc.get('id'),
                'title': doc.get('title', 'No title'),
                'content': doc.get('content', ''),
                'similarity': min(score / 10.0, 1.0),  # Normalize to 0-1 range
                'source': 'knowledge_base',
                'nutrition': doc.get('nutrition', {}),
                'ayurveda': doc.get('ayurveda', {})
            })
    
    # Sort by score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]

def gemini_search(query, num_results=5):
    """Use Gemini to search for information based on its training data."""
    # Check cache first
    cache_key = get_cache_key(query, f"gemini_search_{num_results}")
    if cache_key in search_cache:
        timestamp, cached_results = search_cache[cache_key]
        # Use cache if less than 30 minutes old for search results
        if time.time() - timestamp < 1800:
            print(f"Using cached Gemini search results for: {query}")
            return cached_results
    
    try:
        # Create a search prompt for Gemini
        search_prompt = f"""
        Search for comprehensive information about: {query}
        
        Please provide search-like results with the following format for each result:
        1. Title: [Clear, descriptive title]
        2. Summary: [2-3 sentence summary]
        3. Key Information: [Bulleted list of key facts]
        
        Provide {num_results} distinct results covering different aspects of the topic.
        Focus on nutrition, health benefits, scientific research, and practical applications.
        """
        
        response = gemini_model.generate_content(search_prompt)
        response_text = response.text
        
        # Parse the Gemini response into search-like results
        results = parse_gemini_search_response(response_text, query)
        
        print(f"Gemini search returned {len(results)} results for query: {query}")
        
        # Cache the results
        search_cache[cache_key] = (time.time(), results)
        
        return results
        
    except Exception as e:
        print(f"Error in Gemini search: {str(e)}")
        return fallback_search(query, num_results)

def parse_gemini_search_response(response_text, query):
    """Parse Gemini's response into structured search results."""
    results = []
    
    # Split by numbered items or sections
    sections = response_text.split('\n\n')
    
    current_result = {}
    result_count = 0
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
        
        # Check if this starts a new result
        if section and (section[0].isdigit() or section.lower().startswith('title:')):
            # Save previous result if exists
            if current_result and 'title' in current_result:
                # Ensure all required keys exist
                if 'snippet' not in current_result:
                    current_result['snippet'] = current_result.get('title', '') + ' - Additional information available.'
                if 'link' not in current_result:
                    current_result['link'] = f"gemini://search/{query.replace(' ', '_')}"
                results.append(current_result)
                result_count += 1
                if result_count >= 5:  # Limit results
                    break
            
            # Start new result
            current_result = {'source': 'gemini_search'}
            
            # Parse title
            if 'Title:' in section:
                title = section.split('Title:')[1].split('\n')[0].strip()
                current_result['title'] = title
            elif section[0].isdigit() and '.' in section:
                title = section.split('.')[1].strip()
                current_result['title'] = title
        
        # Parse summary
        if 'Summary:' in section:
            summary = section.split('Summary:')[1].split('\n')[0].strip()
            current_result['snippet'] = summary
        
        # Parse key information
        if 'Key Information:' in section or 'Key facts:' in section:
            key_info = section.split('Key')[1].strip()
            current_result['snippet'] = current_result.get('snippet', '') + ' ' + key_info
    
    # Add the last result
    if current_result and 'title' in current_result:
        # Ensure all required keys exist
        if 'snippet' not in current_result:
            current_result['snippet'] = current_result.get('title', '') + ' - Additional information available.'
        if 'link' not in current_result:
            current_result['link'] = f"gemini://search/{query.replace(' ', '_')}"
        results.append(current_result)
    
    # If parsing failed, create a simple result
    if not results:
        results.append({
            'title': f"Information about {query}",
            'snippet': response_text[:300] + '...' if len(response_text) > 300 else response_text,
            'link': f"gemini://search/{query.replace(' ', '_')}",
            'source': 'gemini_search'
        })
    
    # Ensure all results have required keys
    for result in results:
        if 'snippet' not in result:
            result['snippet'] = result.get('title', 'No summary available.')
        if 'link' not in result:
            result['link'] = f"gemini://search/{query.replace(' ', '_')}"
        if 'source' not in result:
            result['source'] = 'gemini_search'
    
    return results[:5]  # Limit to 5 results

def fallback_search(query, num_results=3):
    """Fallback search using knowledge base and simulated web results."""
    print(f"Using fallback search for: {query}")
    
    # Search knowledge base first
    kb_results = search_knowledge_base(query, top_k=num_results, threshold=0.3)
    
    # Convert to search-like format
    fallback_results = []
    for doc in kb_results:
        fallback_results.append({
            'title': doc.get('title', ''),
            'snippet': doc.get('content', '')[:150] + '...' if len(doc.get('content', '')) > 150 else doc.get('content', ''),
            'link': f"knowledge_base://{doc.get('id', '')}",
            'source': 'knowledge_base_search'
        })
    
    # Add some general nutrition/Ayurveda "simulated" results if needed
    if len(fallback_results) < num_results:
        general_topics = [
            {
                'title': 'Nutritional Guidelines and Health Benefits',
                'snippet': 'Comprehensive information about nutritional values, health benefits, and dietary recommendations for various foods and ingredients.',
                'link': 'general://nutrition_guidelines',
                'source': 'general_knowledge'
            },
            {
                'title': 'Ayurvedic Principles and Food Properties',
                'snippet': 'Traditional Ayurvedic knowledge about food properties, dosha balancing, and therapeutic benefits of various ingredients.',
                'link': 'general://ayurvedic_principles',
                'source': 'general_knowledge'
            }
        ]
        
        for topic in general_topics:
            if len(fallback_results) < num_results:
                # Check if topic is relevant to query
                query_lower = query.lower()
                topic_lower = topic['title'].lower()
                
                if any(word in topic_lower for word in query_lower.split() if len(word) > 3):
                    fallback_results.append(topic)
    
    return fallback_results[:num_results]

def generate_response(query, context_docs=None, client_ip=None):
    """Generate a response using the Gemini model with advanced research and formatting."""
    # Check cache first
    context_hash = ""
    if context_docs:
        context_hash = hashlib.md5(json.dumps([doc['id'] for doc in context_docs], sort_keys=True).encode()).hexdigest()
    
    cache_key = get_cache_key(query, f"{context_hash}_{client_ip}")
    if cache_key in response_cache:
        timestamp, cached_response = response_cache[cache_key]
        # Use cache if less than 10 minutes old
        if time.time() - timestamp < 600:
            print(f"Using cached response for: {query}")
            return cached_response
    
    try:
        # Check if this is a follow-up query
        is_follow_up = is_follow_up_query(query, client_ip) if client_ip else False
        
        # Get conversation context
        conversation_context = get_conversation_context(client_ip) if client_ip else ""
        
        # Prepare the prompt with system message and context
        prompt_parts = [
            "You are a helpful nutrition and Ayurveda assistant. "
            "Provide clear, accurate, and helpful responses based on the following context and your knowledge.\n\n"
            f"Question: {query}\n\n"
        ]
        
        # Add conversation context if available
        if conversation_context:
            prompt_parts.append("Conversation Context:\n")
            prompt_parts.append(conversation_context + "\n\n")
        
        # Add learned context if available
        learned_context = get_learned_context(query)
        if learned_context:
            prompt_parts.append("Learned Context from Previous Interactions:\n")
            prompt_parts.append(learned_context + "\n\n")
        
        # Add knowledge base context if available
        if context_docs and any(doc['similarity'] > 0.7 for doc in context_docs):
            prompt_parts.append("Context from knowledge base:\n")
            
            for i, doc in enumerate(context_docs, 1):
                if doc['similarity'] < 0.7:
                    continue
                    
                doc_text = f"--- Document {i} ---\n"
                doc_text += f"Title: {doc.get('title', 'No title')}\n"
                
                # Include nutrition info if available
                if 'nutrition' in doc:
                    doc_text += "\nNutritional Information (per 100g):\n"
                    for key, value in doc['nutrition'].items():
                        doc_text += f"- {key.capitalize()}: {value}\n"
                
                # Include Ayurvedic properties if available
                if 'ayurveda' in doc:
                    doc_text += "\nAyurvedic Properties:\n"
                    for key, value in doc['ayurveda'].items():
                        doc_text += f"- {key.capitalize()}: {value}\n"
                
                doc_text += f"\n{doc.get('content', '')}\n\n"
                prompt_parts.append(doc_text)
        
        # Perform search based on query type
        if is_follow_up:
            # Deep research for follow-up queries
            prompt_parts.append("Deep Research Context:\n")
            gemini_results = deep_research(query, num_results=8)
        else:
            # Standard Gemini Search
            gemini_results = gemini_search(query, num_results=3)
        
        if gemini_results:
            for i, result in enumerate(gemini_results, 1):
                search_text = f"--- Search Result {i} ---\n"
                search_text += f"Title: {result.get('title', '')}\n"
                search_text += f"Summary: {result.get('snippet', '')}\n"
                if result.get('link'):
                    search_text += f"Reference: {result.get('link', '')}\n"
                search_text += "\n"
                prompt_parts.append(search_text)
        
        # Add enhanced instructions for the model
        instructions = [
            "\nInstructions:\n"
            "1. Provide a clear, accurate, and helpful response based on the context and your knowledge.\n"
            "2. Use the knowledge base and search results to provide comprehensive information.\n"
            "3. If this is a follow-up query, provide additional details and deeper insights.\n"
            "4. Structure your response with proper formatting:\n"
            "   - Keep paragraphs between 50-200 characters for readability\n"
            "   - Use bullet points for lists and key information (start with •)\n"
            "   - Separate different topics with clear paragraph breaks\n"
            "   - Use **double asterisks** for important terms and emphasis\n"
            "   - Use *single asterisks* for italic emphasis when appropriate\n"
            "5. If the information is not sufficient in the context, use your general knowledge to provide a helpful response.\n"
            "6. For health-related questions, always recommend consulting with a healthcare professional for personalized advice.\n"
            "7. When using search results, cite the sources appropriately.\n"
            "8. Format your response in clear, readable paragraphs with proper spacing.\n\n"
        ]
        
        if is_follow_up:
            instructions.append(
                "9. Since this is a follow-up query, provide more detailed and comprehensive information.\n"
                "10. Expand on previous topics and provide additional insights or research findings.\n\n"
            )
        
        instructions.append("Answer:")
        prompt_parts.extend(instructions)
        
        # Generate response using Gemini
        response = gemini_model.generate_content("".join(prompt_parts))
        response_text = response.text
        
        # Format the response for proper paragraph alignment
        formatted_response = format_response_text(response_text)
        
        # Cache the formatted response
        response_cache[cache_key] = (time.time(), formatted_response)
        
        return formatted_response
    
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return "I'm sorry, I encountered an error while processing your request. Please try again."

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
        
        if not query:
            return jsonify({
                'response': 'Please enter a message.',
                'sources': []
            }), 400
        
        try:
            # Search knowledge base for relevant context
            kb_results = search_knowledge_base(query)
            
            # Generate response using Gemini with knowledge base context
            response_text = generate_response(
                query, 
                context_docs=kb_results if kb_results and any(doc['similarity'] > 0.5 for doc in kb_results) else None,
                client_ip=client_ip
            )
            
            # Update conversation memory
            update_conversation_memory(client_ip, query, response_text)
            
            # Prepare sources from knowledge base and Gemini Search (only include relevant ones)
            sources = []
            
            # Add knowledge base sources
            if kb_results and any(doc['similarity'] > 0.5 for doc in kb_results):
                kb_sources = [{
                    'title': doc['title'],
                    'content': doc['content'][:200] + '...' if len(doc['content']) > 200 else doc['content'],
                    'source': 'knowledge_base',
                    'similarity': f"{doc['similarity']:.2f}"
                } for doc in kb_results if doc['similarity'] > 0.5]
                sources.extend(kb_sources)
            
            # Add Gemini Search sources
            gemini_results = gemini_search(query, num_results=2)
            if gemini_results:
                search_sources = [{
                    'title': result['title'],
                    'content': result['snippet'],
                    'source': 'gemini_search',
                    'link': result.get('link', '')
                } for result in gemini_results]
                sources.extend(search_sources)
                
            # Sort sources by relevance (knowledge base first, then Gemini search)
            sources.sort(key=lambda x: (x['source'] != 'knowledge_base', float(x.get('similarity', 0))), reverse=True)
            
            # Learn from this interaction
            learn_from_interaction(query, response_text, sources, client_ip)
            
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
            # Try to get a response directly from Gemini if other methods fail
            try:
                response = gemini_model.generate_content(
                    f"The user asked: {query}\n\n"
                    "Provide a helpful response. If this is a health-related question, "
                    "recommend consulting a healthcare professional for personalized advice."
                )
                return jsonify({
                    'response': response.text,
                    'sources': [{
                        'title': 'Generated by Gemini',
                        'content': 'This response was generated by Gemini based on general knowledge.',
                        'source': 'generated'
                    }]
                })
            except Exception as fallback_error:
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
    return send_from_directory(STATIC_FOLDER, path)

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback for learning improvement."""
    try:
        data = request.get_json()
        query_signature = data.get('query_signature')
        response_index = data.get('response_index', 0)
        feedback_score = data.get('feedback_score', 0)  # -1 to 1 scale
        
        if query_signature and feedback_score:
            update_feedback(query_signature, response_index, feedback_score)
            return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid feedback data'}), 400
            
    except Exception as e:
        print(f"Error processing feedback: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to process feedback'}), 500

if __name__ == '__main__':
    # Load knowledge base on startup
    print("Loading knowledge base...")
    load_knowledge_base()
    
    # Initialize learning system
    print("Initializing learning system...")
    load_learning_database()
    
    # Start the server
    print("Starting server...")
    app.run(host='0.0.0.0', port=3000, debug=True)
