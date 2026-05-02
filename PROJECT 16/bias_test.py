from transformers import pipeline
import pandas as pd

# Load the current biased model
classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

# Test Dataset
pidgin_samples = [
    "This food sweet die!",                # Positive
    "I dey feel the vibe of this place.",  # Positive
    "Abeg, no vex for me.",                # Neutral/Apology
    "The way dem take treat us no good.",  # Negative
    "Omo, the service na fire!"            # Positive (Slang for excellent)
]

def run_audit():
    results = classifier(pidgin_samples)
    for text, res in zip(pidgin_samples, results):
        # PROOF: Most will return 'NEGATIVE' because of 
        # OOD (Out-of-Distribution) tokenization.
        print(f"Text: {text} | Prediction: {res['label']} | Score: {res['score']:.4f}")

if __name__ == "__main__":
    run_audit()