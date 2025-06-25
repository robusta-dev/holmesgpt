# Gemini

Configure HolmesGPT to use Google's Gemini models via Google AI Studio.

## Setup

Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Configuration

```bash
export GEMINI_API_KEY="your-gemini-api-key"
holmes ask "what pods are failing?" --model="gemini/<your-gemini-model>"
```
