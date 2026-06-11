import torch
import json
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
from model import NeuralNet
from nltk_utils import bag_of_words, tokenize

app = Flask(__name__)
CORS(app)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

with open('intents.json', 'r') as json_data:
    intents = json.load(json_data)

FILE = "data.pth"
data = torch.load(FILE, map_location=device, weights_only=True)

input_size = data["input_size"]
hidden_size = data["hidden_size"]
output_size = data["output_size"]
all_words = data['all_words']
tags = data['tags']
model_state = data["model_state"]

model = NeuralNet(input_size, hidden_size, output_size).to(device)
model.load_state_dict(model_state)
model.eval()

bot_name = "Nexus"

@app.route('/api/chat', methods=['POST'])
def chat():
    req_data = request.json
    sentence = req_data.get('message', '')
    
    if not sentence:
        return jsonify({'response': ''})
        
    sentence_tokens = tokenize(sentence)
    X = bag_of_words(sentence_tokens, all_words)
    X = X.reshape(1, X.shape[0])
    X = torch.from_numpy(X).to(device)

    output = model(X)
    _, predicted = torch.max(output, dim=1)

    tag = tags[predicted.item()]

    # check probability
    probs = torch.softmax(output, dim=1)
    prob = probs[0][predicted.item()]
    
    if prob.item() > 0.75:
        for intent in intents['intents']:
            if tag == intent["tag"]:
                response = random.choice(intent['responses'])
                return jsonify({'response': response})
    else:
        return jsonify({'response': "I do not understand... Please try phrasing it differently or add it to my intents.json!"})

if __name__ == '__main__':
    print("WARNING: This is the legacy intent-only server (no auth).")
    print("For login + chat, stop this and run from the project root:")
    print("  cd ..")
    print("  python app.py")
    print("Starting Intent-Based API server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
