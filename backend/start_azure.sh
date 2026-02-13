#!/bin/bash
export USE_AZURE_OPENAI=true
export AZURE_OPENAI_ENDPOINT="https://secondbrain-resource.services.ai.azure.com"
export AZURE_OPENAI_API_KEY="YOUR_KEY_HERE"
export AZURE_CHAT_DEPLOYMENT="gpt-4.1"

echo "Starting with Azure OpenAI..."
echo "USE_AZURE_OPENAI=$USE_AZURE_OPENAI"
echo "AZURE_CHAT_DEPLOYMENT=$AZURE_CHAT_DEPLOYMENT"

./venv_new/bin/python app_v2.py
