import os
os.environ["DIFFUSERS_VERBOSITY"] = "critical"
os.environ["DIFFUSERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
from diffusers.utils import logging
from diffusers import StableDiffusionPipeline
import torch
import random

from .settings import load_settings
settings = load_settings()

model_id = settings['general']['image_model']

logging.set_verbosity_error()
pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16, safety_checker=None)
pipe.set_progress_bar_config(disable=True)
pipe = pipe.to('cuda')

def generate_image(description):
    image = pipe(description).images[0]  
    
    name = f'{random.randint(1000, 9999)}.png'
    image.save(name)

    return name
