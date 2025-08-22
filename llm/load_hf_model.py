import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

class ModelLoader:
    def __init__(self, base_model_id="mistralai/Mixtral-8x7B-Instruct-v0.1", fourbit=False, atebit=False):

        self.model_id = base_model_id

        # 4bit
        self.bnb_config_4_bit = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16
        )

        # 8bit
        self.bnb_config_8_bit = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,  
            llm_int8_skip_modules=None
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            use_fast=True, trust_remote_code=True
        )
        
        # self.tokenizer.pad_token = self.tokenizer.eos_token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        if fourbit and not atebit:
            self.llm = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                quantization_config=self.bnb_config_4_bit,
                device_map="auto",
            )
        elif atebit and not fourbit:
            self.llm = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                quantization_config=self.bnb_config_8_bit,
                device_map="auto",
            )
        elif not fourbit and not atebit:
            self.llm = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                device_map="auto",
            )
        else:
            raise ValueError("Invalid input: provide valid model quantization")
    
    def invoke(self, input: str, **gen_kwargs) -> str:
        '''
        input : plain text string
        gen_kwargs : to override runtime params
        '''
        SUPPORTED = {
                    "max_new_tokens", "min_new_tokens",
                    "temperature", "top_p", "top_k",
                    "repetition_penalty", "do_sample",
                    "num_beams", "length_penalty",
                    "eos_token_id", "pad_token_id",
                    }
        
        self.llm.eval()
        defaults = dict (
                max_new_tokens=384,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.15,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id,
                min_new_tokens=32 
        )
        clean = {k: v for k, v in gen_kwargs.items() if k in SUPPORTED}

        # support only HF params for local models
        params = {**defaults, **clean}

        messages = [{"role": "user", "content": input}]
        rendered = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )


        with torch.no_grad():
            model_input = self.tokenizer(rendered, return_tensors="pt").to("cuda")
            generated = self.llm.generate(**model_input, **params)
            # slice off the prompt
            new_tokens = generated[0, model_input["input_ids"].shape[1]:]
            text = self.tokenizer.decode(
                new_tokens, skip_special_tokens=True, pad_token_id=self.tokenizer.eos_token_id
            )
            return text