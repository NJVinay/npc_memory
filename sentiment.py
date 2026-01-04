from functools import lru_cache
from typing import Union, List

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ transformers/torch not available. Falling back to TextBlob for sentiment analysis.")

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Load RoBERTa tokenizer and model for sentiment analysis (cached)
_tokenizer = None
_model = None
_model_load_failed = False

def get_sentiment_model():
    """Lazy load sentiment analysis model to reduce startup time."""
    global _tokenizer, _model, _model_load_failed
    
    if _model_load_failed:
        return None, None
    
    if _tokenizer is None or _model is None:
        try:
            if not TRANSFORMERS_AVAILABLE:
                _model_load_failed = True
                return None, None
            
            _tokenizer = AutoTokenizer.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")
            _model = AutoModelForSequenceClassification.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")
            print("✅ Loaded RoBERTa sentiment model")
        except Exception as e:
            print(f"⚠️ Failed to load RoBERTa model: {e}")
            _model_load_failed = True
            return None, None
    
    return _tokenizer, _model

# Sentiment labels as per model
LABELS = ['negative', 'neutral', 'positive']

def _textblob_sentiment(text: str) -> str:
    """Fallback sentiment analysis using TextBlob."""
    if not TEXTBLOB_AVAILABLE:
        return "neutral"
    
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        if polarity > 0.1:
            return "positive"
        elif polarity < -0.1:
            return "negative"
        else:
            return "neutral"
    except Exception:
        return "neutral"

@lru_cache(maxsize=1000)
def analyze_sentiment_cached(text: str) -> str:
    """Cached version of sentiment analysis for repeated queries.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Sentiment label: 'negative', 'neutral', or 'positive'
    """
    return _analyze_sentiment_internal(text)

def _analyze_sentiment_internal(text: str) -> str:
    """Internal sentiment analysis implementation."""
    tokenizer, model = get_sentiment_model()
    
    # Fallback to TextBlob if model not available
    if tokenizer is None or model is None:
        return _textblob_sentiment(text)
    
    try:
        # Tokenize input text for model
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        
        # Disable gradient calculations for inference
        with torch.no_grad():
            logits = model(**inputs).logits

        # Get index of highest scoring class
        predicted_class = torch.argmax(logits, dim=1).item()

        # Return corresponding sentiment label
        return LABELS[predicted_class]
    
    except Exception as e:
        print(f"⚠️ Sentiment analysis error: {e}")
        return _textblob_sentiment(text)

def analyze_sentiment(input_data: Union[str, dict]) -> str:
    """Analyze sentiment of the input text or dict containing 'response' key.
    
    Args:
        input_data: Text string or dict with a 'response' field containing text
        
    Returns:
        str: One of 'negative', 'neutral', or 'positive' based on sentiment classification
        
    Raises:
        ValueError: If input is invalid or empty
    """
    # Extract text from dict or use input directly if string
    if isinstance(input_data, dict):
        text = input_data.get("response", "")
    else:
        text = str(input_data) if input_data is not None else ""

    text = text.strip().lower()
    if not text:
        return "neutral"
    
    # Use cached version for better performance
    return analyze_sentiment_cached(text)

def analyze_sentiment_batch(texts: List[str]) -> List[str]:
    """Analyze sentiment for multiple texts in batch for better performance.
    
    Args:
        texts: List of text strings to analyze
        
    Returns:
        List of sentiment labels corresponding to each input text
    """
    if not texts:
        return []
    
    tokenizer, model = get_sentiment_model()
    
    # Preprocess texts
    processed_texts = [str(t).strip().lower() if t else "" for t in texts]
    
    # If model not available, use TextBlob fallback
    if tokenizer is None or model is None:
        return [_textblob_sentiment(text) if text else "neutral" for text in processed_texts]
    
    results = []
    
    try:
        # TRUE batch processing with PyTorch
        non_empty_texts = []
        non_empty_indices = []
        
        for i, text in enumerate(processed_texts):
            if text:
                non_empty_texts.append(text)
                non_empty_indices.append(i)
            else:
                results.insert(i, "neutral")
        
        if non_empty_texts:
            # Batch tokenization
            inputs = tokenizer(
                non_empty_texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Batch inference
            with torch.no_grad():
                logits = model(**inputs).logits
                predicted_classes = torch.argmax(logits, dim=1).tolist()
            
            # Map results back
            result_list = ["neutral"] * len(processed_texts)
            for idx, pred_class in zip(non_empty_indices, predicted_classes):
                result_list[idx] = LABELS[pred_class]
            
            results = result_list
    
    except Exception as e:
        print(f"⚠️ Batch sentiment analysis error: {e}. Using fallback.")
        results = [_textblob_sentiment(text) if text else "neutral" for text in processed_texts]
    
    return results
