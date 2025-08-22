from ..settings import Settings
from .protocols import LLMClient
from .langchain_chat_client import ChatLLM
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint, HuggingFacePipeline

# TODO  :  write interfaces for gemini and ChatHuggingFace

def instantiate_llm(settings: Settings) -> ChatLLM:
    if settings.local_model and not settings.use_hf:
        print('Loading {} from Huggingface-Transformers with 4bit: {} and 8bit: {}'.format(settings.local_model, settings.fourbit, settings.atebit))
        llm = ChatLLM(model=settings.local_model, temperature=0.1, fourbit=settings.fourbit, atebit=settings.atebit)

    elif settings.use_hf and settings.local_model:
        raise NotImplementedError("ChatHuggingFace support hasn't been implemented")
    
    else:
        raise NotImplementedError("Gemini support hasn't been implemented")
    return llm

    # elif settings.use_hf and settings.local_model:
    #     print('Creating local model through ChatHuggingFace')
    #     from transformers import BitsAndBytesConfig

    #     quantization_config = BitsAndBytesConfig(
    #         load_in_8bit=True,
    #         llm_int8_threshold=6.0,  
    #         llm_int8_skip_modules=None
    #     )
    #     chatllm = HuggingFacePipeline.from_model_id(
    #     model_id=settings.local_model,
    #     task="text-generation",
    #     pipeline_kwargs=dict(
    #         max_new_tokens=512,
    #         do_sample=False,
    #         repetition_penalty=1.03,
    #         ),
    #     model_kwargs={"quantization_config": quantization_config},
    #     )

    #     llm = ChatHuggingFace(llm=chatllm)

    # else:
    #     print('creating google model!!')
    #     if not os.getenv("GOOGLE_API_KEY") and google_api_key == None:
    #         print("Warning: GOOGLE_API_KEY not found in environment variables.")
    #         print("Please set it for the LangChain Gemini LLM to work.")
    #         return
    #     elif google_api_key is not None:
    #         os.environ["GOOGLE_API_KEY"] = google_api_key
    #     try:
    #         llm = ChatGoogleGenerativeAI(model=gemini_llm_model, temperature=0.3)
    #     except Exception as e:
    #         print(f"Error initializing Gemini LLM: {e}")
    #         print("Ensure your GOOGLE_API_KEY is set correctly and you have internet access.")

    # return llm
