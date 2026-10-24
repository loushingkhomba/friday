import speech_recognition as sr

def test_mic():
    r = sr.Recognizer()
    languages = ["en-US", "en-IN", "en-GB"] # Test multiple English accents
    
    try:
        with sr.Microphone() as source:
            print("--- Ultimate Mic & Accent Test ---")
            print("Calibrating... Please be quiet for 2 seconds.")
            r.adjust_for_ambient_noise(source, duration=2)
            print(f"Baseline Threshold: {r.energy_threshold}")
            
            print("\nSpeak now! Try saying: \"Hello Friday, can you hear me?\"")
            print("I will try to translate your voice using different regional models...")
            
            # Listen for one good phrase
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=7)
                print("Sound captured! Attempting translation...")
                
                for lang in languages:
                    try:
                        text = r.recognize_google(audio, language=lang)
                        print(f"? SUCCESS with [{lang}]: {text}")
                        return lang
                    except sr.UnknownValueError:
                        print(f"? [{lang}] could not translate.")
                
                print("\nNone of the language models worked. Your voice might be too quiet or the background noise is too high.")
                
            except sr.WaitTimeoutError:
                print("No sound detected. Please try again.")
                
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    result = test_mic()
    if result:
        print(f"\n?? THE WINNER IS: {result}")
        print("I will update Friday to use this language model!")
