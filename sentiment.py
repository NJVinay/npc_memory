from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load RoBERTa tokenizer and model for sentiment analysis
tokenizer = AutoTokenizer.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")
model = AutoModelForSequenceClassification.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")

# Sentiment labels as per model
labels = ['negative', 'neutral', 'positive']

def analyze_sentiment(input_data) -> str:
    """
    Analyze sentiment of the input text or dict containing 'response' key.
    
    Args:
        input_data (str or dict): Text string or dict with a 'response' field containing text.
        
    Returns:
        str: One of 'negative', 'neutral', or 'positive' based on sentiment classification.
    """
    # Extract text from dict or use input directly if string
    if isinstance(input_data, dict):
        text = input_data.get("response", "")
    else:
        text = input_data

    text = str(text).strip().lower()
    if not text:
        return "neutral"

    # Tokenize input text for model
    inputs = tokenizer(text, return_tensors="pt")
    
    # Disable gradient calculations for inference
    with torch.no_grad():
        logits = model(**inputs).logits

    # Get index of highest scoring class
    predicted_class = torch.argmax(logits, dim=1).item()

    # Return corresponding sentiment label
    return labels[predicted_class]
