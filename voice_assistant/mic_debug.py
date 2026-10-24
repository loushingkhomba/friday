import speech_recognition as sr
import time

def debug_mic():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("--- MICROPHONE RAW TEST ---")
            print("Checking for audio input...")
            for i in range(5):
                r.adjust_for_ambient_noise(source, duration=0.5)
                print(f"Reading Mic... Current Energy Level: {r.energy_threshold}")
                time.sleep(0.1)
            
            print("\n--- LIVE SIGNAL TEST ---")
            print("Please SPEAK LOUDLY now for 5 seconds...")
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=5)
                print("? SIGNAL DETECTED! Audio was captured.")
                try:
                    text = r.recognize_google(audio)
                    print(f"Transcription: {text}")
                except:
                    print("? SIGNAL DETECTED, but Google could not translate it.")
            except sr.WaitTimeoutError:
                print("? NO SIGNAL. The app is not receiving any audio.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    debug_mic()
