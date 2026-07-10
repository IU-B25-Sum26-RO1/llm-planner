import json
from vosk import Model, KaldiRecognizer

class Recognizer:
    def __init__(self, model_path, samplerate=16000):
        self.model = Model(model_path)
        self.samplerate = samplerate
        self.recognizer = KaldiRecognizer(self.model, self.samplerate)

    def recognize_chunk(self, audio_chunk) -> dict:
        if self.recognizer.AcceptWaveform(audio_chunk):
            result = self.recognizer.Result()
            return json.loads(result)
        else:
            partial_result = self.recognizer.PartialResult()
            return json.loads(partial_result)
        
    def finalize_recognition(self) -> dict:
        final_result = self.recognizer.FinalResult()
        return json.loads(final_result)
    
    def recognize_file(self, file_path) -> dict:
        with open(file_path, "rb") as f:
            audio_data = f.read()
            if self.recognizer.AcceptWaveform(audio_data):
                result = self.recognizer.Result()
                return json.loads(result)
        return None