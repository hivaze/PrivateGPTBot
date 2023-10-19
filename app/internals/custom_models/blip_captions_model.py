import logging

import torch
from transformers import AutoProcessor, BlipForConditionalGeneration

from app.bot import settings

logger = logging.getLogger(__name__)

device = settings.config.blip.device

blip_model_name = "Salesforce/blip-image-captioning-large" if settings.config.blip.use_large \
    else "Salesforce/blip-image-captioning-base"
blip_processor = AutoProcessor.from_pretrained(blip_model_name)

blip_model = BlipForConditionalGeneration.from_pretrained(blip_model_name).to(device)
blip_model = torch.compile(blip_model)

print(f'BLIP model loaded: {blip_model_name}, device: {device}')


def get_images_captions(images):
    inputs = blip_processor(images=images, return_tensors="pt").to(device)

    with torch.inference_mode():
        generated_ids = blip_model.generate(**inputs,
                                            repetition_penalty=5.0,
                                            num_beams=4, use_cache=True,
                                            min_length=15, max_new_tokens=100)

    generated_texts = blip_processor.batch_decode(generated_ids, skip_special_tokens=True)
    return generated_texts
