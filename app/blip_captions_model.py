import logging

import torch
from transformers import AutoProcessor, BlipForConditionalGeneration

logger = logging.getLogger(__name__)

device = "cuda" if torch.cuda.is_available() else "cpu"

model_name = "Salesforce/blip-image-captioning-base"
processor = AutoProcessor.from_pretrained(model_name)
model = BlipForConditionalGeneration.from_pretrained(model_name).to(device)

logger.debug(f'BLIP model loaded: {model_name}, device: {device}')

if device == 'cuda':
    model.half()


def get_images_captions(images):
    inputs = processor(images=images, return_tensors="pt").to(device)
    if device == 'cuda':
        inputs = inputs.to(torch.half)

    with torch.inference_mode():
        generated_ids = model.generate(**inputs,
                                       repetition_penalty=5.0,
                                       num_beams=4, use_cache=True,
                                       min_length=15, max_new_tokens=100)

    generated_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
    return generated_texts
