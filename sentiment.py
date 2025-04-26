from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np

# Load RoBERTa model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")
model = AutoModelForSequenceClassification.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment")

labels = ['negative', 'neutral', 'positive']

def analyze_sentiment(text: str) -> str:
    text = text.strip().lower()
    if not text.strip():
        return "neutral"
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    predicted_class = torch.argmax(logits, dim=1).item()
    return labels[predicted_class]
