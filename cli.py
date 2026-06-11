"""CLI interface for testing the chatbot locally."""
import sys
from chatbot import Chatbot


def main():
    """Run chatbot in CLI mode."""
    print("=" * 60)
    print("🤖 Nexus AI Chatbot - CLI Mode")
    print("=" * 60)
    print("Initializing chatbot...\n")
    
    bot = Chatbot()
    status = bot.get_status()
    
    print(f"✓ Model loaded: {status['intent_model_loaded']}")
    print(f"✓ Intents: {status['intents_count']}")
    print(f"✓ Local LLM: {status['local_llm'].get('available', False)}")
    print("\nType 'quit' or 'exit' to quit.\n")
    print("-" * 60)
    
    history = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in {'quit', 'exit', 'q'}:
                print("Nexus: Goodbye! Have a great day.")
                break
            
            if not user_input:
                continue
            
            response = bot.get_response(user_input, history=history, mode="balanced")
            
            print(f"\nNexus: {response['response']}")
            print(f"Intent: {response['intent']} ({response['confidence']*100:.0f}%)")
            print(f"Engine: {response['engine']}\n")
            
            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response['response']})
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
