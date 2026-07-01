import asyncio
import json
import os

from dotenv import load_dotenv

from audio.llm_decomposer import LLMClient
from audio.recorder import Recorder
from audio.recognizer import Recognizer

from sys_prompt_collector import get_system_prompt

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")

VOSK_MODEL_PATH = "vosk-models/vosk-model-small-ru-0.22"
SYS_PROMPT_FILE_PATH = "system_prompts/decomposer_system_prompt.txt"



async def process_llm_request(llm_client: LLMClient, text: str):
    """Fires off the LLM call completely in the background."""
    print(f"\n[LLM] Processing command: '{text}'...")
    command = await llm_client.call(text)
    print("\n[LLM] JSON Output received:")
    print(json.dumps(command, ensure_ascii=False, indent='\t'))


async def main_loop():
    if not os.path.exists(VOSK_MODEL_PATH):
        raise FileNotFoundError(f"Model path '{VOSK_MODEL_PATH}' does not exist. Please check the path.")
    
    current_loop = asyncio.get_running_loop() 

    recorder = Recorder(loop=current_loop)
    recognizer = Recognizer(model_path=VOSK_MODEL_PATH)
    llm = LLMClient(
        model=LLM_MODEL, 
        base_url=LLM_BASE_URL, 
        api_key=LLM_API_KEY,
        system_prompt=get_system_prompt(SYS_PROMPT_FILE_PATH)
    )

    recorder.start_recording()

    while True:
        chunk = await recorder.get_chunk()

        result = await asyncio.to_thread(recognizer.recognize_chunk, chunk)

        if result.get("text", ""):
            final_text = result["text"]
            print(f"\n[Vosk] Final text: {final_text}")

            asyncio.create_task(process_llm_request(llm, final_text))

        elif result.get("partial", ""):
            print(f"[Listening]: {result['partial']}", end="\r", flush=True)

if __name__ == "__main__":
    asyncio.run(main_loop())